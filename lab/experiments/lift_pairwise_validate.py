"""READ-ONLY validation of the lift_pairwise gold's JOIN LOGIC (harness-lift study).

`lift_pairwise` has never run live. Its gold (`_pairwise_gold`) is a SQL self-join of two members'
vote_records (both cast yea/nay -> shared_event; same option -> agreement). The per-(member, roll)
OPTIONS underneath are already validated by the 40/40 roster spot-check (lift_roster_spotcheck.py),
so what remains unproven is the JOIN itself. This recomputes {agreements, shared_events} for seeded
pairs INDEPENDENTLY in Python -- from each member's full record dict, a different code path -- and
asserts it equals the SQL gold. A join bug (wrong filter, double-count, yea/nay edge) would diverge
here while still looking internally consistent in a graded run. NEVER writes (SELECTs only).

Run: PYTHONPATH=. uv run python -m lab.experiments.lift_pairwise_validate
"""

from lab.experiments.lift_instances import (
    _house_member_ids,
    _pairwise_gold,
    member_pairs,
)
from lab.experiments.lift_roster_spotcheck import _member_rolls
from lab.harness import get_connection

SEED = 42
N_PAIRS = 8  # seeded disjoint pairs to cross-check


def recompute_pairwise(rolls_a: dict[str, str], rolls_b: dict[str, str]) -> dict[str, int]:
    """{agreements, shared_events} over the events BOTH members cast yea/nay -- the same contract as
    `_pairwise_gold`, recomputed from per-member {event_id: option} dicts. PURE (hermetically
    testable; no DB)."""
    yn = ("yea", "nay")
    shared = agreements = 0
    for event_id, opt_a in rolls_a.items():
        opt_b = rolls_b.get(event_id)
        if opt_a in yn and opt_b in yn:
            shared += 1
            if opt_a == opt_b:
                agreements += 1
    return {"agreements": agreements, "shared_events": shared}


def validate(conn, n_pairs: int = N_PAIRS, seed: int = SEED) -> list[dict]:
    """Cross-check the SQL pairwise gold against the independent Python recompute for seeded pairs.
    Returns one record per pair with both results + a match flag."""
    cur = conn.cursor()
    member_ids = _house_member_ids(conn)
    pairs = member_pairs(member_ids, n_pairs, seed)
    out: list[dict] = []
    for person_a, person_b in pairs:
        rolls_a = dict(_member_rolls(conn, person_a))
        rolls_b = dict(_member_rolls(conn, person_b))
        recomputed = recompute_pairwise(rolls_a, rolls_b)
        sql_gold = _pairwise_gold(cur, person_a, person_b)
        out.append(
            {
                "pair": (person_a, person_b),
                "recomputed": recomputed,
                "sql_gold": sql_gold,
                "match": recomputed == sql_gold,
            }
        )
    return out


def main() -> None:
    conn = get_connection()
    try:
        results = validate(conn)
    finally:
        conn.close()
    mismatches = [r for r in results if not r["match"]]
    print(f"=== lift_pairwise gold JOIN cross-check ({CONGRESS_LABEL}, READ-ONLY) ===")
    print(f"pairs checked : {len(results)} (seed={SEED})")
    if mismatches:
        print("JOIN MISMATCHES (Python recompute != SQL gold -> the pairwise join is WRONG):")
        for r in mismatches:
            print(f"   {r['pair']}: recomputed={r['recomputed']} sql={r['sql_gold']}")
    else:
        print(
            "ALL MATCH: the SQL pairwise gold equals the independent recompute -> the join logic "
            "is trustworthy (per-cast options already validated by lift_roster_spotcheck)."
        )


CONGRESS_LABEL = "118th House"


if __name__ == "__main__":
    main()
