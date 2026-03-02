"""Tests for the alert evaluator service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.alert_evaluator import (
    CHANGE_TYPE_TO_EVENT,
    _build_payload,
    _matches_criteria,
    evaluate_alerts_for_changes,
)


class TestMatchesCriteria:
    def _make_bill(self, **kwargs):
        bill = MagicMock()
        bill.jurisdiction_id = kwargs.get("jurisdiction_id", "us")
        bill.status = kwargs.get("status", "introduced")
        bill.title = kwargs.get("title", "Test Bill")
        return bill

    def test_empty_criteria_matches_everything(self):
        bill = self._make_bill()
        assert _matches_criteria(bill, {}) is True

    def test_jurisdiction_filter_match(self):
        bill = self._make_bill(jurisdiction_id="us-ca")
        assert _matches_criteria(bill, {"jurisdiction_id": "us-ca"}) is True

    def test_jurisdiction_filter_mismatch(self):
        bill = self._make_bill(jurisdiction_id="us-ca")
        assert _matches_criteria(bill, {"jurisdiction_id": "us-tx"}) is False

    def test_status_filter_match(self):
        bill = self._make_bill(status="enacted")
        assert _matches_criteria(bill, {"status": "enacted"}) is True

    def test_status_filter_mismatch(self):
        bill = self._make_bill(status="introduced")
        assert _matches_criteria(bill, {"status": "enacted"}) is False

    def test_keyword_filter_match_case_insensitive(self):
        bill = self._make_bill(title="Consumer Data Privacy Act")
        assert _matches_criteria(bill, {"query": "privacy"}) is True
        assert _matches_criteria(bill, {"query": "PRIVACY"}) is True

    def test_keyword_filter_mismatch(self):
        bill = self._make_bill(title="Infrastructure Bill")
        assert _matches_criteria(bill, {"query": "privacy"}) is False

    def test_combined_filters_all_match(self):
        bill = self._make_bill(jurisdiction_id="us", status="introduced", title="Tax Reform Act")
        criteria = {
            "jurisdiction_id": "us",
            "status": "introduced",
            "query": "tax",
        }
        assert _matches_criteria(bill, criteria) is True

    def test_combined_filters_one_fails(self):
        bill = self._make_bill(jurisdiction_id="us", status="introduced", title="Tax Reform Act")
        criteria = {
            "jurisdiction_id": "us",
            "status": "enacted",  # mismatch
            "query": "tax",
        }
        assert _matches_criteria(bill, criteria) is False

    def test_none_title_handled(self):
        bill = self._make_bill(title=None)
        assert _matches_criteria(bill, {"query": "anything"}) is False


class TestBuildPayload:
    def test_payload_structure(self):
        event = MagicMock()
        event.change_type = "status_changed"
        event.field_name = "status"
        event.old_value = "introduced"
        event.new_value = "enacted"

        bill = MagicMock()
        bill.id = "us-119-hr1"
        bill.identifier = "HR 1"
        bill.jurisdiction_id = "us"
        bill.title = "Test Bill"

        payload = _build_payload(event, bill, "bill.status_changed")

        assert payload["event_type"] == "bill.status_changed"
        assert payload["bill_id"] == "us-119-hr1"
        assert payload["identifier"] == "HR 1"
        assert payload["jurisdiction_id"] == "us"
        assert payload["title"] == "Test Bill"
        assert payload["change_summary"]["change_type"] == "status_changed"
        assert payload["change_summary"]["field_name"] == "status"
        assert payload["change_summary"]["old_value"] == "introduced"
        assert payload["change_summary"]["new_value"] == "enacted"
        assert payload["detail_url"] == "/api/v1/bills/us-119-hr1"


class TestChangeTypeToEvent:
    def test_created_mapping(self):
        assert CHANGE_TYPE_TO_EVENT["created"] == "bill.created"

    def test_status_changed_mapping(self):
        assert CHANGE_TYPE_TO_EVENT["status_changed"] == "bill.status_changed"

    def test_updated_mapping(self):
        assert CHANGE_TYPE_TO_EVENT["updated"] == "bill.updated"

    def test_text_added_mapping(self):
        assert CHANGE_TYPE_TO_EVENT["text_added"] == "bill.text_added"


class TestEvaluateAlertsForChanges:
    @pytest.mark.asyncio
    async def test_empty_events_returns_zero(self):
        session = AsyncMock()
        result = await evaluate_alerts_for_changes(session, [])
        assert result == 0

    @pytest.mark.asyncio
    async def test_no_saved_searches_returns_zero(self):
        session = AsyncMock()

        event = MagicMock()
        event.bill_id = "us-119-hr1"
        event.change_type = "created"

        # Bill query
        bill_result = MagicMock()
        bill = MagicMock()
        bill.id = "us-119-hr1"
        bill_result.scalars.return_value.all.return_value = [bill]

        # Saved search query — empty
        search_result = MagicMock()
        search_result.scalars.return_value.all.return_value = []

        session.execute.side_effect = [bill_result, search_result]

        result = await evaluate_alerts_for_changes(session, [event])
        assert result == 0

    @pytest.mark.asyncio
    async def test_matching_criteria_enqueues_delivery(self):
        session = AsyncMock()

        event = MagicMock()
        event.bill_id = "us-119-hr1"
        event.change_type = "status_changed"
        event.field_name = "status"
        event.old_value = "introduced"
        event.new_value = "enacted"

        bill = MagicMock()
        bill.id = "us-119-hr1"
        bill.jurisdiction_id = "us"
        bill.status = "enacted"
        bill.title = "Test Bill"
        bill.identifier = "HR 1"

        search = MagicMock()
        search.id = uuid.uuid4()
        search.criteria = {"jurisdiction_id": "us"}

        sub = MagicMock()
        sub.saved_search_id = search.id
        sub.webhook_endpoint_id = uuid.uuid4()
        sub.event_types = ["bill.status_changed"]
        sub.is_active = True

        endpoint = MagicMock()
        endpoint.id = sub.webhook_endpoint_id
        endpoint.is_active = True

        # Mock execute calls: bills, searches, subscriptions (batch), endpoints (batch)
        bill_result = MagicMock()
        bill_result.scalars.return_value.all.return_value = [bill]

        search_result = MagicMock()
        search_result.scalars.return_value.all.return_value = [search]

        sub_result = MagicMock()
        sub_result.scalars.return_value.all.return_value = [sub]

        ep_result = MagicMock()
        ep_result.scalars.return_value.all.return_value = [endpoint]

        session.execute.side_effect = [bill_result, search_result, sub_result, ep_result]

        with patch(
            "src.services.alert_evaluator.enqueue_delivery",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            result = await evaluate_alerts_for_changes(session, [event])

        assert result == 1
        mock_enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_matching_criteria_skips(self):
        session = AsyncMock()

        event = MagicMock()
        event.bill_id = "us-119-hr1"
        event.change_type = "created"

        bill = MagicMock()
        bill.id = "us-119-hr1"
        bill.jurisdiction_id = "us"
        bill.status = "introduced"
        bill.title = "Test"

        search = MagicMock()
        search.id = uuid.uuid4()
        search.criteria = {"jurisdiction_id": "us-ca"}  # Doesn't match bill's "us"

        sub = MagicMock()
        sub.saved_search_id = search.id
        sub.webhook_endpoint_id = uuid.uuid4()
        sub.event_types = ["bill.created"]
        sub.is_active = True

        endpoint = MagicMock()
        endpoint.id = sub.webhook_endpoint_id
        endpoint.is_active = True

        bill_result = MagicMock()
        bill_result.scalars.return_value.all.return_value = [bill]

        search_result = MagicMock()
        search_result.scalars.return_value.all.return_value = [search]

        sub_result = MagicMock()
        sub_result.scalars.return_value.all.return_value = [sub]

        ep_result = MagicMock()
        ep_result.scalars.return_value.all.return_value = [endpoint]

        session.execute.side_effect = [bill_result, search_result, sub_result, ep_result]

        with patch(
            "src.services.alert_evaluator.enqueue_delivery",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            result = await evaluate_alerts_for_changes(session, [event])

        assert result == 0
        mock_enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_type_filter_on_subscription(self):
        """Subscription only subscribes to bill.created, but event is status_changed."""
        session = AsyncMock()

        event = MagicMock()
        event.bill_id = "us-119-hr1"
        event.change_type = "status_changed"

        bill = MagicMock()
        bill.id = "us-119-hr1"
        bill.jurisdiction_id = "us"
        bill.status = "enacted"
        bill.title = "Test"

        search = MagicMock()
        search.id = uuid.uuid4()
        search.criteria = {}  # matches everything

        sub = MagicMock()
        sub.saved_search_id = search.id
        sub.webhook_endpoint_id = uuid.uuid4()
        sub.event_types = ["bill.created"]  # Only created, not status_changed
        sub.is_active = True

        endpoint = MagicMock()
        endpoint.id = sub.webhook_endpoint_id
        endpoint.is_active = True

        bill_result = MagicMock()
        bill_result.scalars.return_value.all.return_value = [bill]

        search_result = MagicMock()
        search_result.scalars.return_value.all.return_value = [search]

        sub_result = MagicMock()
        sub_result.scalars.return_value.all.return_value = [sub]

        ep_result = MagicMock()
        ep_result.scalars.return_value.all.return_value = [endpoint]

        session.execute.side_effect = [bill_result, search_result, sub_result, ep_result]

        with patch(
            "src.services.alert_evaluator.enqueue_delivery",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            result = await evaluate_alerts_for_changes(session, [event])

        assert result == 0
        mock_enqueue.assert_not_called()
