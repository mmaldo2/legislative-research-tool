"""Tool-surface "moat" ablation — pass 1 (vote_lookup CONTROL).

Runs the matrix surface{ours, web} × model{...} over the vote_lookup ANSWERABLE arm (the frozen
template, reused unchanged), reusing AgentSolver(surface=...) on the agent-sdk backend — surface is
the SOLE variable (backend held constant). Reports the TRUST-WEIGHTED rates PER surface, separately
(accuracy / hallucination / over_refusal / format_fail / errored + retrieved-rate), so a
confident-wrong web answer is never hidden inside raw accuracy.

This is a MEASUREMENT, not a target: a TIE is the EXPECTED pass-1 outcome (a spurious moat on this
easy lookup = a broken metric). LIVE — real WebSearch + subscription calls; run MANUALLY, NOT CI.

Reuses the frozen load glue (harness.prepare_run) + the canonical write_trace chokepoint
(harness.solve_grade_write) — no bespoke trace artifact. Runs SEQUENTIALLY (the ANTHROPIC_API_KEY
pop/restore in _asolve_sdk is a process-global race; never parallelize cells in-process).
"""

import argparse
import asyncio
from collections import Counter
from datetime import datetime
from pathlib import Path

from lab import templates
from lab.experiments.lift_instances import LIFT_TEMPLATES
from lab.harness import RUNS_DIR, prepare_run, solve_grade_write
from lab.manifest import RunManifest
from lab.solvers import _SANDBOX_IMAGE, AgentSolver, ensure_sandbox_image
from src.ingestion.vote_parsers import OPTION_BUCKETS

_MODEL_IDS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",  # pre-registered frontier (harness-lift study rev 4.2)
}


def _resolve_template(name):
    """Frozen Family-1 templates first, then the NON-FROZEN lift-study generators (REV 4.2): the
    lift study runs through this same matrix driver but its instances live outside content_hash."""
    if name in templates.TEMPLATE_REGISTRY:
        return templates.TEMPLATE_REGISTRY[name]
    if name in LIFT_TEMPLATES:
        return LIFT_TEMPLATES[name]
    raise KeyError(
        f"unknown template {name!r}; "
        f"frozen={sorted(templates.TEMPLATE_REGISTRY)} lift={sorted(LIFT_TEMPLATES)}"
    )


# Per-rollout caps. Single-event tasks (vote_lookup) submit in ~3 ours turns, but the lift study's
# WINDOW tasks (member_summary / pairwise) retrieve a large record set then run_python to tally it,
# so ours needs real headroom too (the n=1 cost probe truncated ours at 10 turns mid-tally). Both
# arms now compute (REV 4.3), so ours and web get the same turn cap. A truncated chain classifies
# as `errored` (truncation is NOT a wrong answer); the $ budget + timeout bound cost/latency too.
# PROVISIONAL pilot values — frozen into the pre-registration after the post-run_python re-probe.
# The n=6 pilot showed opus x web TIMED OUT 67% on the HONEST WebSearch+fetch_url path at 180s, so
# web accuracy is CONFOUNDED with the wall clock -> raise the web timeout/turns so the baseline gets
# a fair shot, and lift the budget so a longer honest run is not budget-truncated (a new confound).
_MAX_TURNS = 20  # ours (window retrieve + run_python tally)
_MAX_TURNS_WEB = 30  # web (multi-search WebSearch -> fetch_url -> run_python honest path)
_MAX_BUDGET_USD = 3.5  # headroom over the $1.33 opus x web observed at 180s
_TIMEOUT_S = 300.0  # was 180s; opus's honest path needs the room (pilot: 67% timeout)

_BUCKETS = ("correct", "hallucination", "over_refusal", "format_fail", "errored")
_TAG = {
    "correct": "acc",
    "hallucination": "halluc",
    "over_refusal": "over_ref",
    "format_fail": "fmt_fail",
    "errored": "err",
}


