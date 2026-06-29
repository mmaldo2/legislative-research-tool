"""family6.covoting_disagreement -- the integrity properties with no analog elsewhere.

Hermetic: the `_same_party_pair_keys` pair builder (party/floor filter, canonical
same-chamber-same-party dedup, no self-pair, input-order-independent determinism).
`requires_pg`: the gold predicate (each gold eid = both cast yea/nay AND differ), the
`(vote_event_id, person_id)` uniqueness linchpin, the twins (cross-body -> answerable EMPTY set;
nonexistent name -> REFUSE), the deterministic invariants, and the gold == two-tool differ-set drift
guard. plain `def` for the sync (psycopg2) checks; one async test for the tool equality (best-effort
skip like the sibling async pg tests).
"""

import json

import pytest

from lab.graders import REFUSAL, grade
from lab.solvers import OverRefuseSolver, SqlOracleSolver, WrongBaselineSolver
from lab.templates import (
    _COVOTING_ACTIVE_FLOOR,
    TEMPLATE_COVOTING,
    _same_party_pair_keys,
    generate_covoting_disagreement,
)


class TestSamePartyPairKeys:
    def test_filters_party_and_floor_pairs_within_chamber_party(self):
        floor = _COVOTING_ACTIVE_FLOOR
        rows = [
            ("A", "D", "house", floor),  # active D house
            ("B", "D", "house", floor + 5),  # active D house -> pairs with A
            ("C", "R", "house", floor),  # active R house (lone R -> no same-party partner)
            ("D", "D", "house", floor - 1),  # below the floor -> excluded
            ("E", "I", "house", floor + 10),  # not D/R -> excluded
            ("F", "D", "senate", floor),  # D senate
            (
                "G",
                "D",
                "senate",
                floor + 1,
            ),  # D senate -> pairs with F (different chamber from A/B)
        ]
        # only A-B (house D) and F-G (senate D); cross-party (C) and cross-chamber pairs never form.
        assert _same_party_pair_keys(rows) == ["house|A|B", "senate|F|G"]

    def test_canonical_sorted_no_self_pair(self):
        floor = _COVOTING_ACTIVE_FLOOR
        rows = [
            ("A", "D", "house", floor),
            ("B", "D", "house", floor),
            ("C", "D", "house", floor),
        ]
        keys = _same_party_pair_keys(rows)
        assert keys == [
            "house|A|B",
            "house|A|C",
            "house|B|C",
        ]  # canonical a<b, sorted, no self-pair
        assert all(len(k.split("|")) == 3 for k in keys)

    def test_input_order_independent(self):
        floor = _COVOTING_ACTIVE_FLOOR
        rows = [
            ("B", "D", "house", floor),
            ("A", "D", "house", floor),
            ("C", "D", "senate", floor),
            ("D", "D", "senate", floor),
        ]
        assert _same_party_pair_keys(rows) == _same_party_pair_keys(list(reversed(rows)))
        assert _same_party_pair_keys(rows) == ["house|A|B", "senate|C|D"]

    def test_empty_and_singletons(self):
        floor = _COVOTING_ACTIVE_FLOOR
        assert _same_party_pair_keys([]) == []
        # a single member per (chamber, party) group yields no pair
        assert _same_party_pair_keys([("A", "D", "house", floor), ("B", "R", "house", floor)]) == []


def _conn():
    from lab.harness import get_connection

    try:
        return get_connection()
    except Exception as exc:  # noqa: BLE001 -- unreachable means skip, not fail
        pytest.skip(f"Postgres unreachable: {exc}")


def _gen(n=12):
    from lab.precompute import Precomputed

    conn = _conn()
    try:
        # the generator ignores `precomputed`; pass an empty one to skip the 5.4M-row scan.
        return generate_covoting_disagreement(conn, n, 42, Precomputed()), conn
    except Exception:
        conn.close()
        raise


@pytest.mark.requires_pg
def test_gold_predicate_same_party_and_leak_safe():
    insts, conn = _gen()
    try:
        # the natural same-party pairs (the crossbody-empty kind is checked separately below).
        answerable = [i for i in insts if i.params.get("kind") == "answerable"]
        assert answerable, "no answerable covoting instances generated"
        cur = conn.cursor()
        for i in answerable:
            assert i.template_id == TEMPLATE_COVOTING and i.grader == "set_match"
            a, b, chamber = i.params["person_a"], i.params["person_b"], i.params["chamber"]
            assert a != b
            # the pair is SAME party (the selection invariant)
            cur.execute("SELECT party FROM people WHERE id IN (%s, %s)", (a, b))
            parties = {r[0] for r in cur.fetchall()}
            assert len(parties) == 1 and parties <= {"D", "R"}, f"{a},{b} not same D/R party"
            # each gold eid: BOTH members cast yea/nay on it in (chamber) AND their options differ
            for eid in i.gold:
                cur.execute(
                    'SELECT vr.person_id, vr."option" FROM vote_records vr '
                    "JOIN vote_events ve ON ve.id = vr.vote_event_id "
                    "WHERE vr.vote_event_id = %s AND vr.person_id IN (%s, %s) AND ve.chamber = %s",
                    (eid, a, b, chamber),
                )
                opts = dict(cur.fetchall())
                assert set(opts) == {a, b}, f"{eid}: both members not present"
                assert opts[a] in ("yea", "nay") and opts[b] in ("yea", "nay")
                assert opts[a] != opts[b], f"{eid}: not a disagreement"
            # leak-safe: the prompt names the two members, never a gold vote_event_id
            assert all(str(eid) not in i.prompt for eid in i.gold)
    finally:
        conn.close()


