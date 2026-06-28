"""family2.cosponsored_and_voted_against -- the integrity properties with no analog elsewhere.

Hermetic: the `_stratified_bills` floor-of-each sampling (balanced split + deterministic fill).
`requires_pg`: the gold predicate (each gold member cosponsored the bill AND voted nay on its single
roll call), the kind<->gold-emptiness binding, the two refusal twins (nonexistent bill; real bill
with cosponsors but NO roll call -> REFUSE, not empty), the deterministic invariants, and the gold
subset-of get_bill_cosponsors (the OURS tool is a faithful superset of gold -- closes the two-layer
"cosponsored"-literal drift seam). plain `def` for the sync (psycopg2) checks; one async test for
the tool superset (best-effort skip like the sibling async pg tests)."""

import json

import pytest

from lab.graders import REFUSAL, grade
from lab.solvers import OverRefuseSolver, SqlOracleSolver, WrongBaselineSolver
from lab.templates import (
    _COSPONSOR_ROLES,
    TEMPLATE_COSPONSOR_VOTE,
    _stratified_bills,
    generate_cosponsored_and_voted_against,
)


class TestStratifiedBills:
    def test_balanced_split_when_both_pools_ample(self):
        hd = [f"d{i}" for i in range(20)]
        cl = [f"c{i}" for i in range(20)]
        picks = _stratified_bills(hd, cl, 10, seed=42)
        kinds = [k for _b, k in picks]
        assert len(picks) == 10
        assert kinds.count("has_defectors") == 5 and kinds.count("clean") == 5
        assert all((b in hd) == (k == "has_defectors") for b, k in picks)  # kind matches the pool

    def test_fills_from_clean_when_has_defectors_short(self):
        # only 2 defector bills; n=10 -> 2 has_defectors + 8 clean (the deficit fills from clean).
        hd = ["d0", "d1"]
        cl = [f"c{i}" for i in range(20)]
        picks = _stratified_bills(hd, cl, 10, seed=42)
        kinds = [k for _b, k in picks]
        assert len(picks) == 10
        assert kinds.count("has_defectors") == 2 and kinds.count("clean") == 8
        assert len({b for b, _k in picks}) == 10  # no duplicates

    def test_deterministic_and_pool_short(self):
        hd, cl = ["d0", "d1", "d2"], ["c0", "c1"]
        assert _stratified_bills(hd, cl, 10, 42) == _stratified_bills(hd, cl, 10, 42)
        assert len(_stratified_bills(hd, cl, 10, 42)) == 5  # capped at the candidate count
        assert _stratified_bills([], [], 4, 42) == []


def _conn():
    from lab.harness import get_connection

    try:
        return get_connection()
    except Exception as exc:  # noqa: BLE001 -- unreachable means skip, not fail
        pytest.skip(f"Postgres unreachable: {exc}")


def _gen(n=10):
    from lab.precompute import precompute

    conn = _conn()
    try:
        return generate_cosponsored_and_voted_against(conn, n, 42, precompute(conn)), conn
    except Exception:
        conn.close()
        raise


@pytest.mark.requires_pg
def test_gold_predicate_and_kinds():
    insts, conn = _gen()
    try:
        answerable = [i for i in insts if not i.is_refusal]
        assert answerable, "no answerable cosponsor-vote instances generated"
        assert {i.params["kind"] for i in answerable} == {"has_defectors", "clean"}, (
            "both kinds must be sampled (the stratification)"
        )
        cur = conn.cursor()
        roles = "(" + ",".join(["%s"] * len(_COSPONSOR_ROLES)) + ")"
        for i in answerable:
            assert i.template_id == TEMPLATE_COSPONSOR_VOTE and i.grader == "set_match"
            bid, eid = i.params["bill_id"], i.params["vote_event_id"]
            # the bill has EXACTLY ONE roll call, and it is the prompted eid
            cur.execute("SELECT COUNT(*) FROM vote_events WHERE bill_id = %s", (bid,))
            assert cur.fetchone()[0] == 1, "answerable bill must be single-roll-call"
            # kind <-> gold-emptiness binding
            assert (len(i.gold) > 0) == (i.params["kind"] == "has_defectors")
            for pid in i.gold:
                # each gold member cosponsored the bill (a cosponsor role, NOT primary) ...
                cur.execute(
                    f"SELECT COUNT(*) FROM sponsorships WHERE bill_id = %s AND person_id = %s "
                    f"AND classification IN {roles}",
                    (bid, pid, *_COSPONSOR_ROLES),
                )
                assert cur.fetchone()[0] >= 1, f"{pid} is not a cosponsor of {bid}"
                # ... AND voted nay on the single roll call
                cur.execute(
                    'SELECT "option" FROM vote_records WHERE vote_event_id = %s AND person_id = %s',
                    (eid, pid),
                )
                row = cur.fetchone()
                assert row is not None and row[0] == "nay", f"{pid} did not vote nay on {eid}"
            # leak-safe: the prompt names the bill + motion, never a gold member id
            assert all(str(pid) not in i.prompt for pid in i.gold)
    finally:
        conn.close()


