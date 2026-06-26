"""CLI: python -m lab.run --template vote_lookup --n 20 --seed 42        (deterministic solvers)
       python -m lab.run --template vote_lookup --agent --n 10           (live agent — real LLM)

Deterministic mode runs the SQL-oracle + wrong-baseline + over-refuse solvers and ASSERTS the v1
machinery invariants (oracle 100% / wrong-baseline 0% / over-refuse fails answerable). Agent mode
runs the live AgentSolver: a non-deterministic measurement, so it asserts NO invariant — its pass
rate is the signal. The two modes are separate code paths (the agent run has no oracle/wrong/over
keys, so it must never touch the deterministic-invariant block).
"""

import argparse
import sys

from lab import templates
from lab.harness import get_connection, run
from lab.precompute import Precomputed
from lab.solvers import AgentSolver, OverRefuseSolver, SqlOracleSolver, WrongBaselineSolver
from src.ingestion.vote_parsers import OPTION_BUCKETS


def _counts(rows) -> tuple[int, int, int, int]:
    ans = [v.passed for (_id, ref, v) in rows if not ref]
    ref = [v.passed for (_id, ref, v) in rows if ref]
    return sum(ans), len(ans), sum(ref), len(ref)


def vote_lookup_name_collisions(conn, instances) -> set[str]:
    """Answerable vote_lookup instance ids whose looked-up member shares a NAME with another voter
    in the SAME event. The prompt gives a name but the gold is person_id-keyed, so a collision is
    INPUT AMBIGUITY, not an agent error — excluded from the *reported* clean rate. Read-only; never
    touches gold."""
    cur = conn.cursor()
    collided: set[str] = set()
    for inst in instances:
        if inst.is_refusal or not inst.template_id.endswith("vote_lookup"):
            continue
        eid = inst.params["vote_event_id"]
        pid = inst.params["person_id"]
        cur.execute(
            "SELECT COUNT(*) FROM vote_records vr JOIN people p ON p.id = vr.person_id "
            "WHERE vr.vote_event_id = %s AND p.name = (SELECT name FROM people WHERE id = %s)",
            (eid, pid),
        )
        if cur.fetchone()[0] > 1:
            collided.add(inst.instance_id)
    return collided


def _name_collisions(template, name: str, n: int, seed: int) -> set[str]:
    """Regenerate the (seed-deterministic) instances read-only and flag name collisions. Scoped to
    vote_lookup (its generate ignores `precomputed`, so an empty one yields the identical set)."""
    if name != "vote_lookup":
        return set()
    conn = get_connection()
    try:
        instances = template.generate(conn, n, seed, Precomputed())
        return vote_lookup_name_collisions(conn, instances)
    finally:
        conn.close()


def _run_deterministic(template, name: str, n: int, seed: int) -> int:
    solvers = [SqlOracleSolver(), WrongBaselineSolver(), OverRefuseSolver()]
    results = run(template, solvers, n, seed, set(OPTION_BUCKETS))

    print(f"Template {name}, n={n}, seed={seed}")
    for sname, rows in results.items():
        ap, at, rp, rt = _counts(rows)
        passed = sum(v.passed for *_, v in rows)
        mean_score = sum(v.score for *_, v in rows) / len(rows)
        print(
            f"  {sname:14} pass {passed}/{len(rows)} "
            f"(answerable {ap}/{at}, refusal {rp}/{rt})  mean_score={mean_score:.2f}"
        )

    oracle = results["oracle"]
    wrong = results["wrong-baseline"]
    over = results["over-refuse"]
    assert oracle and all(v.passed for *_, v in oracle), "INVARIANT FAIL: oracle must pass 100%"
    assert not any(v.passed for *_, v in wrong), "INVARIANT FAIL: wrong-baseline must pass nothing"
    assert all(
        v.subscores["decision_correct"] == 1.0 and v.subscores["answer_correct"] == 0.0
        for (_id, ref, v) in wrong
        if not ref
    ), "INVARIANT FAIL: wrong-baseline answerable must be attempted-but-wrong"
    assert all(v.subscores["decision_correct"] == 0.0 for (_id, ref, v) in over if not ref), (
        "INVARIANT FAIL: over-refuse must over-refuse every answerable instance"
    )
    print("INVARIANTS OK: oracle 100% · wrong-baseline 0% · over-refuse fails all answerable")
    return 0


