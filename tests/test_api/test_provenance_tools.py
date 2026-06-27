"""Tests for the Family 10 provenance tool (get_bill_votes).

Two layers, mirroring test_window_tools.py: hermetic (mocked AsyncSession) for the error/guard arms
(incl. the no-DB-leak property + the bill-not-found vs real-bill-no-roll-calls distinction), and one
`requires_pg` integration test over a real bill.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from src.api.chat import _tool_get_bill_votes


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
