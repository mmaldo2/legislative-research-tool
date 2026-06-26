"""Corpus batch harness: run ALL Family 1 templates × multiple seeds in ONE process,
paying the expensive `precompute` (5.4M-row scan) ONCE and reusing it across the whole matrix.

This is the diagnostic primitive behind a "real corpus batch": it does not just re-assert the
deterministic invariants at scale (oracle 100% / wrong-baseline 0% / over-refuse fails answerable),
it also CHARACTERIZES the distribution each generator produces — refusal ratio, gold-magnitude
spread (e.g. how often `party_defection` gold is 0, how often `crossed_party` is the empty set),
and the eligibility yield of each gate. That shape is what tells us whether a template is
well-formed before a live agent is ever pointed at it.

Run (detached is fine — it only reads):
    uv run python -m lab.batch --n 200 --seeds 42,43,44

Traces append to lab/runs/batch_<ts>.jsonl (the source of truth, gitignored); a human-readable
summary lands at lab/runs/batch_<ts>_summary.md plus a machine summary _summary.json.
"""

import argparse
import functools
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from lab import templates
from lab.harness import RUNS_DIR, get_connection, solve_grade_write, validate_gold
from lab.precompute import precompute
from lab.solvers import OverRefuseSolver, SqlOracleSolver, WrongBaselineSolver
from lab.trace import (
    RunContext,
    content_hash,
    dataset_fingerprint,
    grading_contract_hash,
)
from src.ingestion.vote_parsers import OPTION_BUCKETS


@dataclass
class TemplateStats:
    """Accumulator for one template across every seed in the matrix."""

    answerable: int = 0
    refusal: int = 0
    errors: list[str] = field(default_factory=list)
    grader: str | None = None  # the (constant per template) answerable grader
    # solver_name -> verdict rows: (is_refusal, passed, decision_correct, answer_correct, score)
    by_solver: dict[str, list[tuple]] = field(default_factory=dict)
    golds: list[Any] = field(default_factory=list)  # answerable gold values, for characterization


def _memoize_pure(fn):
    """Cache the single (conn, pre) result of a pure gate query for the batch's load phase.
    `functools.cache` can't be used (conn / Precomputed are unhashable) — but exactly one
    (conn, pre) exists per batch, and the DB is opened read-only, so one cached result is correct.
    Collapses the generators' ~10 repeated `_party_eligible_events` calls (each ≥ the precompute
    scan) to one, honoring the batch's 'pay the expensive scan once' premise."""
    box: dict[str, Any] = {}

    @functools.wraps(fn)
    def wrapper(conn, pre):
        if "v" not in box:
            box["v"] = fn(conn, pre)
        return box["v"]

    return wrapper


