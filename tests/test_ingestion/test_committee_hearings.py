"""Tests for committee hearing ingestion (no network calls)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.ingestion.committee_hearings import (
    CommitteeHearingIngester,
    _generate_hearing_id,
    _normalize_chamber,
)

# --- Sample API responses ---

SAMPLE_HEARINGS_LIST_RESPONSE = {
    "hearings": [
        {
            "chamber": "Senate",
            "congress": 119,
            "jacketNumber": "12345",
            "title": "Hearing on Data Privacy",
            "date": "2025-03-15",
            "url": "https://api.congress.gov/v3/hearing/119/senate/12345",
            "committee": {
                "name": "Committee on Commerce, Science, and Transportation",
                "systemCode": "sscm00",
            },
        },
        {
            "chamber": "House",
            "congress": 119,
            "jacketNumber": "67890",
            "number": "67890",
            "title": "Markup of HR 1234",
            "date": "2025-04-01",
            "url": "https://api.congress.gov/v3/hearing/119/house/67890",
            "committee": {
                "name": "Committee on Energy and Commerce",
                "systemCode": "hsif00",
            },
        },
    ],
    "pagination": {
        "count": 2,
    },
}

SAMPLE_HEARING_DETAIL_RESPONSE = {
    "hearing": {
        "jacketNumber": "12345",
        "title": "Hearing on Data Privacy",
        "congress": 119,
        "chamber": "Senate",
        "associatedBills": [
            {
                "type": "s",
                "number": "100",
                "congress": 119,
            },
        ],
    },
}

SAMPLE_HEARING_DETAIL_NO_BILLS = {
    "hearing": {
        "jacketNumber": "67890",
        "title": "Markup of HR 1234",
        "congress": 119,
        "chamber": "House",
    },
}


# --- Unit tests for helper functions ---


class TestNormalizeChamber:
    """Test chamber normalization."""

    def test_senate(self):
        assert _normalize_chamber("Senate") == "senate"

    def test_house(self):
        assert _normalize_chamber("House") == "house"

    def test_house_of_representatives(self):
        assert _normalize_chamber("House of Representatives") == "house"

    def test_joint(self):
        assert _normalize_chamber("Joint") == "joint"

    def test_abbreviation_s(self):
        assert _normalize_chamber("S") == "senate"

    def test_abbreviation_h(self):
        assert _normalize_chamber("H") == "house"

    def test_none(self):
        assert _normalize_chamber(None) is None

    def test_empty_string(self):
        assert _normalize_chamber("") is None

    def test_unknown_passthrough(self):
        assert _normalize_chamber("other") == "other"


class TestGenerateHearingId:
    """Test hearing ID generation."""

    def test_deterministic(self):
        id1 = _generate_hearing_id(119, "senate", "12345")
        id2 = _generate_hearing_id(119, "senate", "12345")
        assert id1 == id2

    def test_different_for_different_inputs(self):
        id1 = _generate_hearing_id(119, "senate", "12345")
        id2 = _generate_hearing_id(119, "house", "12345")
        assert id1 != id2

    def test_length(self):
        hid = _generate_hearing_id(119, "senate", "12345")
        assert len(hid) == 16

    def test_different_congress(self):
        id1 = _generate_hearing_id(118, "senate", "12345")
        id2 = _generate_hearing_id(119, "senate", "12345")
        assert id1 != id2


class TestParseDateStatic:
    """Test date parsing without instantiating the full ingester."""

    def test_iso_date(self):
        result = CommitteeHearingIngester._parse_date("2025-03-15")
        assert result == date(2025, 3, 15)

    def test_iso_datetime(self):
        result = CommitteeHearingIngester._parse_date("2025-03-15T10:00:00")
        assert result == date(2025, 3, 15)

    def test_us_date_format(self):
        result = CommitteeHearingIngester._parse_date("03/15/2025")
        assert result == date(2025, 3, 15)

    def test_none_input(self):
        result = CommitteeHearingIngester._parse_date(None)
        assert result is None

    def test_invalid_date(self):
        result = CommitteeHearingIngester._parse_date("not-a-date")
        assert result is None

    def test_empty_string(self):
        result = CommitteeHearingIngester._parse_date("")
        assert result is None


# --- Integration-style tests with mocked HTTP ---


class TestCommitteeHearingIngester:
    """Test the ingester with mocked HTTP and database sessions."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async database session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def ingester(self, mock_session):
        """Create an ingester with mocked session."""
        return CommitteeHearingIngester(mock_session, congress=119)

    def test_source_name(self, ingester):
        assert ingester.source_name == "committee_hearings"

    def test_congress_default(self):
        session = AsyncMock()
        ing = CommitteeHearingIngester(session)
        assert ing.congress == 119

    def test_congress_custom(self):
        session = AsyncMock()
        ing = CommitteeHearingIngester(session, congress=118)
        assert ing.congress == 118

    @pytest.mark.asyncio
    async def test_ingest_no_api_key(self, ingester, mock_session):
        """Ingestion should log warning and return when no API key is set."""
        with patch("src.ingestion.committee_hearings.settings") as mock_settings:
            mock_settings.congress_api_key = ""
            # Mock start_run to create a mock run object
            mock_run = MagicMock()
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            ingester.run = mock_run

            await ingester._fetch_hearings()
            # Should not have attempted any HTTP requests

    @pytest.mark.asyncio
    async def test_fetch_hearings_parses_response(self, ingester, mock_session):
        """Test that hearing list response is correctly parsed."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = SAMPLE_HEARINGS_LIST_RESPONSE

        mock_detail_response = MagicMock()
        mock_detail_response.status_code = 404

        with (
            patch("src.ingestion.committee_hearings.settings") as mock_settings,
            patch.object(ingester.client, "get", new_callable=AsyncMock) as mock_get,
        ):
            mock_settings.congress_api_key = "test-key"
            mock_get.side_effect = [
                mock_response,  # list endpoint
                mock_detail_response,  # detail for first hearing
                mock_detail_response,  # detail for second hearing
            ]

            # Mock session.execute for pg_insert to return a result with rowcount
            mock_result = MagicMock()
            mock_result.rowcount = 1
            mock_session.execute.return_value = mock_result

            await ingester._fetch_hearings()

            # Should have called execute for upserts
            assert mock_session.execute.call_count >= 2
            assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_upsert_hearing_extracts_fields(self, ingester, mock_session):
        """Test field extraction from a hearing data dict."""
        hearing_data = {
            "chamber": "Senate",
            "congress": 119,
            "jacketNumber": "12345",
            "title": "Test Hearing",
            "date": "2025-06-01",
            "url": "https://example.com/hearing",
            "committee": {
                "name": "Test Committee",
                "systemCode": "tc00",
            },
        }

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        # Mock the detail fetch to return 404
        with patch.object(ingester.client, "get", new_callable=AsyncMock) as mock_get:
            mock_detail = MagicMock()
            mock_detail.status_code = 404
            mock_get.return_value = mock_detail

            created = await ingester._upsert_hearing(hearing_data)
            assert created is True

    @pytest.mark.asyncio
    async def test_upsert_hearing_committee_as_string(self, ingester, mock_session):
        """Test handling when committee is a plain string."""
        hearing_data = {
            "chamber": "House",
            "congress": 119,
            "jacketNumber": "99999",
            "title": "Another Hearing",
            "date": "2025-07-01",
            "committee": "Energy and Commerce",
        }

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        with patch.object(ingester.client, "get", new_callable=AsyncMock) as mock_get:
            mock_detail = MagicMock()
            mock_detail.status_code = 404
            mock_get.return_value = mock_detail

            created = await ingester._upsert_hearing(hearing_data)
            assert created is True

    @pytest.mark.asyncio
    async def test_fetch_and_link_bills(self, ingester, mock_session):
        """Test that bill linking works when hearing detail has associated bills."""
        mock_detail_resp = MagicMock()
        mock_detail_resp.status_code = 200
        mock_detail_resp.json.return_value = SAMPLE_HEARING_DETAIL_RESPONSE

        # Mock finding the bill in database
        mock_bill = MagicMock()
        mock_bill.id = "us-119-s100"
        mock_bill_result = MagicMock()
        mock_bill_result.scalar_one_or_none.return_value = mock_bill

        mock_link_result = MagicMock()
        mock_link_result.rowcount = 1

        mock_session.execute = AsyncMock(side_effect=[mock_bill_result, mock_link_result])

        with patch.object(ingester.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_detail_resp

            with patch("src.ingestion.committee_hearings.settings") as mock_settings:
                mock_settings.congress_api_key = "test-key"

                await ingester._fetch_and_link_bills("test-hearing-id", 119, "senate", "12345")

            # Should have executed a select for the bill + an insert for the link
            assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_and_link_bills_no_jacket(self, ingester, mock_session):
        """Test that link fetching is skipped when jacket_number is empty."""
        await ingester._fetch_and_link_bills("test-id", 119, "senate", "")
        # Should not have made any HTTP calls
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_hearings_handles_http_error(self, ingester, mock_session):
        """Test graceful handling of HTTP errors."""
        with (
            patch("src.ingestion.committee_hearings.settings") as mock_settings,
            patch.object(ingester.client, "get", new_callable=AsyncMock) as mock_get,
        ):
            mock_settings.congress_api_key = "test-key"
            mock_get.side_effect = httpx.HTTPError("Connection refused")

            # Should not raise — errors are logged and loop breaks
            await ingester._fetch_hearings()

    @pytest.mark.asyncio
    async def test_close(self, ingester):
        """Test client cleanup."""
        with patch.object(ingester.client, "aclose", new_callable=AsyncMock) as mock_close:
            await ingester.close()
            mock_close.assert_called_once()
