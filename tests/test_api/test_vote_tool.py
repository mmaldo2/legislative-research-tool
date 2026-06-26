"""Tests for the get_vote_event research tool handler.

Two layers: hermetic (mocked AsyncSession) for the error/guard paths that need no DB, and one
`requires_pg` integration test for the integrity-critical property — that the handler resolves
VOTE-TIME party via the half-open as-of join, NOT current `people.party` — proven with a switcher.
"""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from src.api.chat import _tool_get_vote_event


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


async def test_not_found_event_returns_clean_error():
    db = AsyncMock()
    db.execute.return_value = _scalar_result(None)  # header select → no event
    out = json.loads(await _tool_get_vote_event({"vote_event_id": "NX-EVENT"}, db, None))
    assert out == {"error": "Vote event 'NX-EVENT' not found."}


async def test_db_error_returns_generic_error_no_traceback_leak():
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("DataError: invalid input syntax for type ...")
    out = json.loads(await _tool_get_vote_event({"vote_event_id": "weird"}, db, None))
    assert out == {"error": "Failed to retrieve the vote event."}
    # the DB internals must not leak into what the agent (or a trace) sees
    assert "DataError" not in json.dumps(out)


@pytest.mark.requires_pg
async def test_vote_time_party_for_switcher():
    """A member whose CURRENT party (people.party) differs from their party AS OF the vote date
    must be reported by their vote-date span party. Inserts a synthetic switcher, asserts, rolls
    back (no residue). Skips when Postgres is unreachable."""
    from src.database import async_session_factory
    from src.models.person import Person
    from src.models.person_party_span import PersonPartySpan
    from src.models.vote import VoteEvent, VoteRecord

    pid = "ZZ-AGENTTEST-PERSON"
    veid = "ZZ-AGENTTEST-EVENT"

    async with async_session_factory() as db:
        try:
            await db.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 — connection failure means skip, not fail
            pytest.skip(f"Postgres unreachable: {exc}")
        bill_id = (await db.execute(text("SELECT id FROM bills LIMIT 1"))).scalar()
        if bill_id is None:
            pytest.skip("no bills in the DB to anchor a synthetic vote_event")
        try:
            db.add(Person(id=pid, name="Test Switcher", party="D"))  # CURRENT party = D
            db.add(  # vote-time party (covers 2009-03-01) = R
                PersonPartySpan(
                    person_id=pid,
                    party="R",
                    start_date=date(2009, 1, 1),
                    end_date=date(2009, 5, 1),
                )
            )
            db.add(
                VoteEvent(
                    id=veid,
                    bill_id=bill_id,
                    vote_date=date(2009, 3, 1),
                    chamber="senate",
                    motion_text="Test motion",
                    result="Passed",
                    yes_count=1,
                    no_count=0,
                    other_count=0,
                )
            )
            db.add(VoteRecord(vote_event_id=veid, person_id=pid, option="yea"))
            await db.flush()  # send INSERTs (FK-checked) WITHOUT committing
            out = json.loads(await _tool_get_vote_event({"vote_event_id": veid}, db, None))
        finally:
            await db.rollback()  # discard all synthetic rows

    assert out["yes_count"] == 1 and out["result"] == "Passed"
    recs = {r["person_id"]: r for r in out["records"]}
    assert pid in recs
    assert recs[pid]["party"] == "R", "must be VOTE-TIME party (span), not current people.party=D"
    assert recs[pid]["option"] == "yea"
    # refusal basis for vote_lookup: a member who never voted is simply absent from records
    assert "ZZ-NEVER-VOTED" not in recs
