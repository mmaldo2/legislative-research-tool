"""Tests for Federal Register ingester — parsing, bill reference extraction, and upsert logic."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.ingestion.federal_register import (
    FederalRegisterIngester,
    extract_bill_references,
)

# ---------------------------------------------------------------------------
# Sample API response fixtures
# ---------------------------------------------------------------------------

SAMPLE_FR_DOCUMENT = {
    "document_number": "2026-01234",
    "type": "Rule",
    "title": "Clean Air Standards Implementation Under H.R. 1234",
    "abstract": (
        "This final rule implements provisions of the Clean Air Act as amended "
        "by S. 567 and Public Law 119-42. The rule establishes new emission "
        "standards for industrial facilities in accordance with Section 112 of "
        "the Clean Air Act."
    ),
    "agencies": [
        {"name": "Environmental Protection Agency", "id": 145},
        {"name": "Department of the Interior", "id": 253},
    ],
    "publication_date": "2026-02-15",
    "citation": "91 FR 12345",
    "html_url": "https://www.federalregister.gov/documents/2026/02/15/2026-01234/clean-air",
    "pdf_url": "https://www.govinfo.gov/content/pkg/FR-2026-02-15/pdf/2026-01234.pdf",
    "raw_text_url": "https://www.federalregister.gov/documents/full_text/text/2026-01234.txt",
    "topics": ["Air pollution control", "Environmental protection"],
    "cfr_references": [
        {"title": 40, "part": 63, "chapter": "I"},
        {"title": 40, "part": 60, "chapter": "I"},
    ],
    "docket_ids": ["EPA-HQ-OAR-2025-0001"],
    "regulation_id_numbers": ["2060-AV01"],
}

SAMPLE_FR_PROPOSED_RULE = {
    "document_number": "2026-05678",
    "type": "Proposed Rule",
    "title": "Proposed Water Quality Standards for Industrial Discharge",
    "abstract": "Proposed amendments to water quality standards. See also H.J.Res. 45.",
    "agencies": [{"name": "Environmental Protection Agency", "id": 145}],
    "publication_date": "2026-02-20",
    "citation": "91 FR 23456",
    "html_url": "https://www.federalregister.gov/documents/2026/02/20/2026-05678/water-quality",
    "pdf_url": None,
    "raw_text_url": None,
    "topics": ["Water pollution control"],
    "cfr_references": [],
    "docket_ids": [],
    "regulation_id_numbers": [],
}

SAMPLE_FR_API_RESPONSE = {
    "count": 2,
    "total_pages": 1,
    "results": [SAMPLE_FR_DOCUMENT, SAMPLE_FR_PROPOSED_RULE],
}


# ---------------------------------------------------------------------------
# Bill reference extraction tests
# ---------------------------------------------------------------------------


class TestExtractBillReferences:
    """Test bill reference extraction from free text."""

    def test_extract_hr_reference(self):
        refs = extract_bill_references("This rule implements H.R. 1234.")
        assert "HR 1234" in refs

    def test_extract_hr_no_dots(self):
        refs = extract_bill_references("Pursuant to HR 5678, the agency...")
        assert "HR 5678" in refs

    def test_extract_senate_bill(self):
        refs = extract_bill_references("As required by S. 567, we propose...")
        assert "S 567" in refs

    def test_extract_senate_bill_no_dot(self):
        refs = extract_bill_references("As required by S 42, the regulation...")
        assert "S 42" in refs

    def test_extract_public_law(self):
        refs = extract_bill_references("Under Public Law 119-42, agencies must...")
        assert "PL 119-42" in refs

    def test_extract_pl_abbreviation(self):
        refs = extract_bill_references("P.L. 118-100 requires compliance by 2026.")
        assert "PL 118-100" in refs

    def test_extract_joint_resolution(self):
        refs = extract_bill_references("As specified in H.J.Res. 45, the President...")
        assert "HJRES 45" in refs

    def test_extract_multiple_references(self):
        text = (
            "This rule implements H.R. 1234 and S. 567. "
            "See also Public Law 119-42 for additional context."
        )
        refs = extract_bill_references(text)
        assert "HR 1234" in refs
        assert "S 567" in refs
        assert "PL 119-42" in refs

    def test_no_references(self):
        refs = extract_bill_references("This rule has no legislative references.")
        assert refs == []

    def test_empty_string(self):
        refs = extract_bill_references("")
        assert refs == []

    def test_none_string(self):
        refs = extract_bill_references(None)  # type: ignore[arg-type]
        assert refs == []

    def test_section_not_senate(self):
        """'Section 123' should not be mistaken for 'S. 123'."""
        refs = extract_bill_references("See Section 5 and Section 112 of the Clean Air Act.")
        # Should not contain S 5 or S 112
        assert not any(r.startswith("S ") for r in refs)

    def test_results_are_sorted(self):
        refs = extract_bill_references("S. 999 and H.R. 100 and S. 1")
        assert refs == sorted(refs)


# ---------------------------------------------------------------------------
# Document parsing tests
# ---------------------------------------------------------------------------


class TestDocumentParsing:
    """Test parsing of Federal Register API response data."""

    def test_parse_document_type_rule(self):
        from src.ingestion.federal_register import _DOC_TYPE_MAP

        assert _DOC_TYPE_MAP["Rule"] == "rule"

    def test_parse_document_type_proposed_rule(self):
        from src.ingestion.federal_register import _DOC_TYPE_MAP

        assert _DOC_TYPE_MAP["Proposed Rule"] == "proposed_rule"

    def test_parse_document_type_notice(self):
        from src.ingestion.federal_register import _DOC_TYPE_MAP

        assert _DOC_TYPE_MAP["Notice"] == "notice"

    def test_parse_document_type_presidential(self):
        from src.ingestion.federal_register import _DOC_TYPE_MAP

        assert _DOC_TYPE_MAP["Presidential Document"] == "presidential_document"

    def test_agency_extraction(self):
        agencies_raw = SAMPLE_FR_DOCUMENT["agencies"]
        agency_names = [a.get("name", "") for a in agencies_raw if a.get("name")]
        assert agency_names == [
            "Environmental Protection Agency",
            "Department of the Interior",
        ]

    def test_cfr_reference_extraction(self):
        cfr_refs_raw = SAMPLE_FR_DOCUMENT["cfr_references"]
        cfr_references = [
            {"title": r.get("title"), "part": r.get("part"), "chapter": r.get("chapter")}
            for r in cfr_refs_raw
        ]
        assert len(cfr_references) == 2
        assert cfr_references[0] == {"title": 40, "part": 63, "chapter": "I"}

    def test_publication_date_parsing(self):
        pub_date_str = SAMPLE_FR_DOCUMENT["publication_date"]
        pub_date = date.fromisoformat(pub_date_str)
        assert pub_date == date(2026, 2, 15)

    def test_bill_references_from_sample(self):
        title = SAMPLE_FR_DOCUMENT["title"]
        abstract = SAMPLE_FR_DOCUMENT["abstract"]
        search_text = f"{title} {abstract}"
        refs = extract_bill_references(search_text)
        assert "HR 1234" in refs
        assert "S 567" in refs
        assert "PL 119-42" in refs


# ---------------------------------------------------------------------------
# Ingester upsert logic tests (mocked DB)
# ---------------------------------------------------------------------------


class TestFederalRegisterIngester:
    """Test the ingester's upsert flow with mocked HTTP and DB."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(rowcount=1))
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def ingester(self, mock_session):
        return FederalRegisterIngester(mock_session, lookback_days=30)

    @pytest.mark.asyncio
    async def test_upsert_document_returns_true_on_create(self, ingester):
        """_upsert_document returns True when a row is created/updated."""
        result = await ingester._upsert_document(SAMPLE_FR_DOCUMENT)
        assert result is True

    @pytest.mark.asyncio
    async def test_upsert_document_uses_document_number_as_id(self, ingester, mock_session):
        """The upserted values should use the document_number as the primary key."""
        await ingester._upsert_document(SAMPLE_FR_DOCUMENT)
        # The execute call should have been made with a pg_insert statement
        call_args = mock_session.execute.call_args
        assert call_args is not None
        # Verify the statement was called (it's a compiled insert)
        stmt = call_args[0][0]
        # The compiled parameters should contain our document number
        compiled = stmt.compile()
        assert "2026-01234" in str(compiled.params) or "2026-01234" in str(compiled)

    @pytest.mark.asyncio
    async def test_upsert_skips_empty_document_number(self, ingester):
        """Documents without a document_number are skipped."""
        result = await ingester._upsert_document({"document_number": "", "type": "Rule"})
        assert result is False

    @pytest.mark.asyncio
    async def test_upsert_proposed_rule_type(self, ingester):
        """Proposed rules are correctly typed."""
        await ingester._upsert_document(SAMPLE_FR_PROPOSED_RULE)
        call_args = ingester.session.execute.call_args
        stmt = call_args[0][0]
        compiled = stmt.compile()
        # Check that proposed_rule appears in the compiled statement
        params_str = str(compiled.params)
        assert "proposed_rule" in params_str

    @pytest.mark.asyncio
    async def test_fetch_documents_pagination(self, ingester):
        """Test that _fetch_documents iterates pages correctly."""
        mock_request = httpx.Request("GET", "https://www.federalregister.gov/api/v1/documents.json")
        page1_response = httpx.Response(
            200,
            json={
                "count": 150,
                "total_pages": 2,
                "results": [SAMPLE_FR_DOCUMENT],
            },
            request=mock_request,
        )
        page2_response = httpx.Response(
            200,
            json={
                "count": 150,
                "total_pages": 2,
                "results": [SAMPLE_FR_PROPOSED_RULE],
            },
            request=mock_request,
        )

        with patch.object(ingester.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [page1_response, page2_response]
            created, updated = await ingester._fetch_documents()

        assert mock_get.call_count == 2
        assert created + updated == 2

    @pytest.mark.asyncio
    async def test_fetch_documents_handles_http_error(self, ingester):
        """HTTP errors should be caught without crashing the ingester."""
        with patch.object(ingester.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(500),
            )
            created, updated = await ingester._fetch_documents()

        assert created == 0
        assert updated == 0

    @pytest.mark.asyncio
    async def test_ingest_full_flow(self, ingester, mock_session):
        """Test the complete ingest() method with mocked HTTP."""
        mock_request = httpx.Request("GET", "https://www.federalregister.gov/api/v1/documents.json")
        api_response = httpx.Response(200, json=SAMPLE_FR_API_RESPONSE, request=mock_request)

        with patch.object(
            ingester.client, "get", new_callable=AsyncMock, return_value=api_response
        ):
            await ingester.ingest()

        # Should have committed (from _fetch_documents + finish_run)
        assert mock_session.commit.call_count >= 1
        # Should have recorded the run
        assert ingester.run is not None
        assert ingester.run.status == "completed"

    @pytest.mark.asyncio
    async def test_ingest_records_failure(self, ingester, mock_session):
        """If ingestion raises, the run should be marked as failed."""
        with patch.object(ingester.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = RuntimeError("Connection reset")
            with pytest.raises(RuntimeError, match="Connection reset"):
                await ingester.ingest()

        assert ingester.run is not None
        assert ingester.run.status == "failed"

    @pytest.mark.asyncio
    async def test_build_params(self, ingester):
        """Verify the query parameters structure."""
        params = ingester._build_params(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
            page=1,
        )
        assert params["per_page"] == 100
        assert params["page"] == 1
        assert params["conditions[publication_date][gte]"] == "2026-02-01"
        assert params["conditions[publication_date][lte]"] == "2026-02-28"
        assert "conditions[type][]" in params

    @pytest.mark.asyncio
    async def test_close(self, ingester):
        """close() should close the HTTP client."""
        with patch.object(ingester.client, "aclose", new_callable=AsyncMock) as mock_close:
            await ingester.close()
            mock_close.assert_called_once()
