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
# Tight per-rollout caps for pass 1: a simple lookup has no excuse for 14 turns / $6 (those are the
# big-window defaults). The smoke confirmed total_cost_usd IS populated under subscription, so the
# budget cap is a real guard; max_turns is the turn backstop, timeout the wall-clock backstop.
_MAX_TURNS = 6
_MAX_BUDGET_USD = 1.0
_TIMEOUT_S = 180.0

_BUCKETS = ("correct", "hallucination", "over_refusal", "format_fail", "errored")


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


def _run_cell(model: str, surface: str, instances, ctx, seed: int) -> dict:
    """Run one (model, surface) cell over the pre-filtered answerable instances. Fresh solver +
    guaranteed close() (disposes the asyncpg pool on its Runner's loop)."""
    solver = AgentSolver(
        model=_MODEL_IDS[model],
        backend="agent-sdk",
        surface=surface,
        max_turns=_MAX_TURNS,
        max_budget_usd=_MAX_BUDGET_USD,
        timeout_s=_TIMEOUT_S,
    )
    counts: Counter = Counter()
    retrieved = 0
    latencies: list[float] = []
    costs: list[float] = []
    subtypes: Counter = Counter()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    out_path = RUNS_DIR / f"ablation_{model}_{surface}_{ts}.jsonl"
    try:
        with open(out_path, "a", encoding="utf-8") as fh:
            for _s, _inst, verdict in solve_grade_write(instances, [solver], ctx, seed, fh):
                h = solver.history[-1]  # this instance's diagnostic row (just appended by solve)
                x = solver.trace_extras or {}
                counts[classify(verdict.subscores, h["errored"])] += 1
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
        "n": n,
        "counts": dict(counts),
        "rates": {b: (counts[b] / n if n else 0.0) for b in _BUCKETS},
        "retrieved_rate": retrieved / n if n else 0.0,
        "mean_latency_s": sum(latencies) / len(latencies) if latencies else 0.0,
        "mean_cost": sum(costs) / len(costs) if costs else None,  # may be None under subscription
        "result_subtypes": dict(subtypes),
    }


def _fmt_pct(x: float) -> str:
    return f"{100 * x:4.0f}%"


def run_ablation(models, surfaces, n, seed, repeats) -> list[dict]:
    """Run the full matrix and print the trust-weighted report. Returns the per-cell-run records."""
    # Generate the answerable set ONCE and reuse across ALL cells + repeats (P10): so ours-vs-web
    # compares the SAME questions, and the repeats measure model variance, not sample variance.
    all_instances, ctx = prepare_run(
        templates.TEMPLATE_REGISTRY["vote_lookup"], n, seed, set(OPTION_BUCKETS)
    )
    instances = [i for i in all_instances if not i.is_refusal]  # answerable arm only (B1)
    print(
        f"ABLATION pass 1 (vote_lookup control): {len(instances)} answerable instances "
        f"(seed={seed}); models={models} surfaces={surfaces} repeats={repeats}\n"
        f"  caps: max_turns={_MAX_TURNS} max_budget_usd=${_MAX_BUDGET_USD} timeout={_TIMEOUT_S}s "
        f"| backend=agent-sdk (surface = sole variable)\n"
    )

    runs: list[dict] = []
    for model in models:
        for surface in surfaces:
            for rep in range(repeats):
                r = _run_cell(model, surface, instances, ctx, seed)
                runs.append(r)
                cost_str = "n/a" if r["mean_cost"] is None else f"${r['mean_cost']:.2f}"
                rr = r["rates"]
                print(
                    f"  [{model:7} {surface:4} rep{rep + 1}] "
                    f"acc={_fmt_pct(rr['correct'])} halluc={_fmt_pct(rr['hallucination'])} "
                    f"over_ref={_fmt_pct(rr['over_refusal'])} "
                    f"fmt_fail={_fmt_pct(rr['format_fail'])} "
                    f"err={_fmt_pct(rr['errored'])} retr={_fmt_pct(r['retrieved_rate'])} "
                    f"lat={r['mean_latency_s']:.0f}s cost={cost_str}"
                )
    _print_summary(runs, models, surfaces)
    return runs


def _agg(runs, model, surface, rate):
    vals = [r["rates"][rate] for r in runs if r["model"] == model and r["surface"] == surface]
    return vals


def _print_summary(runs, models, surfaces):
    print("\n=== TRUST-WEIGHTED SUMMARY (mean [min-max] over repeats) ===")
    print("  the moat lives in HALLUCINATION (confident-wrong), not raw accuracy\n")
    for model in models:
        print(f"  {model}:")
        for surface in surfaces:
            cells = [r for r in runs if r["model"] == model and r["surface"] == surface]
            if not cells:
                continue
            parts = []
            for rate in ("correct", "hallucination", "over_refusal", "format_fail", "errored"):
                vals = [c["rates"][rate] for c in cells]
                m = sum(vals) / len(vals)
                lo, hi = min(vals), max(vals)
                tag = {
                    "correct": "acc",
                    "hallucination": "halluc",
                    "over_refusal": "over_ref",
                    "format_fail": "fmt_fail",
                    "errored": "err",
                }[rate]
                parts.append(f"{tag}={_fmt_pct(m)} [{_fmt_pct(lo)}-{_fmt_pct(hi)}]")
            retr = [c["retrieved_rate"] for c in cells]
            parts.append(f"retr={_fmt_pct(sum(retr) / len(retr))}")
            print(f"    {surface:4}: " + "  ".join(parts))
        # ours-vs-web delta per model (on the rates that matter)
        if "ours" in surfaces and "web" in surfaces:
            for rate, tag in (("correct", "acc"), ("hallucination", "halluc")):
                ours = _agg(runs, model, "ours", rate)
                web = _agg(runs, model, "web", rate)
                if ours and web:
                    d = sum(web) / len(web) - sum(ours) / len(ours)
                    print(f"    delta(web-ours) {tag}: {100 * d:+.0f}pp")
    print(
        "\n  EXPECTED for a control = a TIE (delta ~0). A real ours>web gap on this easy lookup => "
        "suspect the metric/harness (did web actually search + retrieve the right roll call?)."
    )


def main(argv=None) -> int:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description="Tool-surface moat ablation: pass 1 (vote_lookup)")
    p.add_argument("--models", default="haiku,sonnet")
    p.add_argument("--surfaces", default="ours,web")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--repeats", type=int, default=3)
    args = p.parse_args(argv)
    run_ablation(
        [m.strip() for m in args.models.split(",")],
        [s.strip() for s in args.surfaces.split(",")],
        args.n,
        args.seed,
        args.repeats,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
