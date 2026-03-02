"""Tests for CRS report ingestion (no network calls)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.ingestion.crs_reports import (
    CrsReportIngester,
    _parse_date,
    extract_bill_references,
)

# --- Sample API response fixtures ---

SAMPLE_LISTING_RESPONSE = [
    {
        "number": "R12345",
        "title": "Overview of Federal Data Privacy Legislation",
        "latestPubDate": "2025-11-15",
    },
    {
        "number": "RL33476",
        "title": "Congressional Oversight Manual",
        "latestPubDate": "2025-10-01",
    },
    {
        "number": "R99999",
        "title": "Old Report",
        "latestPubDate": "2020-01-01",
    },
]

SAMPLE_REPORT_DETAIL = {
    "number": "R12345",
    "title": "Overview of Federal Data Privacy Legislation",
    "summary": "This report examines H.R. 1234 and S. 567, two bills addressing consumer privacy.",
    "authors": [
        {"name": "Jane Smith"},
        {"name": "John Doe"},
    ],
    "topics": [
        {"name": "Data Privacy"},
        {"name": "Consumer Protection"},
    ],
    "firstVersionDate": "2025-06-01",
    "latestPubDate": "2025-11-15",
    "versions": [
        {
            "date": "2025-06-01",
            "formats": [
                {"format": "HTML", "url": "https://example.com/R12345.html"},
                {"format": "PDF", "url": "https://example.com/R12345.pdf"},
            ],
        },
        {
            "date": "2025-11-15",
            "formats": [
                {"format": "HTML", "url": "https://example.com/R12345-v2.html"},
                {"format": "PDF", "url": "https://example.com/R12345-v2.pdf"},
            ],
        },
    ],
}

SAMPLE_REPORT_DETAIL_MINIMAL = {
    "number": "RL33476",
    "title": "Congressional Oversight Manual",
    "date": "2025-10-01",
    "authors": ["Alice Johnson"],
    "topics": ["Congressional Oversight"],
    "versions": [],
}


class TestExtractBillReferences:
    """Test bill reference extraction from text."""

    def test_hr_reference(self):
        refs = extract_bill_references("This report covers H.R. 1234.")
        assert "HR 1234" in refs

    def test_senate_reference(self):
        refs = extract_bill_references("Analysis of S. 567 provisions.")
        assert "S 567" in refs

    def test_multiple_references(self):
        refs = extract_bill_references("Comparing H.R. 1234 and S. 567 with H.R. 890.")
        assert len(refs) == 3
        assert "HR 1234" in refs
        assert "S 567" in refs
        assert "HR 890" in refs

    def test_resolution_references(self):
        refs = extract_bill_references("H.Res. 100 and S.J.Res. 42 were introduced.")
        assert "HRES 100" in refs
        assert "SJRES 42" in refs

    def test_concurrent_resolution(self):
        refs = extract_bill_references("S.Con.Res. 15 passed the Senate.")
        assert "SCONRES 15" in refs

    def test_no_references(self):
        refs = extract_bill_references("This report has no bill references.")
        assert refs == []

    def test_empty_string(self):
        refs = extract_bill_references("")
        assert refs == []

    def test_no_duplicates(self):
        refs = extract_bill_references("H.R. 1234 and H.R. 1234 again.")
        assert refs.count("HR 1234") == 1


class TestParseDate:
    """Test date parsing utility."""

    def test_valid_iso_date(self):
        assert _parse_date("2025-11-15") == date(2025, 11, 15)

    def test_datetime_string(self):
        assert _parse_date("2025-11-15T10:30:00Z") == date(2025, 11, 15)

    def test_invalid_date(self):
        assert _parse_date("not-a-date") is None

    def test_none_input(self):
        assert _parse_date(None) is None

    def test_empty_string(self):
        assert _parse_date("") is None


class TestCrsReportIngesterUnit:
    """Unit tests for CrsReportIngester logic (mocked HTTP and DB)."""

    def _make_ingester(self) -> CrsReportIngester:
        """Create an ingester with a mocked session."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(rowcount=1))
        return CrsReportIngester(mock_session, months_back=12, max_reports=100)

    def test_source_name(self):
        ingester = self._make_ingester()
        assert ingester.source_name == "crs_reports"

    def test_cutoff_date(self):
        ingester = self._make_ingester()
        ingester.months_back = 6
        cutoff = ingester._cutoff_date()
        assert isinstance(cutoff, date)
        # Cutoff should be roughly 6 months ago
        from datetime import UTC, datetime

        now = datetime.now(tz=UTC)
        # Allow some tolerance for month boundary
        assert cutoff.year in (now.year - 1, now.year)

    @pytest.mark.asyncio
    async def test_fetch_report_listing_filters_old(self):
        """Listing should filter out reports older than cutoff."""
        ingester = self._make_ingester()
        ingester.months_back = 12

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_LISTING_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch.object(ingester.client, "get", return_value=mock_response) as mock_get:
            result = await ingester._fetch_report_listing()
            mock_get.assert_called_once()

        # R12345 and RL33476 are recent, R99999 is from 2020 (should be filtered)
        numbers = [r.get("number") for r in result]
        assert "R12345" in numbers
        assert "RL33476" in numbers
        assert "R99999" not in numbers

    @pytest.mark.asyncio
    async def test_fetch_report_listing_http_error(self):
        """Listing should return empty list on HTTP error."""
        ingester = self._make_ingester()

        with patch.object(
            ingester.client,
            "get",
            side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock()),
        ):
            result = await ingester._fetch_report_listing()

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_report_detail_success(self):
        """Detail fetch should return parsed JSON."""
        ingester = self._make_ingester()

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_REPORT_DETAIL
        mock_response.raise_for_status = MagicMock()

        with patch.object(ingester.client, "get", return_value=mock_response):
            result = await ingester._fetch_report_detail("R12345")

        assert result is not None
        assert result["number"] == "R12345"

    @pytest.mark.asyncio
    async def test_fetch_report_detail_http_error(self):
        """Detail fetch should return None on HTTP error."""
        ingester = self._make_ingester()

        with patch.object(
            ingester.client,
            "get",
            side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock()),
        ):
            result = await ingester._fetch_report_detail("NONEXISTENT")

        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_report_extracts_metadata(self):
        """Upsert should extract authors, topics, dates, and bill refs."""
        ingester = self._make_ingester()

        created = await ingester._upsert_report(SAMPLE_REPORT_DETAIL)

        assert created is True
        # Verify execute was called with the pg_insert statement
        ingester.session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_report_minimal_data(self):
        """Upsert should handle minimal report data (string authors, no versions)."""
        ingester = self._make_ingester()

        created = await ingester._upsert_report(SAMPLE_REPORT_DETAIL_MINIMAL)

        assert created is True
        ingester.session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_report_no_number(self):
        """Upsert should return False if report has no number."""
        ingester = self._make_ingester()

        created = await ingester._upsert_report({"title": "No Number"})

        assert created is False
        ingester.session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_listing_respects_max_reports(self):
        """Listing should respect max_reports limit."""
        ingester = self._make_ingester()
        ingester.max_reports = 1
        ingester.months_back = 24

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_LISTING_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch.object(ingester.client, "get", return_value=mock_response):
            result = await ingester._fetch_report_listing()

        assert len(result) <= 1

    @pytest.mark.asyncio
    async def test_close(self):
        """Close should close the HTTP client."""
        ingester = self._make_ingester()
        with patch.object(ingester.client, "aclose", new_callable=AsyncMock) as mock_close:
            await ingester.close()
            mock_close.assert_called_once()


