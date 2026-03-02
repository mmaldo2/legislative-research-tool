"""Federal Register regulatory document ingester.

Fetches rules, proposed rules, and notices from the Federal Register API.
Links regulatory documents to bills by extracting bill references from titles/abstracts.
"""

import logging
import re
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import BaseIngester
from src.models.regulatory_document import RegulatoryDocument

logger = logging.getLogger(__name__)

# Federal Register API — free, no key required
FR_API_BASE = "https://www.federalregister.gov/api/v1"

# Patterns that match bill references in text
# Matches: H.R. 1234, HR 1234, S. 567, S 567, H.J.Res. 12, S.Con.Res. 45,
#          Public Law 119-12, P.L. 119-12
_BILL_REFERENCE_PATTERNS = [
    re.compile(
        r"\b(H\.?\s?R\.?|H\.?\s?J\.?\s?Res\.?|H\.?\s?Con\.?\s?Res\.?)\s*(\d+)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(S\.?)\s*(\d+)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(S\.?\s?J\.?\s?Res\.?|S\.?\s?Con\.?\s?Res\.?)\s*(\d+)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:Public\s+Law|P\.?\s?L\.?)\s+(\d+)[–\-](\d+)\b",
        re.IGNORECASE,
    ),
]

# Map Federal Register document type codes to our canonical types
_DOC_TYPE_MAP = {
    "Rule": "rule",
    "Proposed Rule": "proposed_rule",
    "Notice": "notice",
    "Presidential Document": "presidential_document",
}


def extract_bill_references(text: str) -> list[str]:
    """Extract bill identifier references from free text.

    Returns a list of normalized bill reference strings (e.g., "HR 1234", "S 567").
    """
    if not text:
        return []

    refs: set[str] = set()

    # House and joint/concurrent resolutions
    for pattern in _BILL_REFERENCE_PATTERNS[:1]:
        for match in pattern.finditer(text):
            prefix = re.sub(r"[\s.]", "", match.group(1)).upper()
            number = match.group(2)
            refs.add(f"{prefix} {number}")

    # Senate bills — avoid matching "Section" or "Sec." followed by a number
    for match in _BILL_REFERENCE_PATTERNS[1].finditer(text):
        # Check that we're not matching "Section 123" or "Sec. 123"
        start = match.start()
        preceding = text[max(0, start - 8) : start].lower()
        if "section" in preceding or "sec" in preceding:
            continue
        prefix = "S"
        number = match.group(2)
        refs.add(f"{prefix} {number}")

    # Senate resolutions
    for match in _BILL_REFERENCE_PATTERNS[2].finditer(text):
        prefix = re.sub(r"[\s.]", "", match.group(1)).upper()
        number = match.group(2)
        refs.add(f"{prefix} {number}")

    # Public Laws — store as "PL 119-12"
    for match in _BILL_REFERENCE_PATTERNS[3].finditer(text):
        congress = match.group(1)
        law_num = match.group(2)
        refs.add(f"PL {congress}-{law_num}")

    return sorted(refs)


