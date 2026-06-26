"""CLI: python -m lab.run --n 20 --seed 42

Runs Family-1 Template #1 against the SQL-oracle + wrong-baseline + over-refuse solvers
on live Postgres, logs a JSONL trace, and asserts the v1 machinery invariants in Verdict
terms: oracle passes 100%, wrong-baseline passes nothing (answerable = attempted-but-wrong),
over-refuse over-refuses every answerable item.
"""

import argparse
import sys

from lab import templates
from lab.harness import run
from lab.solvers import OverRefuseSolver, SqlOracleSolver, WrongBaselineSolver
from src.ingestion.vote_parsers import OPTION_BUCKETS


def _counts(rows) -> tuple[int, int, int, int]:
    ans = [v.passed for (_id, ref, v) in rows if not ref]
    ref = [v.passed for (_id, ref, v) in rows if ref]
    return sum(ans), len(ans), sum(ref), len(ref)


def main() -> int:
    parser = argparse.ArgumentParser(description="Condorcet Lab — Family 1 harness")
    parser.add_argument("--n", type=int, default=20, help="answerable instances per template")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--template",
        default="vote_lookup",
        choices=sorted(templates.TEMPLATE_REGISTRY),
        help="which Family 1 template to run",
    )
    args = parser.parse_args()

    template = templates.TEMPLATE_REGISTRY[args.template]
    solvers = [SqlOracleSolver(), WrongBaselineSolver(), OverRefuseSolver()]
    results = run(template, solvers, args.n, args.seed, set(OPTION_BUCKETS))

    print(f"Template {args.template}, n={args.n}, seed={args.seed}")
    for name, rows in results.items():
        ap, at, rp, rt = _counts(rows)
        passed = sum(v.passed for *_, v in rows)
        mean_score = sum(v.score for *_, v in rows) / len(rows)
        print(
            f"  {name:14} pass {passed}/{len(rows)} "
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


if __name__ == "__main__":
    sys.exit(main())
