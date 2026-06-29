"""Tests for the bill-keyed provenance tools (get_bill_votes, get_bill_cosponsors).

Two layers, mirroring test_window_tools.py: hermetic (mocked AsyncSession) for the error/guard arms
(incl. the no-DB-leak property + the bill-not-found vs real-bill-empty distinction), and one
`requires_pg` integration test per tool over real rows.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from src.api.chat import (
    _tool_get_bill_cosponsors,
    _tool_get_bill_votes,
    _tool_get_member_sponsorships,
)


def _rows(values):
    r = MagicMock()
    r.all.return_value = values
    return r


def _first(value):
    r = MagicMock()
    r.first.return_value = value
    return r


async def test_get_bill_votes_unknown_bill_returns_error():
    db = AsyncMock()
    # main query → no rows; then the existence check → absent
    db.execute.side_effect = [_rows([]), _first(None)]
    out = json.loads(await _tool_get_bill_votes({"bill_id": "NX-BILL"}, db, None))
    assert out == {"error": "Bill 'NX-BILL' not found."}


async def test_get_bill_votes_real_bill_no_rollcalls_returns_empty():
    db = AsyncMock()
    # main query → no rows; existence check → the bill IS present
    db.execute.side_effect = [_rows([]), _first(("some-bill-id",))]
    out = json.loads(await _tool_get_bill_votes({"bill_id": "some-bill-id"}, db, None))
    assert out == {"bill_id": "some-bill-id", "roll_calls": [], "count": 0}


async def test_get_bill_votes_db_error_no_traceback_leak():
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("DataError: invalid input syntax for type ...")
    out = json.loads(await _tool_get_bill_votes({"bill_id": "weird"}, db, None))
    assert out == {"error": "Failed to retrieve the bill votes."}
    assert "DataError" not in json.dumps(out)  # DB internals must not reach the agent/trace


@pytest.mark.requires_pg
async def test_get_bill_votes_against_real_bill():
    """A real bill with roll-calls returns its events ORDER BY id; a nonexistent bill errors.
    Read-only; skips if Postgres is unreachable."""
    from src.database import async_session_factory

    async with async_session_factory() as db:
        try:
            await db.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 — unreachable means skip, not fail
            pytest.skip(f"Postgres unreachable: {exc}")

        bill_id = (
            await db.execute(
                text("SELECT bill_id FROM vote_events WHERE bill_id IS NOT NULL LIMIT 1")
            )
        ).scalar()
        if bill_id is None:
            pytest.skip("no bill-linked vote events in the DB")

        out = json.loads(await _tool_get_bill_votes({"bill_id": bill_id}, db, None))
        assert out["bill_id"] == bill_id
        assert out["count"] > 0
        ids = [rc["vote_event_id"] for rc in out["roll_calls"]]
        assert ids == sorted(ids), "get_bill_votes must ORDER BY id"
        assert all(
            set(rc) == {"vote_event_id", "chamber", "vote_date", "motion_text", "result"}
            for rc in out["roll_calls"]
        )

        nf = json.loads(await _tool_get_bill_votes({"bill_id": "ZZ-NX-BILL-PROV"}, db, None))
        assert nf == {"error": "Bill 'ZZ-NX-BILL-PROV' not found."}


# --- get_bill_cosponsors (Family 2) ------------------------------------------------------------


async def test_get_bill_cosponsors_returns_person_id_and_name():
    db = AsyncMock()
    db.execute.return_value = _rows([("p1", "Rep. A"), ("p2", "Rep. B")])
    out = json.loads(await _tool_get_bill_cosponsors({"bill_id": "b1"}, db, None))
    assert out == {
        "bill_id": "b1",
        "cosponsors": [
            {"person_id": "p1", "name": "Rep. A"},
            {"person_id": "p2", "name": "Rep. B"},
        ],
        "count": 2,
    }


async def test_get_bill_cosponsors_unknown_bill_returns_error():
    db = AsyncMock()
    # cosponsor query → no rows; then the existence check → absent
    db.execute.side_effect = [_rows([]), _first(None)]
    out = json.loads(await _tool_get_bill_cosponsors({"bill_id": "NX-BILL"}, db, None))
    assert out == {"error": "Bill 'NX-BILL' not found."}


async def test_get_bill_cosponsors_real_bill_no_cosponsors_returns_empty():
    db = AsyncMock()
    # cosponsor query → no rows; existence check → the bill IS present
    db.execute.side_effect = [_rows([]), _first(("some-bill-id",))]
    out = json.loads(await _tool_get_bill_cosponsors({"bill_id": "some-bill-id"}, db, None))
    assert out == {"bill_id": "some-bill-id", "cosponsors": [], "count": 0}


async def test_get_bill_cosponsors_db_error_no_traceback_leak():
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("DataError: invalid input syntax for type ...")
    out = json.loads(await _tool_get_bill_cosponsors({"bill_id": "weird"}, db, None))
    assert out == {"error": "Failed to retrieve the bill cosponsors."}
    assert "DataError" not in json.dumps(out)  # DB internals must not reach the agent/trace


@pytest.mark.requires_pg
async def test_get_bill_cosponsors_filters_to_cosponsor_roles():
    """The tool returns the cosponsor-role members and EXCLUDES the primary sponsor; a member who
    holds BOTH a `cosponsor` and `original-cosponsor` row on the bill is returned once (DISTINCT).
    Inserts a synthetic bill + sponsorships, asserts, rolls back (no residue). Skips if PG down."""
    from src.database import async_session_factory
    from src.models.bill import Bill
    from src.models.person import Person
    from src.models.sponsorship import Sponsorship

    # Best-effort like the sibling async requires_pg tests (test_vote_tool / test_window_tools): a
    # prior async pg test binds the asyncpg pool to its now-closed loop, so this skips gracefully in
    # the full suite and runs when it's the first pg test (e.g. in isolation / a focused CI shard).
    bid = "ZZ-COSPON-BILL"
    async with async_session_factory() as db:
        try:
            await db.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 — unreachable means skip, not fail
            pytest.skip(f"Postgres unreachable: {exc}")
        juris = (await db.execute(text("SELECT id FROM jurisdictions LIMIT 1"))).scalar()
        sid = (await db.execute(text("SELECT id FROM sessions LIMIT 1"))).scalar()
        if juris is None or sid is None:
            pytest.skip("no jurisdiction/session to anchor a synthetic bill")
        try:
            db.add(
                Bill(
                    id=bid,
                    jurisdiction_id=juris,
                    session_id=sid,
                    identifier="ZZ COSPON 1",
                    title="Synthetic cosponsor test bill",
                )
            )
            db.add(Person(id="ZZ-PRIMARY", name="Rep. Primary", party="D"))
            db.add(Person(id="ZZ-CO", name="Rep. Co", party="R"))
            db.add(Person(id="ZZ-DOUBLE", name="Rep. Double", party="I"))
            db.add(Sponsorship(bill_id=bid, person_id="ZZ-PRIMARY", classification="primary"))
            db.add(Sponsorship(bill_id=bid, person_id="ZZ-CO", classification="cosponsor"))
            db.add(Sponsorship(bill_id=bid, person_id="ZZ-DOUBLE", classification="cosponsor"))
            db.add(
                Sponsorship(bill_id=bid, person_id="ZZ-DOUBLE", classification="original-cosponsor")
            )
            await db.flush()  # FK-checked INSERTs WITHOUT committing
            out = json.loads(await _tool_get_bill_cosponsors({"bill_id": bid}, db, None))
        finally:
            await db.rollback()  # discard all synthetic rows

    ids = {c["person_id"] for c in out["cosponsors"]}
    assert ids == {"ZZ-CO", "ZZ-DOUBLE"}, "primary EXCLUDED; both cosponsor roles included"
    assert out["count"] == 2, "the double-role person must be deduped (DISTINCT)"
    names = {c["person_id"]: c["name"] for c in out["cosponsors"]}
    assert names["ZZ-CO"] == "Rep. Co"


# --- get_member_sponsorships (Family 2, reverse direction) --------------------------------------


async def test_get_member_sponsorships_returns_bill_ids():
    db = AsyncMock()
    db.execute.return_value = _rows([("b1",), ("b2",)])
    out = json.loads(
        await _tool_get_member_sponsorships({"person_id": "p1", "congress": "110"}, db, None)
    )
    assert out == {
        "person_id": "p1",
        "congress": "110",
        "bills": [{"bill_id": "b1"}, {"bill_id": "b2"}],
        "count": 2,
    }


async def test_get_member_sponsorships_unknown_person_returns_error():
    db = AsyncMock()
    # primary query → no rows; then the existence check → absent
    db.execute.side_effect = [_rows([]), _first(None)]
    out = json.loads(
        await _tool_get_member_sponsorships({"person_id": "NX-PERSON", "congress": "110"}, db, None)
    )
    assert out == {"error": "Person 'NX-PERSON' not found."}


async def test_get_member_sponsorships_real_member_no_primary_bills_returns_empty():
    db = AsyncMock()
    # primary query → no rows; existence check → the person IS present (empty-list answer, no error)
    db.execute.side_effect = [_rows([]), _first(("p1",))]
    out = json.loads(
        await _tool_get_member_sponsorships({"person_id": "p1", "congress": "110"}, db, None)
    )
    assert out == {"person_id": "p1", "congress": "110", "bills": [], "count": 0}


async def test_get_member_sponsorships_db_error_no_traceback_leak():
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("DataError: invalid input syntax for type ...")
    out = json.loads(
        await _tool_get_member_sponsorships({"person_id": "weird", "congress": "110"}, db, None)
    )
    assert out == {"error": "Failed to retrieve the member sponsorships."}
    assert "DataError" not in json.dumps(out)  # DB internals must not reach the agent/trace


@pytest.mark.requires_pg
async def test_get_member_sponsorships_filters_to_primary_role_and_congress():
    """The tool returns the member's PRIMARY-sponsored bills and EXCLUDES bills where they only
    cosponsor; it scopes to the requested congress (a different congress → empty); a nonexistent
    person errors. Inserts a synthetic session/bills/sponsorships, asserts, rolls back. Skips if
    PG down."""
    from src.database import async_session_factory
    from src.models.bill import Bill
    from src.models.person import Person
    from src.models.sponsorship import Sponsorship

    # Best-effort like the sibling async requires_pg tests: a prior async pg test binds the asyncpg
    # pool to its now-closed loop, so this skips gracefully in the full suite and runs when it's the
    # first pg test (isolation / a focused CI shard).
    async with async_session_factory() as db:
        try:
            await db.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 — unreachable means skip, not fail
            pytest.skip(f"Postgres unreachable: {exc}")
        juris = (await db.execute(text("SELECT id FROM jurisdictions LIMIT 1"))).scalar()
        row = (await db.execute(text("SELECT id, identifier FROM sessions LIMIT 1"))).first()
        if juris is None or row is None:
            pytest.skip("no jurisdiction/session to anchor synthetic bills")
        sid, cong = row
        led, cosponsored = "ZZ-MS-LED", "ZZ-MS-COSPON"
        try:
            db.add(
                Bill(
                    id=led,
                    jurisdiction_id=juris,
                    session_id=sid,
                    identifier="ZZ MS LED 1",
                    title="Synthetic primary-sponsored bill",
                )
            )
            db.add(
                Bill(
                    id=cosponsored,
                    jurisdiction_id=juris,
                    session_id=sid,
                    identifier="ZZ MS COSPON 1",
                    title="Synthetic cosponsored-only bill",
                )
            )
            db.add(Person(id="ZZ-MEMBER", name="Rep. Member", party="D"))
            # primary on `led`; only a cosponsor on `cosponsored` → `cosponsored` must be EXCLUDED.
            db.add(Sponsorship(bill_id=led, person_id="ZZ-MEMBER", classification="primary"))
            db.add(
                Sponsorship(bill_id=cosponsored, person_id="ZZ-MEMBER", classification="cosponsor")
            )
            await db.flush()  # FK-checked INSERTs WITHOUT committing

            out = json.loads(
                await _tool_get_member_sponsorships(
                    {"person_id": "ZZ-MEMBER", "congress": cong}, db, None
                )
            )
            # a different congress for a real member → empty list (not an error)
            other = json.loads(
                await _tool_get_member_sponsorships(
                    {"person_id": "ZZ-MEMBER", "congress": "ZZ-NOPE-CONG"}, db, None
                )
            )
            # a nonexistent person → clean not-found error
            nf = json.loads(
                await _tool_get_member_sponsorships(
                    {"person_id": "ZZ-NX-PERSON", "congress": cong}, db, None
                )
            )
        finally:
            await db.rollback()  # discard all synthetic rows

    assert out["bills"] == [{"bill_id": led}], (
        "only the PRIMARY-sponsored bill; cosponsored EXCLUDED"
    )
    assert out["count"] == 1
    assert other == {"person_id": "ZZ-MEMBER", "congress": "ZZ-NOPE-CONG", "bills": [], "count": 0}
    assert nf == {"error": "Person 'ZZ-NX-PERSON' not found."}