@pytest.mark.requires_pg
def test_vote_records_pair_uniqueness():
    """The no-gate claim + the drift-guard equality both rest on (vote_event_id, person_id) being
    unique (model-declared + ingestion-proven, but not migration-verified). Assert it directly."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT vote_event_id, person_id FROM vote_records "
            "GROUP BY vote_event_id, person_id HAVING COUNT(*) > 1 LIMIT 1"
        )
        assert cur.fetchone() is None, "(vote_event_id, person_id) not unique -> gold is ambiguous"
    finally:
        conn.close()


@pytest.mark.requires_pg
def test_twins_crossbody_empty_and_nonexistent_refusal():
    insts, conn = _gen()
    try:
        cur = conn.cursor()
        crossbody = [i for i in insts if i.params.get("kind") == "crossbody_empty"]
        noname = [i for i in insts if i.refusal_reason == "member_not_in_data"]
        assert crossbody and noname, "crossbody-empty and nonexistent-name twins must be generated"
        # Twin A is ANSWERABLE-EMPTY (gold=set()), not a refusal: House member + real Senator asked
        # about HOUSE votes share zero roll calls. Proof: the senator has 0 (119,house) records.
        for i in crossbody:
            assert i.gold == set() and i.grader == "set_match" and not i.is_refusal
            cur.execute(
                "SELECT 1 FROM vote_records vr JOIN vote_events ve ON ve.id = vr.vote_event_id "
                "JOIN bills b ON b.id = ve.bill_id JOIN sessions s ON s.id = b.session_id "
                "WHERE vr.person_id = %s AND s.identifier = '119' AND ve.chamber = 'house' LIMIT 1",
                (i.params["person_b"],),
            )
            assert cur.fetchone() is None, (
                f"crossbody senator {i.params['person_b']} has a house record"
            )
        # Twin B is a genuine REFUSAL: the synthetic name (person_b) matches no person at all.
        for i in noname:
            assert i.gold == REFUSAL and i.grader == "refusal_correct" and i.is_refusal
            token = i.params["person_b"]
            cur.execute(
                "SELECT 1 FROM people WHERE LOWER(name) LIKE %s LIMIT 1", (f"%{token.lower()}%",)
            )
            assert cur.fetchone() is None, f"twin name {token} matches a real person"
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
async def test_gold_equals_two_tool_diff():
    """gold == the differ-set computed from two REAL get_member_voting_record calls (both yea/nay,
    options differ). Equality (not subset): gold SQL and the tool read the SAME vote_records. Async;
    best-effort skip on DB-down, but FAIL if the tool errors for an active member (real drift)."""
    insts, conn = _gen()
    conn.close()
    # only the natural same-party pairs: the crossbody-empty member is not in the prompted chamber,
    # so the tool would (correctly) error for it -- gold=set() is proven by the twin test instead.
    answerable = [i for i in insts if i.params.get("kind") == "answerable"]
    from sqlalchemy import text

    from src.api.chat import _tool_get_member_voting_record
    from src.database import async_session_factory

    async with async_session_factory() as db:
        try:
            await db.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 -- unreachable / cross-loop means skip
            pytest.skip(f"Postgres unreachable: {exc}")
        for i in answerable:
            a, b, chamber = i.params["person_a"], i.params["person_b"], i.params["chamber"]
            ra = json.loads(
                await _tool_get_member_voting_record(
                    {"person_id": a, "congress": "119", "chamber": chamber}, db, None
                )
            )
            rb = json.loads(
                await _tool_get_member_voting_record(
                    {"person_id": b, "congress": "119", "chamber": chamber}, db, None
                )
            )
            assert "records" in ra and "records" in rb, (
                f"tool errored for an active member ({a}/{b})"
            )
            opt_a = {r["vote_event_id"]: r["option"] for r in ra["records"]}
            opt_b = {r["vote_event_id"]: r["option"] for r in rb["records"]}
            diff = {
                eid
                for eid in (opt_a.keys() & opt_b.keys())
                if opt_a[eid] in ("yea", "nay")
                and opt_b[eid] in ("yea", "nay")
                and opt_a[eid] != opt_b[eid]
            }
            assert diff == set(i.gold), f"gold != two-tool differ-set for {a}/{b}"