def classify(subscores: dict, errored: bool) -> str:
    """The closed-match trust partition over an ANSWERABLE item, derived purely from the frozen
    Verdict.subscores (+ the errored flag). EXHAUSTIVE + mutually exclusive; RAISES on a subscore
    state that build_verdict cannot produce (so a future None-returning grader can never silently
    land in the trust-fatal `hallucination` bucket)."""
    if errored:
        return "errored"  # P11: an SDK crash / budget-or-turn truncation — NOT a trust failure
    fv = subscores["format_valid"]
    if fv == 0.0:
        return "format_fail"  # never-submitted / non-canonical
    dc = subscores["decision_correct"]
    if dc is None:
        raise AssertionError("format_valid==1 must imply decision_correct present")
    if dc == 0.0:
        return "over_refusal"  # refused an answerable item
    ac = subscores["answer_correct"]
    if ac is None:
        raise AssertionError(
            "format_valid==1 & decision_correct==1 must imply answer_correct present"
        )
    return "correct" if ac == 1.0 else "hallucination"  # confident-correct vs confident-WRONG


def _partition_by_kind(instances) -> dict[str, list]:
    """Split the answerable instances by `params["kind"]` (the matrix axis). A template without a
    kind (vote_lookup) collapses to a single "all" bucket — so pass 1 is unchanged."""
    by_kind: dict[str, list] = {}
    for inst in instances:
        by_kind.setdefault(inst.params.get("kind", "all"), []).append(inst)
    return by_kind


def _run_cell(model: str, surface: str, kind: str, instances, ctx, seed: int, run_id=None) -> dict:
    """Run one (model, surface, kind) cell over the kind's answerable instances. Fresh solver +
    guaranteed close() (disposes the asyncpg pool on its Runner's loop). The web arm gets a higher
    turn cap (PR-5). Additively accumulates a per-switcher bucket breakdown (the cluster check) —
    the classify->Counter core is unchanged; `by_switcher` is an extra dict, keyed off the trace."""
    solver = AgentSolver(
        model=_MODEL_IDS[model],
        backend="agent-sdk",
        surface=surface,
        max_turns=_MAX_TURNS_WEB if surface == "web" else _MAX_TURNS,
        max_budget_usd=_MAX_BUDGET_USD,
        timeout_s=_TIMEOUT_S,
    )
    counts: Counter = Counter()
    by_switcher: dict[str, Counter] = {}  # switcher_name -> bucket counts (mandatory breakdown)
    retrieved = 0
    latencies: list[float] = []
    costs: list[float] = []
    subtypes: Counter = Counter()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    tag = f"{run_id}_" if run_id else ""  # run-id tag -> the manifest groups a run's cell files
    out_path = RUNS_DIR / f"ablation_{tag}{model}_{surface}_{kind}_{ts}.jsonl"
    try:
        with open(out_path, "a", encoding="utf-8") as fh:
            for _s, inst, verdict in solve_grade_write(instances, [solver], ctx, seed, fh):
                h = solver.history[-1]  # this instance's diagnostic row (just appended by solve)
                x = solver.trace_extras or {}
                # A sandbox APPARATUS failure is EXCLUDED, not a trust outcome: route it to the
                # already-non-trust `errored` bucket instead of letting classify() score the agent's
                # downstream refusal/guess as a real miss (panel blocker; the subtype stays visible
                # in result_subtypes below).
                if x.get("result_subtype") == "sandbox_infra":
                    bucket = "errored"
                else:
                    bucket = classify(verdict.subscores, h["errored"])
                counts[bucket] += 1
                sw = inst.params.get("switcher_name")
                if sw is not None:
                    by_switcher.setdefault(sw, Counter())[bucket] += 1
                retrieved += int(h["retrieved"])
                latencies.append((x.get("latency_ms") or 0.0) / 1000.0)
                if x.get("cost") is not None:
                    costs.append(x["cost"])
                if x.get("result_subtype"):
                    subtypes[x["result_subtype"]] += 1
    finally:
        solver.close()
    n = sum(counts.values())
    return {
        "model": model,
        "surface": surface,
        "kind": kind,
        "out_path": str(out_path),  # the manifest enumerates a run's cell files from this
        "n": n,
        "counts": dict(counts),
        "rates": {b: (counts[b] / n if n else 0.0) for b in _BUCKETS},
        "by_switcher": {k: dict(v) for k, v in by_switcher.items()},
        "retrieved_rate": retrieved / n if n else 0.0,
        "mean_latency_s": sum(latencies) / len(latencies) if latencies else 0.0,
        "mean_cost": sum(costs) / len(costs) if costs else None,  # may be None under subscription
        "result_subtypes": dict(subtypes),
    }


