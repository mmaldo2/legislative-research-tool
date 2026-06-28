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
from collections import Counter
from datetime import datetime

from lab import templates
from lab.harness import RUNS_DIR, prepare_run, solve_grade_write
from lab.solvers import AgentSolver
from src.ingestion.vote_parsers import OPTION_BUCKETS

_MODEL_IDS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-1",
}
# Per-rollout caps. ours submits in ~3 turns. The WEB arm needs more (WebSearch -> fetch_url ->
# re-search past a landing/Cloudflare page -> submit); pass 2's TEMPORAL task is turn-hungrier still
# (it must establish the vote's date AND the member's party then), so web gets a higher cap (PR-5) —
# a truncated reasoning chain classifies as `errored`, which would SILENTLY MASK the moat. The $1
# budget (total_cost_usd IS populated under subscription, ~$0.1/rollout) + the 180s timeout bound
# cost/latency regardless. (A fairness fix for web, NOT a moat tweak.)
_MAX_TURNS = 10  # ours
_MAX_TURNS_WEB = 20  # web (temporal reasoning is multi-search)
_MAX_BUDGET_USD = 1.0
_TIMEOUT_S = 180.0

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


def _run_cell(model: str, surface: str, kind: str, instances, ctx, seed: int) -> dict:
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
    out_path = RUNS_DIR / f"ablation_{model}_{surface}_{kind}_{ts}.jsonl"
    try:
        with open(out_path, "a", encoding="utf-8") as fh:
            for _s, inst, verdict in solve_grade_write(instances, [solver], ctx, seed, fh):
                h = solver.history[-1]  # this instance's diagnostic row (just appended by solve)
                x = solver.trace_extras or {}
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


def run_ablation(template_name, models, surfaces, n, seed, repeats) -> list[dict]:
    """Run the full matrix on `template_name` and print the trust-weighted report. Returns the
    per-cell-run records. The switcher/control split is a MATRIX AXIS (kind), so the headline
    ours-vs-web delta is read on the SWITCHER subset, never averaged with the control."""
    # Generate the answerable set ONCE and reuse across ALL cells + repeats (P10): so ours-vs-web
    # compares the SAME questions, and the repeats measure model variance, not sample variance.
    template = templates.TEMPLATE_REGISTRY[template_name]
    all_instances, ctx = prepare_run(template, n, seed, set(OPTION_BUCKETS))
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
                for rep in range(repeats):
                    r = _run_cell(model, surface, kind, by_kind[kind], ctx, seed)
                    runs.append(r)
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
    p.add_argument("--template", default="vote_lookup")  # pass 2: member_party_at_vote
    p.add_argument("--models", default="haiku,sonnet")
    p.add_argument("--surfaces", default="ours,web")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--repeats", type=int, default=3)
    args = p.parse_args(argv)
    run_ablation(
        args.template,
        [m.strip() for m in args.models.split(",")],
        [s.strip() for s in args.surfaces.split(",")],
        args.n,
        args.seed,
        args.repeats,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
