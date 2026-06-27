"""Tests for the Family 1 Phase B window tools (list_vote_events, find_people,
get_member_voting_record).

Two layers, mirroring test_vote_tool.py: hermetic (mocked AsyncSession) for the error/guard arms
(incl. the P16 no-DB-leak property), and one `requires_pg` integration test over a real
(congress, chamber) window that exercises all three tools + the refusal arms.
"""

import json
import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from src.api.chat import (
    _tool_find_people,
    _tool_get_member_voting_record,
    _tool_list_vote_events,
)


def _rows(values):
    r = MagicMock()
    r.all.return_value = values
    return r


def _first(value):
    r = MagicMock()
    r.first.return_value = value
    return r


# --- list_vote_events -------------------------------------------------------------------------


async def test_list_vote_events_unknown_congress_returns_error():
    db = AsyncMock()
    # main query → no rows; then the existence check → absent
    db.execute.side_effect = [_rows([]), _first(None)]
    out = json.loads(
        await _tool_list_vote_events({"congress": "999", "chamber": "house"}, db, None)
    )
    assert out == {"error": "Congress '999' not found."}


async def test_list_vote_events_db_error_no_traceback_leak():
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("DataError: invalid input syntax for type ...")
    out = json.loads(await _tool_list_vote_events({"congress": "x", "chamber": "house"}, db, None))
    assert out == {"error": "Failed to list vote events."}
    assert "DataError" not in json.dumps(out)  # DB internals must not reach the agent/trace


# --- find_people ------------------------------------------------------------------------------


async def test_find_people_no_match_returns_empty_list():
    db = AsyncMock()
    db.execute.return_value = _rows([])  # no name candidates
    out = json.loads(
        await _tool_find_people({"name": "Nobody", "congress": "115", "chamber": "house"}, db, None)
    )
    assert out == {"people": [], "count": 0}


async def test_find_people_db_error_no_traceback_leak():
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("ProgrammingError: relation does not exist")
    out = json.loads(
        await _tool_find_people({"name": "X", "congress": "115", "chamber": "house"}, db, None)
    )
    assert out == {"error": "Failed to find people."}
    assert "ProgrammingError" not in json.dumps(out)


async def test_find_people_non_name_query_returns_empty_without_db():
    # a bioguide id (no alphabetic tokens after the digits) must not match anyone — and must not
    # build a wildcard-less LIKE that matches EVERYONE; early-return before touching the DB.
    db = AsyncMock()
    out = json.loads(
        await _tool_find_people(
            {"name": "000303", "congress": "117", "chamber": "senate"}, db, None
        )
    )
    assert out == {"people": [], "count": 0}
    db.execute.assert_not_called()


# --- get_member_voting_record -----------------------------------------------------------------


async def test_member_record_not_found_returns_error():
    db = AsyncMock()
    db.execute.return_value = _rows([])  # 0 records in the window
    out = json.loads(
        await _tool_get_member_voting_record(
            {"person_id": "NX", "congress": "115", "chamber": "house"}, db, None
        )
    )
    assert out == {"error": "Member 'NX' not found in house Congress 115."}


async def test_member_record_db_error_no_traceback_leak():
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("DataError: bad bind")
    out = json.loads(
        await _tool_get_member_voting_record(
            {"person_id": "p1", "congress": "115", "chamber": "house"}, db, None
        )
    )
    assert out == {"error": "Failed to retrieve the member voting record."}
    assert "DataError" not in json.dumps(out)


# --- integration: a real (congress, chamber) window -------------------------------------------


@pytest.mark.requires_pg
async def test_window_tools_against_real_window():
    """All three tools over a real completed (congress, chamber): list returns rankable events
    ORDER BY id, find_people resolves a real member's name → id, get_member_voting_record returns
    that member's raw options, and the two refusal arms fire. Read-only; skips if PG unreachable."""
    from src.database import async_session_factory

    async with async_session_factory() as db:
        try:
            await db.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 — unreachable means skip, not fail
            pytest.skip(f"Postgres unreachable: {exc}")

        window = (
            await db.execute(
                text(
                    "SELECT s.identifier, ve.chamber FROM vote_events ve "
                    "JOIN bills b ON b.id = ve.bill_id JOIN sessions s ON s.id = b.session_id "
                    "WHERE ve.yes_count IS NOT NULL AND ve.no_count IS NOT NULL "
                    "AND s.end_date IS NOT NULL LIMIT 1"
                )
            )
        ).first()
        if window is None:
            pytest.skip("no rankable vote events in a completed congress")
        congress, chamber = window

        lve = json.loads(
            await _tool_list_vote_events({"congress": congress, "chamber": chamber}, db, None)
        )
        assert lve["count"] > 0
        ids = [e["vote_event_id"] for e in lve["events"]]
        assert ids == sorted(ids), "list_vote_events must ORDER BY id"
        assert all(
            e["yes_count"] is not None and e["no_count"] is not None for e in lve["events"]
        ), "NULL-tally events must be omitted (rankable-set parity with gold)"

        member = (
            await db.execute(
                text(
                    "SELECT vr.person_id, p.name FROM vote_records vr "
                    "JOIN people p ON p.id = vr.person_id "
                    "JOIN vote_events ve ON ve.id = vr.vote_event_id "
                    "JOIN bills b ON b.id = ve.bill_id JOIN sessions s ON s.id = b.session_id "
                    "WHERE s.identifier = :c AND ve.chamber = :ch LIMIT 1"
                ),
                {"c": congress, "ch": chamber},
            )
        ).first()
        pid, pname = member

        fp = json.loads(
            await _tool_find_people(
                {"name": pname, "congress": congress, "chamber": chamber}, db, None
            )
        )
        assert pid in {p["person_id"] for p in fp["people"]}, "find_people must resolve name → id"

        # the bug this fixes: an agent passes the NATURAL name, not the stored 'Sen. Last, First
        # [P-ST]' string. Strip the title + bracket and assert the token-match still resolves.
        core = re.sub(r"\[.*?\]", " ", pname)
        core = re.sub(r"^\s*\w+\.\s+", " ", core).strip()
        natural = json.loads(
            await _tool_find_people(
                {"name": core, "congress": congress, "chamber": chamber}, db, None
            )
        )
        assert pid in {p["person_id"] for p in natural["people"]}, "natural name must token-match"

        gmr = json.loads(
            await _tool_get_member_voting_record(
                {"person_id": pid, "congress": congress, "chamber": chamber}, db, None
            )
        )
        assert gmr["count"] > 0
        rec_ids = [r["vote_event_id"] for r in gmr["records"]]
        assert rec_ids == sorted(rec_ids), "get_member_voting_record must ORDER BY vote_event_id"
        assert all(r["option"] in ("yea", "nay", "present", "not_voting") for r in gmr["records"])

        # refusal arms
        nf = json.loads(
            await _tool_get_member_voting_record(
                {"person_id": "ZZ-NX-PERSON", "congress": congress, "chamber": chamber}, db, None
            )
        )
        assert "error" in nf
        nc = json.loads(
            await _tool_list_vote_events(
                {"congress": "ZZ-NX-CONGRESS", "chamber": chamber}, db, None
            )
        )
        assert nc == {"error": "Congress 'ZZ-NX-CONGRESS' not found."}