def _fmt_pct(x: float) -> str:
    return f"{100 * x:4.0f}%"


def run_ablation(
    template_name, models, surfaces, n, seed, repeats, *, run_id=None, manifest=None, exclude=None
):
    """Run the full matrix on `template_name` and print the trust-weighted report. Returns the
    per-cell-run records. The switcher/control split is a MATRIX AXIS (kind), so the headline
    ours-vs-web delta is read on the SWITCHER subset, never averaged with the control.

    `run_id` tags each cell's output filename. `manifest` (a lab.manifest.RunManifest, optional) is
    stamped with this template's RunContext hashes (before the first cell) and gets each completed
    cell's path appended + re-persisted -> crash-safe provenance for run_matrix's multi-template.
    `exclude` is a set of "model:surface" cells to SKIP (e.g. {"opus:ours"} -- goal #2, not in the
    pre-registered 5-cell design).
    """
    exclude = exclude or set()
    # Generate the answerable set ONCE and reuse across ALL cells + repeats (P10): so ours-vs-web
    # compares the SAME questions, and the repeats measure model variance, not sample variance.
    # SANDBOX PRE-FLIGHT: ensure the pinned run_python image is present (pull if missing) BEFORE any
    # rollout -- a lazy in-rollout pull would time out + pollute cell 1. A failure here means
    # run_python calls will be excluded (sandbox_infra); the digest stamp ties the run to an image.
    infra = asyncio.run(ensure_sandbox_image())
    if infra:
        print(f"  SANDBOX PRE-FLIGHT WARNING: {infra} -> run_python excluded (sandbox_infra)")
    else:
        print(f"  sandbox image ready: {_SANDBOX_IMAGE}")

    template = _resolve_template(template_name)
    all_instances, ctx = prepare_run(template, n, seed, set(OPTION_BUCKETS))
    if manifest is not None:  # stamp the run's hashes before any cell (crash-safe provenance)
        manifest.stamp_hashes(ctx, RUNS_DIR)
    answerable = [i for i in all_instances if not i.is_refusal]  # answerable arm only (B1)
    by_kind = _partition_by_kind(answerable)
    kinds = sorted(by_kind)  # e.g. ["control", "switcher"], or ["all"] for vote_lookup
    split = ", ".join(f"{k}={len(by_kind[k])}" for k in kinds)
    n_cells = len(models) * len(surfaces) * len(kinds) * repeats
    n_rollouts = len(models) * len(surfaces) * len(answerable) * repeats
    print(
        f"ABLATION pass 2 [{template.template_id}]: {len(answerable)} answerable ({split}) "
        f"(seed={seed}); models={models} surfaces={surfaces} repeats={repeats}\n"
        f"  caps: max_turns={_MAX_TURNS}(ours)/{_MAX_TURNS_WEB}(web) "
        f"max_budget_usd=${_MAX_BUDGET_USD} timeout={_TIMEOUT_S}s | backend=agent-sdk\n"
        f"  envelope: ~{n_cells} cells / ~{n_rollouts} rollouts "
        f"(<= ${n_rollouts * _MAX_BUDGET_USD:.0f} hard cap; watch for a runaway web cell)\n"
    )

    runs: list[dict] = []
    for model in models:
        for surface in surfaces:
            for kind in kinds:
                if f"{model}:{surface}" in exclude:
                    continue  # a deselected cell (e.g. opus:ours = goal #2)
                for rep in range(repeats):
                    r = _run_cell(model, surface, kind, by_kind[kind], ctx, seed, run_id=run_id)
                    runs.append(r)
                    if manifest is not None:
                        manifest.add_cell(Path(r["out_path"]), RUNS_DIR)
                    cost_str = "n/a" if r["mean_cost"] is None else f"${r['mean_cost']:.2f}"
                    rr = r["rates"]
                    print(
                        f"  [{model:7} {surface:4} {kind:8} rep{rep + 1}] "
                        f"acc={_fmt_pct(rr['correct'])} halluc={_fmt_pct(rr['hallucination'])} "
                        f"over_ref={_fmt_pct(rr['over_refusal'])} "
                        f"fmt_fail={_fmt_pct(rr['format_fail'])} "
                        f"err={_fmt_pct(rr['errored'])} retr={_fmt_pct(r['retrieved_rate'])} "
                        f"lat={r['mean_latency_s']:.0f}s cost={cost_str}"
                    )
    _print_summary(runs, models, surfaces, kinds)
    return runs


