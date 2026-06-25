"""CLI: python -m lab.run --n 20 --seed 42

Runs Family-1 Template #1 against the SQL-oracle + wrong-baseline + over-refuse solvers
on live Postgres, logs a JSONL trace, and asserts the v1 machinery invariants:
oracle passes 100%, wrong-baseline fails everything, over-refuse fails every answerable item.
"""

import argparse
import sys

from lab import templates
from lab.harness import run
from lab.solvers import OverRefuseSolver, SqlOracleSolver, WrongBaselineSolver
from src.ingestion.vote_parsers import OPTION_BUCKETS


def _counts(rows: list[tuple[str, bool, bool]]) -> tuple[int, int, int, int]:
    ans = [p for (_id, ref, p) in rows if not ref]
    ref = [p for (_id, ref, p) in rows if ref]
    return sum(ans), len(ans), sum(ref), len(ref)


def main() -> int:
    parser = argparse.ArgumentParser(description="Condorcet Lab — Family 1 harness")
    parser.add_argument("--n", type=int, default=20, help="answerable instances per template")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    solvers = [SqlOracleSolver(), WrongBaselineSolver(), OverRefuseSolver()]
    results = run(templates, solvers, args.n, args.seed, set(OPTION_BUCKETS))

    print(f"Template #1 (vote_lookup), n={args.n}, seed={args.seed}")
    for name, rows in results.items():
        ap, at, rp, rt = _counts(rows)
        total_p = sum(p for *_, p in rows)
        print(f"  {name:14} pass {total_p}/{len(rows)}  (answerable {ap}/{at}, refusal {rp}/{rt})")

    oracle = results["oracle"]
    wrong = results["wrong-baseline"]
    over = results["over-refuse"]
    assert oracle and all(p for *_, p in oracle), "INVARIANT FAIL: oracle must pass 100%"
    assert not any(p for *_, p in wrong), "INVARIANT FAIL: wrong-baseline must fail every instance"
    assert not any(p for (_id, ref, p) in over if not ref), (
        "INVARIANT FAIL: over-refuse must fail every answerable instance"
    )
    print("INVARIANTS OK: oracle 100% · wrong-baseline 0% · over-refuse fails all answerable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
