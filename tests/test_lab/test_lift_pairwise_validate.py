"""The lift_pairwise gold join cross-check: a hermetic recompute test + a live PG cross-check."""

import pytest

from lab.experiments.lift_pairwise_validate import recompute_pairwise, validate


def test_recompute_pairwise_contract():
    # both yea -> shared + agreement; yea/nay -> shared, no agreement; a present/missing -> neither.
    rolls_a = {"e1": "yea", "e2": "yea", "e3": "nay", "e4": "present", "e5": "yea"}
    rolls_b = {"e1": "yea", "e2": "nay", "e3": "nay", "e4": "yea", "e6": "yea"}
    # shared = e1,e2,e3 (e4: a is present -> excluded; e5/e6 not shared); agreements = e1,e3
    assert recompute_pairwise(rolls_a, rolls_b) == {"agreements": 2, "shared_events": 3}


def test_recompute_pairwise_empty_and_disjoint():
    assert recompute_pairwise({}, {}) == {"agreements": 0, "shared_events": 0}
    assert recompute_pairwise({"e1": "yea"}, {"e2": "yea"}) == {"agreements": 0, "shared_events": 0}
    # not_voting is "other" -> never shared
    assert recompute_pairwise({"e1": "not_voting"}, {"e1": "yea"}) == {
        "agreements": 0,
        "shared_events": 0,
    }


@pytest.mark.requires_pg
def test_pairwise_gold_matches_recompute_live():
    """The GATE: the SQL pairwise gold must equal the independent Python recompute for every seeded
    pair, or the lift_pairwise join is wrong and must not enter a run."""
    from lab.harness import get_connection

    try:
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres unreachable: {exc}")
    try:
        results = validate(conn, n_pairs=5)
    finally:
        conn.close()
    assert results, "no pairs validated (empty member population?)"
    mismatches = [r for r in results if not r["match"]]
    assert not mismatches, f"pairwise join gold diverges from the recompute: {mismatches}"