def run_matrix(
    template_names, models, surfaces, n, seed, repeats, *, run_id, prereg_sha=None, exclude=None
):
    """Run the matrix over MULTIPLE templates under ONE run_id, writing a single CRASH-SAFE manifest
    (params + seed + prereg_sha persisted before any cell; each cell file appended as it completes).
    Loops the validated single-template run_ablation per template (preserving its per-template
    summary + the SANDBOX pre-flight). The manifest is what lift_analysis reads to find a run's
    files deterministically. Returns the concatenated per-cell records."""
    manifest = RunManifest(
        run_id=run_id,
        params={
            "templates": template_names,
            "models": models,
            "surfaces": surfaces,
            "n": n,
            "repeats": repeats,
            "max_turns": _MAX_TURNS,
            "max_turns_web": _MAX_TURNS_WEB,
            "max_budget_usd": _MAX_BUDGET_USD,
            "timeout_s": _TIMEOUT_S,
            "sandbox_image": _SANDBOX_IMAGE,
            "backend": "agent-sdk",
            "exclude": sorted(exclude or set()),
        },
        rollout_seed=seed,
        prereg_doc_sha=prereg_sha,
    )
    manifest.save(RUNS_DIR)  # persist the param block BEFORE any cell runs (crash-safe)
    all_runs: list[dict] = []
    for name in template_names:
        all_runs += run_ablation(
            name,
            models,
            surfaces,
            n,
            seed,
            repeats,
            run_id=run_id,
            manifest=manifest,
            exclude=exclude,
        )
    print(
        f"\n  manifest: {RunManifest.path_for(run_id, RUNS_DIR)} "
        f"({len(manifest.cell_files)} cell files across {len(template_names)} templates)"
    )
    return all_runs


def _agg(runs, model, surface, kind, rate):
    return [
        r["rates"][rate]
        for r in runs
        if r["model"] == model and r["surface"] == surface and r["kind"] == kind
    ]


def _delta(runs, model, kind, rate):
    """web-minus-ours mean for one (model, kind, rate), or None if either arm is absent. PURE —
    the headline number, tested on synthetic run records."""
    ours = _agg(runs, model, "ours", kind, rate)
    web = _agg(runs, model, "web", kind, rate)
    if not ours or not web:
        return None
    return sum(web) / len(web) - sum(ours) / len(ours)


def _aggregate_by_switcher(cells) -> dict[str, Counter]:
    """Merge the per-switcher bucket counts across a set of cells (e.g. all reps of one
    model×surface×switcher). PURE — the cluster check, tested on synthetic run records."""
    agg: dict[str, Counter] = {}
    for c in cells:
        for sw, bucket_counts in c.get("by_switcher", {}).items():
            agg.setdefault(sw, Counter()).update(bucket_counts)
    return agg