def _run_agent(template, name: str, n: int, seed: int, model: str | None = None) -> int:
    # NON-DETERMINISTIC: a live agent's pass rate IS the measurement; no invariant is asserted.
    solver = AgentSolver(model=model) if model else AgentSolver()
    try:
        results = run(template, [solver], n, seed, set(OPTION_BUCKETS))
    finally:
        solver.close()

    rows = results["agent"]
    ap, at, rp, rt = _counts(rows)
    passed = sum(v.passed for *_, v in rows)
    mean_score = sum(v.score for *_, v in rows) / len(rows)
    print(f"AGENT run: template {name}, n={n}, seed={seed}, model={solver.model}")
    print(
        f"  pass {passed}/{len(rows)} "
        f"(answerable {ap}/{at}, refusal {rp}/{rt})  mean_score={mean_score:.2f}"
    )
    for iid, ref, v in rows:
        kind = "refusal" if ref else "answerable"
        print(f"    [{'PASS' if v.passed else 'FAIL'}] {kind:10} {iid}  score={v.score:.2f}")

    # Fairness diagnostics (additive — NEVER touch a grader): separate a protocol/format miss from
    # a knowledge miss, surface a harness/API problem, and flag passes that did NO retrieval (a
    # base-rate / prompt-phrasing game, not real lookup).
    hist = {h["instance_id"]: h for h in solver.history}
    fmt_fail = sum(1 for (_i, _r, v) in rows if v.subscores.get("format_valid") == 0.0)
    errored = sum(1 for h in solver.history if h["errored"])
    no_retrieval_pass = sum(
        1 for (iid, _ref, v) in rows if v.passed and not hist.get(iid, {}).get("retrieved", True)
    )
    print(
        f"  diagnostics: format-fail (never-submitted/non-canonical/error) {fmt_fail}/{len(rows)}; "
        f"agent-errors {errored}; passes with NO get_vote_event call {no_retrieval_pass}"
    )
    if errored:
        print("  WARNING: agent-errors present — high count = harness/API problem, not the agent")
    if no_retrieval_pass:
        print("  WARNING: passes WITHOUT retrieval — possible base-rate/phrasing game; inspect")

    # A4b: name-collision noise floor (read-only; never touches gold; must not break the run).
    try:
        collided = _name_collisions(template, name, n, seed)
    except Exception as exc:  # noqa: BLE001 — a diagnostic must never abort the measurement
        print(f"  (name-collision diagnostic skipped: {type(exc).__name__}: {exc})")
    else:
        if collided:
            clean = [r for r in rows if r[0] not in collided]
            cap = sum(v.passed for *_, v in clean)
            rate = cap / len(clean) if clean else 0.0
            print(
                f"  name-collision instances excluded: {len(collided)}; "
                f"clean pass {cap}/{len(clean)} ({rate:.2f})"
            )
        else:
            print("  no name-collision ambiguity in this sample")
    print("(measurement — no invariant asserted for a non-deterministic agent)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Condorcet Lab — Family 1 harness")
    parser.add_argument(
        "--n", type=int, default=None, help="answerable instances (default 20; 10 for --agent)"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--template",
        default="vote_lookup",
        choices=sorted(templates.TEMPLATE_REGISTRY),
        help="which Family 1 template to run",
    )
    parser.add_argument(
        "--agent",
        action="store_true",
        help="run the live AgentSolver (real LLM calls); skips the deterministic invariants",
    )
    parser.add_argument(
        "--model", default=None, help="override the agent model (default claude-sonnet-4-6)"
    )
    args = parser.parse_args(argv)

    n = args.n if args.n is not None else (10 if args.agent else 20)
    template = templates.TEMPLATE_REGISTRY[args.template]
    if args.agent:
        return _run_agent(template, args.template, n, args.seed, args.model)
    return _run_deterministic(template, args.template, n, args.seed)


if __name__ == "__main__":
    sys.exit(main())