class TestCrsReportIngesterIntegration:
    """Integration-style tests for the full ingest pipeline (mocked HTTP + DB)."""

    @pytest.mark.asyncio
    async def test_full_ingest_pipeline(self):
        """Full ingest should fetch listing, then details, and upsert each."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(rowcount=1))

        ingester = CrsReportIngester(mock_session, months_back=24, max_reports=100)

        listing_response = MagicMock()
        listing_response.json.return_value = SAMPLE_LISTING_RESPONSE[:2]  # Only recent ones
        listing_response.raise_for_status = MagicMock()

        detail_response_1 = MagicMock()
        detail_response_1.json.return_value = SAMPLE_REPORT_DETAIL
        detail_response_1.raise_for_status = MagicMock()

        detail_response_2 = MagicMock()
        detail_response_2.json.return_value = SAMPLE_REPORT_DETAIL_MINIMAL
        detail_response_2.raise_for_status = MagicMock()

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "reports.json" in url:
                return listing_response
            elif "R12345" in url:
                return detail_response_1
            elif "RL33476" in url:
                return detail_response_2
            raise httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock())

        with patch.object(ingester.client, "get", side_effect=mock_get):
            await ingester.ingest()

        # Should have fetched listing + 2 details = 3 HTTP calls
        assert call_count == 3

        # Session should have been committed
        mock_session.commit.assert_called()

        await ingester.close()

    @pytest.mark.asyncio
    async def test_ingest_handles_detail_failure_gracefully(self):
        """Ingest should continue even if individual report detail fetch fails."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(rowcount=1))

        ingester = CrsReportIngester(mock_session, months_back=24, max_reports=100)

        listing_response = MagicMock()
        listing_response.json.return_value = SAMPLE_LISTING_RESPONSE[:2]
        listing_response.raise_for_status = MagicMock()

        async def mock_get(url, **kwargs):
            if "reports.json" in url:
                return listing_response
            # All detail fetches fail
            raise httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock())

        with patch.object(ingester.client, "get", side_effect=mock_get):
            # Should not raise even though details fail
            await ingester.ingest()

        await ingester.close()