def _print_summary(runs, models, surfaces, kinds):
    print("\n=== TRUST-WEIGHTED SUMMARY (mean [min-max] over repeats) ===")
    print("  the moat lives in HALLUCINATION on the SWITCHER subset (confident-wrong)\n")
    headline = "switcher" if "switcher" in kinds else kinds[0]
    for model in models:
        print(f"  {model}:")
        for kind in kinds:
            for surface in surfaces:
                cells = [
                    r
                    for r in runs
                    if r["model"] == model and r["surface"] == surface and r["kind"] == kind
                ]
                if not cells:
                    continue
                parts = []
                for rate in ("correct", "hallucination", "over_refusal", "format_fail", "errored"):
                    vals = [c["rates"][rate] for c in cells]
                    m = sum(vals) / len(vals)
                    lo, hi = min(vals), max(vals)
                    parts.append(f"{_TAG[rate]}={_fmt_pct(m)} [{_fmt_pct(lo)}-{_fmt_pct(hi)}]")
                retr = [c["retrieved_rate"] for c in cells]
                parts.append(f"retr={_fmt_pct(sum(retr) / len(retr))}")
                print(f"    {kind:8} {surface:4}: " + "  ".join(parts))
        # headline ours-vs-web delta on the SWITCHER subset (where the moat is), never averaged in
        if "ours" in surfaces and "web" in surfaces:
            for rate, tag in (("correct", "acc"), ("hallucination", "halluc")):
                d = _delta(runs, model, headline, rate)
                if d is not None:
                    print(f"    delta(web-ours) {tag} [{headline}]: {100 * d:+.0f}pp")
    _print_switcher_breakdown(runs, models, surfaces)
    print(
        "\n  the SWITCHER halluc rate is the moat; the control should ~tie (web's current default "
        "is RIGHT there). A switcher gap WITHOUT control-parity => a confound, not a moat.\n"
        "  n_eff ~= the switcher CLUSTER count — READ TRACES + the per-switcher rows first."
    )


def _print_switcher_breakdown(runs, models, surfaces):
    """The cluster check: the switcher moat must not be one famous member. Per (model, surface),
    print each switcher's correct/halluc/total over the switcher cells."""
    if not any(r["kind"] == "switcher" for r in runs):
        return
    print("\n  --- per-switcher (cluster check: the moat must not be one famous switcher) ---")
    for model in models:
        for surface in surfaces:
            cells = [
                r
                for r in runs
                if r["model"] == model and r["surface"] == surface and r["kind"] == "switcher"
            ]
            if not cells:
                continue
            agg = _aggregate_by_switcher(cells)
            parts = []
            for sw in sorted(agg):
                c = agg[sw]
                label = sw.split(",")[0]  # "Rep. Amash, Justin [..]" -> "Rep. Amash"
                parts.append(f"{label}: {c.get('correct', 0)}c/{c.get('hallucination', 0)}h")
            print(f"    {model:7} {surface:4}: " + " | ".join(parts))


def main(argv=None) -> int:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description="Tool-surface moat ablation (pass 1/2)")
    # frozen (vote_lookup, member_party_at_vote, ...) or lift-study (lift_member_summary,
    # lift_pairwise — the harness-lift ablation, REV 4.2). Comma-separated for a multi-template run.
    p.add_argument("--template", default="vote_lookup")
    p.add_argument("--models", default="haiku,sonnet")
    p.add_argument("--surfaces", default="ours,web")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--repeats", type=int, default=3)
    # --run-id -> write a manifest (lift_analysis reads it); --prereg-sha is the committed
    # pre-registration doc SHA (stamped explicitly, NOT auto-derived from repo HEAD).
    p.add_argument("--run-id", default=None)
    p.add_argument("--prereg-sha", default=None)
    # cells to SKIP, comma-separated "model:surface" (e.g. opus:ours -- goal #2, off the 5 cells)
    p.add_argument("--exclude", default="")
    args = p.parse_args(argv)
    template_names = [t.strip() for t in args.template.split(",")]
    models = [m.strip() for m in args.models.split(",")]
    surfaces = [s.strip() for s in args.surfaces.split(",")]
    exclude = {x.strip() for x in args.exclude.split(",") if x.strip()}
    if args.run_id:
        run_matrix(
            template_names,
            models,
            surfaces,
            args.n,
            args.seed,
            args.repeats,
            run_id=args.run_id,
            prereg_sha=args.prereg_sha,
            exclude=exclude,
        )
    else:  # back-compat: no manifest, single or multi template
        for name in template_names:
            run_ablation(name, models, surfaces, args.n, args.seed, args.repeats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
