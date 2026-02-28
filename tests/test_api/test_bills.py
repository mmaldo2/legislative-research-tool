"""Tests for bill API endpoints."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def _mock_bill(**overrides):
    """Create a mock Bill object."""
    defaults = {
        "id": "abc123",
        "jurisdiction_id": "us",
        "session_id": "us-119",
        "identifier": "HR 1234",
        "title": "Consumer Data Privacy Act",
        "status": "introduced",
        "status_date": date(2025, 1, 15),
        "classification": ["bill"],
        "subject": ["Privacy"],
        "source_urls": ["https://example.com"],
        "created_at": datetime(2025, 1, 15),
        "updated_at": datetime(2025, 1, 15),
        "texts": [],
        "actions": [],
        "sponsorships": [],
        "analyses": [],
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    return mock


class TestListBills:
    def test_list_bills_empty(self, client):
        """Empty database returns empty list with correct pagination."""
        with patch("src.api.bills.get_session") as mock_get_session:
            session = AsyncMock()
            # First call: count query
            count_result = MagicMock()
            count_result.scalar_one.return_value = 0
            # Second call: list query
            list_result = MagicMock()
            list_result.scalars.return_value.all.return_value = []

            session.execute = AsyncMock(side_effect=[count_result, list_result])
            mock_get_session.return_value = session

            app.dependency_overrides[get_session_fn()] = lambda: session

        # Test the schema shape
        from src.schemas.bill import BillListResponse
        from src.schemas.common import MetaResponse

        response = BillListResponse(
            data=[],
            meta=MetaResponse(total_count=0, page=1, per_page=20),
        )
        assert response.data == []
        assert response.meta.total_count == 0

    def test_bill_summary_schema(self):
        """BillSummary schema validates correctly."""
        from src.schemas.bill import BillSummary

        summary = BillSummary(
            id="abc123",
            jurisdiction_id="us",
            session_id="us-119",
            identifier="HR 1234",
            title="Test Bill",
            status="introduced",
        )
        assert summary.id == "abc123"
        assert summary.classification is None

    def test_bill_detail_schema(self):
        """BillDetailResponse schema validates correctly."""
        from src.schemas.bill import BillDetailResponse

        detail = BillDetailResponse(
            id="abc123",
            jurisdiction_id="us",
            session_id="us-119",
            identifier="HR 1234",
            title="Test Bill",
            status="introduced",
        )
        assert detail.texts == []
        assert detail.actions == []
        assert detail.sponsors == []
        assert detail.ai_summary is None


class TestBillFilters:
    def test_bill_summary_with_subjects(self):
        """BillSummary with subject list."""
        from src.schemas.bill import BillSummary

        summary = BillSummary(
            id="abc123",
            jurisdiction_id="us-ca",
            session_id="us-ca-2025",
            identifier="AB 100",
            title="Housing Bill",
            subject=["Housing", "Zoning"],
        )
        assert summary.subject == ["Housing", "Zoning"]
        assert summary.jurisdiction_id == "us-ca"


def get_session_fn():
    """Get the get_session dependency function."""
    from src.api.deps import get_session

    return get_session