def _median(vals: list[int | float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    mid = len(s) // 2
    return float(s[mid]) if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def _int_buckets(vals: list[int]) -> dict[str, int]:
    """Coarse magnitude histogram (exact spread is in min/max/mean; this reads at a glance).
    A `<0` bucket is required: tally's `margin` gold is negative on every failed roll call."""
    labels = ["<0", "0", "1", "2-5", "6-10", "11-25", "26+"]
    out = dict.fromkeys(labels, 0)
    for v in vals:
        if v < 0:
            out["<0"] += 1
        elif v == 0:
            out["0"] += 1
        elif v == 1:
            out["1"] += 1
        elif v <= 5:
            out["2-5"] += 1
        elif v <= 10:
            out["6-10"] += 1
        elif v <= 25:
            out["11-25"] += 1
        else:
            out["26+"] += 1
    return out


def _int_summary(vals: list[int]) -> dict:
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "min": min(vals),
        "max": max(vals),
        "mean": round(sum(vals) / len(vals), 2),
        "median": _median(vals),
        "zero_count": sum(1 for v in vals if v == 0),
        "zero_frac": round(sum(1 for v in vals if v == 0) / len(vals), 3),
        "buckets": _int_buckets(vals),
    }


def _characterize_gold(grader: str, golds: list[Any]) -> dict:
    """Describe the gold-value distribution for one template, keyed off its grader shape."""
    if not golds:
        return {"kind": "empty"}
    if grader == "exact":  # scalar option string -> value frequency
        return {"kind": "option", "n": len(golds), "value_freq": dict(Counter(golds))}
    if grader == "exact_int":  # bare int (e.g. defection count)
        return {"kind": "int", **_int_summary(list(golds))}
    if grader == "set_match":  # set of ids -> size distribution + empty fraction
        sizes = [len(g) for g in golds]
        return {
            "kind": "set",
            "size": _int_summary(sizes),
            "empty_frac": round(sum(1 for s in sizes if s == 0) / len(sizes), 3),
        }
    if grader == "fields":  # dict -> per-key characterization
        fields: dict[str, dict] = {}
        for key in golds[0]:
            vals = [g[key] for g in golds]
            if all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
                fields[key] = {"kind": "int", **_int_summary(vals)}
            else:
                fields[key] = {"kind": "value", "value_freq": dict(Counter(vals))}
        return {"kind": "fields", "n": len(golds), "fields": fields}
    return {"kind": "unknown", "grader": grader, "n": len(golds)}


def _invariants(rows_by_solver: dict[str, list[tuple]]) -> dict:
    """Re-assert the deterministic-solver invariants over the FULL distribution (not just n=20)."""
    oracle = rows_by_solver.get("oracle", [])
    wrong = rows_by_solver.get("wrong-baseline", [])
    over = rows_by_solver.get("over-refuse", [])
    # tuple = (is_refusal, passed, decision_correct, answer_correct, score)
    return {
        # a corpus-shape tool must not show a vacuous green for a template that emitted nothing
        # answerable (e.g. an eligibility gate that yielded zero, or a generator that errored).
        "has_answerable": any(not r for (r, *_rest) in oracle),
        "oracle_pass_all": bool(oracle) and all(p for (_r, p, _d, _a, _s) in oracle),
        "wrong_pass_none": not any(p for (_r, p, _d, _a, _s) in wrong),
        "wrong_answerable_attempted_wrong": all(
            d == 1.0 and a == 0.0 for (r, _p, d, a, _s) in wrong if not r
        ),
        "over_refuse_answerable_decision_zero": all(
            d == 0.0 for (r, _p, d, _a, _s) in over if not r
        ),
    }


def _eligibility_yield(conn, pre) -> dict:
    """How many events survive each gate — bounds how many distinct instances ever exist."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vote_events")
    total_events = cur.fetchone()[0]
    return {
        "vote_events_total": total_events,
        "complete_events": len(pre.complete_events),
        "completed_congresses": sorted(pre.completed_congresses),
        "party_eligible_events": len(templates._party_eligible_events(conn, pre)),
        "fully_complete_windows": len(templates._fully_complete_windows(conn, pre)),
    }


def _render_markdown(summary: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Family 1 corpus batch — {summary['timestamp']}")
    lines.append("")
    lines.append(
        f"n={summary['n']} per template per seed · seeds={summary['seeds']} · "
        f"engine=postgres · trace={summary['trace_file']}"
    )
    lines.append("")
    lines.append(f"- content_hash: `{summary['content_hash'][:16]}…`")
    lines.append(f"- grading_contract_hash: `{summary['grading_contract_hash'][:16]}…`")
    lines.append("")

    y = summary["eligibility_yield"]
    lines.append("## Eligibility yield (gate funnel)")
    lines.append("")
    lines.append(f"- vote_events total: **{y['vote_events_total']:,}**")
    lines.append(f"- complete_events (reconcile exactly): **{y['complete_events']:,}**")
    lines.append(
        f"- party_eligible_events (complete ∩ completed ∩ 1-span): "
        f"**{y['party_eligible_events']:,}**"
    )
    lines.append(f"- fully_complete_windows: **{y['fully_complete_windows']}**")
    lines.append(f"- completed_congresses: {', '.join(y['completed_congresses'])}")
    lines.append("")

    lines.append("## Per-template")
    for name, t in summary["templates"].items():
        lines.append("")
        lines.append(f"### {name}")
        if t["errors"]:
            lines.append("")
            lines.append(f"**ERRORS ({len(t['errors'])}):**")
            for e in t["errors"]:
                lines.append(f"- {e}")
        ratio = (
            round(t["refusal"] / (t["answerable"] + t["refusal"]), 3)
            if (t["answerable"] + t["refusal"])
            else 0
        )
        sat = " ⚠️ SATURATED (answerable < n×seeds)" if t["saturated"] else ""
        lines.append("")
        lines.append(
            f"- instances: {t['answerable']} answerable + {t['refusal']} refusal "
            f"(refusal ratio {ratio}; requested {t['requested_n']}){sat}"
        )
        inv = t["invariants"]
        ok = "✅" if all(inv.values()) else "❌"
        lines.append(f"- invariants {ok}: {inv}")
        lines.append(f"- gold distribution: `{json.dumps(t['gold'], default=str)}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Condorcet Lab — Family 1 corpus batch")
    parser.add_argument(
        "--n", type=int, default=200, help="answerable instances per template per seed"
    )
    parser.add_argument("--seeds", default="42,43,44", help="comma-separated seeds")
    parser.add_argument(
        "--templates",
        default="all",
        help="comma-separated template names, or 'all'",
    )
    args = parser.parse_args()

    # The summary carries unicode (∩, ·, ✅); keep a Windows cp1252 console from crashing on print.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    seeds = [int(s) for s in args.seeds.split(",")]
    names = (
        sorted(templates.TEMPLATE_REGISTRY)
        if args.templates == "all"
        else args.templates.split(",")
    )
    unknown = [t for t in names if t not in templates.TEMPLATE_REGISTRY]
    if unknown:
        parser.error(
            f"unknown template(s) {unknown}; choose from {sorted(templates.TEMPLATE_REGISTRY)}"
        )
    valid_options = set(OPTION_BUCKETS)
    solvers = [SqlOracleSolver(), WrongBaselineSolver(), OverRefuseSolver()]
    stats: dict[str, TemplateStats] = {name: TemplateStats() for name in names}

    # --- LOAD PHASE: ONE read-only REPEATABLE READ snapshot so precompute + every generator see a
    # consistent DB; precompute + fingerprint ONCE; the two heavy gate queries memoized for the run.
    conn = get_connection()
    conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
    orig_pe = templates._party_eligible_events
    orig_fcw = templates._fully_complete_windows
    templates._party_eligible_events = _memoize_pure(orig_pe)
    templates._fully_complete_windows = _memoize_pure(orig_fcw)
    try:
        pre = precompute(conn)
        ctx = RunContext(
            grading_contract_hash=grading_contract_hash(),
            content_hash=content_hash(),
            dataset_fingerprint=dataset_fingerprint(conn, pre),
        )
        yield_stats = _eligibility_yield(conn, pre)
        matrix: list[tuple[str, int, list]] = []
        for name in names:
            template = templates.TEMPLATE_REGISTRY[name]
            for seed in seeds:
                try:
                    instances = template.generate(conn, args.n, seed, pre)
                    for inst in instances:
                        validate_gold(inst, valid_options)
                    matrix.append((name, seed, instances))
                except Exception as exc:  # diagnostic: record + continue, don't abort the matrix
                    conn.rollback()  # clear any aborted txn so later generators aren't poisoned
                    stats[name].errors.append(f"seed {seed}: {type(exc).__name__}: {exc}")
    finally:
        templates._party_eligible_events = orig_pe  # never leave the frozen module patched
        templates._fully_complete_windows = orig_fcw
        conn.close()

    # --- SOLVE/GRADE PHASE (no conn): one JSONL for the whole batch ---
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    trace_path = RUNS_DIR / f"batch_{ts}.jsonl"

    with open(trace_path, "a", encoding="utf-8") as fh:
        for name, seed, instances in matrix:
            st = stats[name]
            for inst in instances:
                if inst.is_refusal:
                    st.refusal += 1
                else:
                    st.answerable += 1
                    st.grader = st.grader or inst.grader
                    st.golds.append(inst.gold)
            # the FROZEN solve->grade->write chokepoint (shared with harness.run, never forked)
            for solver, inst, verdict in solve_grade_write(instances, solvers, ctx, seed, fh):
                st.by_solver.setdefault(solver.name, []).append(
                    (
                        inst.is_refusal,
                        verdict.passed,
                        verdict.subscores["decision_correct"],
                        verdict.subscores["answer_correct"],
                        verdict.score,
                    )
                )

    # --- SUMMARY ---
    requested_n = args.n * len(seeds)  # the max answerable a template could yield over all seeds
    template_summaries: dict[str, dict] = {}
    for name in names:
        st = stats[name]
        template_summaries[name] = {
            "answerable": st.answerable,
            "refusal": st.refusal,
            "requested_n": requested_n,
            "saturated": st.answerable < requested_n,
            "errors": st.errors,
            "invariants": _invariants(st.by_solver),
            "gold": _characterize_gold(st.grader, st.golds) if st.grader else {"kind": "none"},
        }

    summary = {
        "timestamp": ts,
        "n": args.n,
        "seeds": seeds,
        "templates": template_summaries,
        "eligibility_yield": yield_stats,
        "trace_file": str(trace_path),
        "content_hash": ctx.content_hash,
        "grading_contract_hash": ctx.grading_contract_hash,
        "dataset_fingerprint": ctx.dataset_fingerprint,
    }

    md = _render_markdown(summary)
    (RUNS_DIR / f"batch_{ts}_summary.md").write_text(md, encoding="utf-8")
    print(md)

    all_ok = all(
        all(t["invariants"].values()) and not t["errors"] for t in template_summaries.values()
    )
    print(f"\nBATCH {'OK' if all_ok else 'HAD FAILURES'} · trace={trace_path}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