@pytest.mark.requires_pg
def test_refusal_twins_are_airtight():
    insts, conn = _gen()
    try:
        cur = conn.cursor()
        nobill = [i for i in insts if i.refusal_reason == "bill_not_in_data"]
        novote = [i for i in insts if i.refusal_reason == "bill_has_no_rollcall"]
        assert nobill and novote, "both refusal twins must be generated"
        for i in nobill + novote:
            assert i.gold == REFUSAL and i.grader == "refusal_correct" and i.is_refusal
        for i in nobill:  # Twin A: the bill truly does not exist
            cur.execute("SELECT COUNT(*) FROM bills WHERE id = %s", (i.params["bill_id"],))
            assert cur.fetchone()[0] == 0, "twin-A bill must be absent"
        for i in novote:  # Twin B: real bill, >=1 cosponsor, ZERO roll calls
            bid = i.params["bill_id"]
            cur.execute("SELECT COUNT(*) FROM bills WHERE id = %s", (bid,))
            assert cur.fetchone()[0] == 1, "twin-B bill must exist"
            cur.execute("SELECT COUNT(*) FROM vote_events WHERE bill_id = %s", (bid,))
            assert cur.fetchone()[0] == 0, "twin-B bill must have NO roll call (no-vote != [])"
            cur.execute(
                "SELECT COUNT(*) FROM sponsorships WHERE bill_id = %s "
                "AND classification IN ('cosponsor', 'original-cosponsor')",
                (bid,),
            )
            assert cur.fetchone()[0] >= 1, "twin-B bill must have >=1 cosponsor"
    finally:
        conn.close()


@pytest.mark.requires_pg
def test_deterministic_invariants():
    insts, conn = _gen()
    conn.close()
    oracle, wrong, refuse = SqlOracleSolver(), WrongBaselineSolver(), OverRefuseSolver()
    answerable = [i for i in insts if not i.is_refusal]
    for i in insts:
        assert grade(i.grader, i.gold, oracle.solve(i), is_refusal=i.is_refusal).passed
        assert not grade(i.grader, i.gold, wrong.solve(i), is_refusal=i.is_refusal).passed
    for i in answerable:  # over-refusing an answerable item (incl. [] gold) must FAIL
        assert not grade(i.grader, i.gold, refuse.solve(i), is_refusal=i.is_refusal).passed


@pytest.mark.requires_pg
async def test_gold_is_subset_of_tool_cosponsors():
    """The OURS-arm tool must be a faithful SUPERSET of gold: the "cosponsored" filter is duplicated
    in the gold SQL (templates.py) and the tool (chat.py) -- this catches drift. Async (calls the
    real tool); best-effort skip like the sibling async pg tests."""
    insts, conn = _gen()
    conn.close()
    answerable = [i for i in insts if not i.is_refusal]
    from sqlalchemy import text

    from src.api.chat import _tool_get_bill_cosponsors
    from src.database import async_session_factory

    async with async_session_factory() as db:
        try:
            await db.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 -- unreachable / cross-loop means skip
            pytest.skip(f"Postgres unreachable: {exc}")
        for i in answerable:
            out = json.loads(
                await _tool_get_bill_cosponsors({"bill_id": i.params["bill_id"]}, db, None)
            )
            tool_ids = {c["person_id"] for c in out["cosponsors"]}
            assert set(i.gold) <= tool_ids, f"gold exceeds tool cosponsors: {i.params['bill_id']}"
