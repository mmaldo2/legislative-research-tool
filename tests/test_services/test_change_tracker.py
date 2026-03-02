"""Tests for the change tracker service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.change_tracker import (
    TRACKED_FIELDS,
    _serialize,
    get_existing_bill,
    track_bill_changes,
)


class TestSerialize:
    def test_none(self):
        assert _serialize(None) is None

    def test_string(self):
        assert _serialize("hello") == "hello"

    def test_integer(self):
        assert _serialize(42) == "42"

    def test_list_sorted(self):
        assert _serialize(["b", "a", "c"]) == "a,b,c"

    def test_empty_list(self):
        assert _serialize([]) == ""

    def test_single_item_list(self):
        assert _serialize(["only"]) == "only"


class TestGetExistingBill:
    @pytest.mark.asyncio
    async def test_returns_none_when_bill_not_found(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        values = await get_existing_bill(session, "us-119-hr1")
        assert values is None

    @pytest.mark.asyncio
    async def test_returns_serialized_fields(self):
        mock_bill = MagicMock()
        mock_bill.title = "Some Title"
        mock_bill.status = "introduced"
        mock_bill.status_date = None
        mock_bill.subject = ["Tax", "Budget"]

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_bill
        session.execute.return_value = result

        values = await get_existing_bill(session, "us-119-hr1")
        assert values is not None
        assert values["title"] == "Some Title"
        assert values["status"] == "introduced"
        assert values["status_date"] is None
        assert values["subject"] == "Budget,Tax"  # sorted


class TestTrackBillChanges:
    @pytest.mark.asyncio
    async def test_new_bill_emits_created_event(self):
        session = AsyncMock()

        changes = await track_bill_changes(
            session, "us-119-hr1", old_values=None, new_values={"title": "Test"}
        )

        assert len(changes) == 1
        assert changes[0].change_type == "created"
        assert changes[0].bill_id == "us-119-hr1"
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_changes_emits_nothing(self):
        session = AsyncMock()
        old = {"title": "Test", "status": "introduced", "status_date": None, "subject": None}
        new = {"title": "Test", "status": "introduced", "status_date": None, "subject": None}

        changes = await track_bill_changes(session, "us-119-hr1", old, new)
        assert len(changes) == 0
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_title_change_emits_updated(self):
        session = AsyncMock()
        old = {"title": "Old Title", "status": "introduced", "status_date": None, "subject": None}
        new = {"title": "New Title", "status": "introduced"}

        changes = await track_bill_changes(session, "us-119-hr1", old, new)
        assert len(changes) == 1
        assert changes[0].change_type == "updated"
        assert changes[0].field_name == "title"
        assert changes[0].old_value == "Old Title"
        assert changes[0].new_value == "New Title"

    @pytest.mark.asyncio
    async def test_status_change_emits_status_changed(self):
        session = AsyncMock()
        old = {"title": "Test", "status": "introduced", "status_date": None, "subject": None}
        new = {"title": "Test", "status": "enacted"}

        changes = await track_bill_changes(session, "us-119-hr1", old, new)
        assert len(changes) == 1
        assert changes[0].change_type == "status_changed"
        assert changes[0].field_name == "status"

    @pytest.mark.asyncio
    async def test_multiple_changes(self):
        session = AsyncMock()
        old = {"title": "Old", "status": "introduced", "status_date": None, "subject": None}
        new = {"title": "New", "status": "enacted"}

        changes = await track_bill_changes(session, "us-119-hr1", old, new)
        assert len(changes) == 2
        types = {c.change_type for c in changes}
        assert "updated" in types
        assert "status_changed" in types

    @pytest.mark.asyncio
    async def test_ingestion_run_id_propagated(self):
        session = AsyncMock()
        changes = await track_bill_changes(
            session, "us-119-hr1", old_values=None, new_values={}, ingestion_run_id=42
        )
        assert changes[0].ingestion_run_id == 42

    @pytest.mark.asyncio
    async def test_subject_list_change_detected(self):
        session = AsyncMock()
        old = {"title": "Test", "status": "introduced", "status_date": None, "subject": "A,B"}
        new = {"title": "Test", "status": "introduced", "subject": ["A", "B", "C"]}

        changes = await track_bill_changes(session, "bill-1", old, new)
        assert len(changes) == 1
        assert changes[0].field_name == "subject"
        assert changes[0].new_value == "A,B,C"


class TestTrackedFields:
    def test_expected_fields(self):
        assert "title" in TRACKED_FIELDS
        assert "status" in TRACKED_FIELDS
        assert "status_date" in TRACKED_FIELDS
        assert "subject" in TRACKED_FIELDS