class FederalRegisterIngester(BaseIngester):
    """Ingests regulatory documents from the Federal Register API."""

    source_name = "federal_register"

    def __init__(
        self,
        session: AsyncSession,
        lookback_days: int = 30,
        document_types: list[str] | None = None,
    ):
        super().__init__(session)
        self.lookback_days = lookback_days
        self.document_types = document_types or ["RULE", "PRORULE", "NOTICE"]
        self.client = httpx.AsyncClient(
            timeout=60.0,
            headers={"Accept": "application/json"},
        )

    async def ingest(self) -> None:
        """Ingest recent Federal Register documents."""
        await self.start_run("incremental")
        try:
            docs_created, docs_updated = await self._fetch_documents()
            if self.run:
                self.run.records_created = docs_created
                self.run.records_updated = docs_updated
            await self.finish_run("completed")
        except Exception as e:
            logger.error("Federal Register ingestion failed: %s", e)
            await self.finish_run("failed")
            raise

    async def _fetch_documents(self) -> tuple[int, int]:
        """Fetch documents from the Federal Register API. Returns (created, updated)."""
        end_date = date.today()
        start_date = end_date - timedelta(days=self.lookback_days)

        docs_created = 0
        docs_updated = 0
        page = 1

        while True:
            params = self._build_params(start_date, end_date, page)
            try:
                resp = await self.client.get(f"{FR_API_BASE}/documents.json", params=params)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.error("Federal Register API request failed (page %d): %s", page, e)
                break

            data = resp.json()
            results = data.get("results", [])
            if not results:
                break

            for doc_data in results:
                was_created = await self._upsert_document(doc_data)
                if was_created:
                    docs_created += 1
                else:
                    docs_updated += 1

            await self.session.commit()

            total_pages = data.get("total_pages", 1)
            logger.info(
                "Federal Register: processed page %d/%d (%d documents)",
                page,
                total_pages,
                len(results),
            )

            if page >= total_pages:
                break
            page += 1

        logger.info(
            "Federal Register ingestion complete: %d created, %d updated",
            docs_created,
            docs_updated,
        )
        return docs_created, docs_updated

    def _build_params(
        self, start_date: date, end_date: date, page: int
    ) -> dict[str, str | int | list[str]]:
        """Build query parameters for the Federal Register API."""
        params: dict[str, str | int | list[str]] = {
            "per_page": 100,
            "page": page,
            "order": "newest",
            "conditions[publication_date][gte]": start_date.isoformat(),
            "conditions[publication_date][lte]": end_date.isoformat(),
        }

        # Add document type filters
        for doc_type in self.document_types:
            params.setdefault("conditions[type][]", [])
            if isinstance(params["conditions[type][]"], list):
                params["conditions[type][]"].append(doc_type)  # type: ignore[union-attr]

        # Request the fields we need
        params["fields[]"] = [  # type: ignore[assignment]
            "document_number",
            "type",
            "title",
            "abstract",
            "agencies",
            "publication_date",
            "citation",
            "html_url",
            "pdf_url",
            "raw_text_url",
            "topics",
            "cfr_references",
            "docket_ids",
            "regulation_id_numbers",
        ]

        return params

    async def _upsert_document(self, doc_data: dict) -> bool:
        """Insert or update a regulatory document. Returns True if created."""
        document_number = doc_data.get("document_number", "")
        if not document_number:
            return False

        doc_type_raw = doc_data.get("type", "Notice")
        document_type = _DOC_TYPE_MAP.get(doc_type_raw, doc_type_raw.lower().replace(" ", "_"))

        title = doc_data.get("title", "Untitled")
        abstract = doc_data.get("abstract")

        # Extract agency names
        agencies_raw = doc_data.get("agencies", [])
        agency_names = [a.get("name", "") for a in agencies_raw if a.get("name")]

        # Parse publication date
        pub_date_str = doc_data.get("publication_date")
        publication_date = date.fromisoformat(pub_date_str) if pub_date_str else None

        citation = doc_data.get("citation")
        federal_register_url = doc_data.get("html_url")
        pdf_url = doc_data.get("pdf_url")
        raw_text_url = doc_data.get("raw_text_url")

        topics = doc_data.get("topics") or None
        docket_ids = doc_data.get("docket_ids") or None
        regulation_id_numbers = doc_data.get("regulation_id_numbers") or None

        # Extract CFR references
        cfr_refs_raw = doc_data.get("cfr_references", [])
        cfr_references = (
            [
                {"title": r.get("title"), "part": r.get("part"), "chapter": r.get("chapter")}
                for r in cfr_refs_raw
            ]
            if cfr_refs_raw
            else None
        )

        # Extract bill references from title + abstract
        search_text = f"{title} {abstract or ''}"
        related_bill_ids = extract_bill_references(search_text) or None

        now = datetime.now(tz=UTC)
        stmt = pg_insert(RegulatoryDocument).values(
            id=document_number,
            document_type=document_type,
            title=title,
            abstract=abstract,
            agency_names=agency_names or None,
            publication_date=publication_date,
            citation=citation,
            federal_register_url=federal_register_url,
            pdf_url=pdf_url,
            raw_text_url=raw_text_url,
            topics=topics,
            cfr_references=cfr_references,
            related_bill_ids=related_bill_ids,
            docket_ids=docket_ids,
            regulation_id_numbers=regulation_id_numbers,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "title": title,
                "abstract": abstract,
                "agency_names": agency_names or None,
                "publication_date": publication_date,
                "citation": citation,
                "federal_register_url": federal_register_url,
                "pdf_url": pdf_url,
                "raw_text_url": raw_text_url,
                "topics": topics,
                "cfr_references": cfr_references,
                "related_bill_ids": related_bill_ids,
                "docket_ids": docket_ids,
                "regulation_id_numbers": regulation_id_numbers,
                "updated_at": now,
            },
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
