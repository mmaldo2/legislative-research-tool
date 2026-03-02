"""EveryCRSReport.com ingester for Congressional Research Service reports.

Fetches CRS report metadata and content from EveryCRSReport.com's public API:
- Reports listing: https://www.everycrsreport.com/reports.json
- Individual report: https://www.everycrsreport.com/reports/{number}.json
"""

import logging
import re
from datetime import UTC, date, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import BaseIngester
from src.models.crs_report import CrsReport

logger = logging.getLogger(__name__)

EVERYCRS_BASE = "https://www.everycrsreport.com"
REPORTS_LISTING_URL = f"{EVERYCRS_BASE}/reports.json"

# Matches bill references like "H.R. 1234", "S. 567", "H.Res. 89", "S.J.Res. 12"
_BILL_REF_RE = re.compile(
    r"\b(H\.R\.|S\.|H\.Res\.|S\.Res\.|H\.J\.Res\.|S\.J\.Res\.|H\.Con\.Res\.|S\.Con\.Res\.)"
    r"\s*(\d+)\b"
)


def extract_bill_references(text: str) -> list[str]:
    """Extract bill identifier strings from text.

    Returns normalized references like "HR 1234", "S 567".
    """
    if not text:
        return []

    refs: list[str] = []
    for match in _BILL_REF_RE.finditer(text):
        prefix = match.group(1)
        number = match.group(2)
        # Normalize: "H.R." -> "HR", "S." -> "S", "H.Res." -> "HRES", etc.
        normalized = prefix.replace(".", "").replace(" ", "").upper()
        ref = f"{normalized} {number}"
        if ref not in refs:
            refs.append(ref)

    return refs


def _parse_date(date_str: str | None) -> date | None:
    """Parse an ISO date string, returning None on failure."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str[:10])
    except (ValueError, TypeError):
        return None


class CrsReportIngester(BaseIngester):
    """Ingests CRS reports from EveryCRSReport.com."""

    source_name = "crs_reports"

    def __init__(
        self,
        session: AsyncSession,
        *,
        months_back: int = 6,
        max_reports: int = 500,
    ):
        super().__init__(session)
        self.months_back = months_back
        self.max_reports = max_reports
        self.client = httpx.AsyncClient(
            timeout=60.0,
            headers={"User-Agent": "legislative-research-tool/0.1"},
        )

    async def ingest(self) -> None:
        """Run the CRS report ingestion pipeline."""
        await self.start_run("full")
        try:
            report_stubs = await self._fetch_report_listing()
            if not report_stubs:
                logger.warning("No CRS reports found in listing")
                await self.finish_run("completed")
                return

            reports_created = 0
            reports_updated = 0

            for i, stub in enumerate(report_stubs):
                report_number = stub.get("number", "")
                if not report_number:
                    continue

                try:
                    detail = await self._fetch_report_detail(report_number)
                    if detail:
                        created = await self._upsert_report(detail)
                        if created:
                            reports_created += 1
                        else:
                            reports_updated += 1
                except Exception as e:
                    logger.warning("Failed to process CRS report %s: %s", report_number, e)

                # Commit in batches of 50
                if (i + 1) % 50 == 0:
                    await self.session.commit()
                    logger.info("Processed %d / %d CRS reports", i + 1, len(report_stubs))

            await self.session.commit()

            if self.run:
                self.run.records_created = reports_created
                self.run.records_updated = reports_updated

            logger.info(
                "CRS ingestion complete: %d created, %d updated",
                reports_created,
                reports_updated,
            )
            await self.finish_run("completed")
        except Exception as e:
            logger.error("CRS report ingestion failed: %s", e)
            await self.finish_run("failed")
            raise

    async def _fetch_report_listing(self) -> list[dict]:
        """Fetch the reports listing from EveryCRSReport.com.

        Returns a filtered list of report stubs (number + basic metadata)
        limited to recent reports within the configured months_back window.
        """
        try:
            resp = await self.client.get(REPORTS_LISTING_URL)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch CRS reports listing: %s", e)
            return []

        data = resp.json()
        reports = data if isinstance(data, list) else data.get("reports", [])

        # Filter to recent reports and limit count
        cutoff = self._cutoff_date()
        filtered: list[dict] = []
        for report in reports:
            last_date = _parse_date(report.get("latestPubDate") or report.get("date"))
            if last_date and last_date < cutoff:
                continue
            filtered.append(report)
            if len(filtered) >= self.max_reports:
                break

        logger.info(
            "Found %d CRS reports (filtered from %d total, cutoff %s)",
            len(filtered),
            len(reports),
            cutoff.isoformat(),
        )
        return filtered

    async def _fetch_report_detail(self, report_number: str) -> dict | None:
        """Fetch full metadata for a single CRS report."""
        url = f"{EVERYCRS_BASE}/reports/{report_number}.json"
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.warning("Failed to fetch CRS report %s: %s", report_number, e)
            return None

    async def _upsert_report(self, detail: dict) -> bool:
        """Insert or update a CRS report from the detail JSON. Returns True if created."""
        report_number = detail.get("number") or detail.get("id", "")
        if not report_number:
            return False

        title = detail.get("title", "Untitled CRS Report")
        summary = detail.get("summary") or detail.get("abstract")

        # Authors: EveryCRS returns list of dicts with "name" key, or plain strings
        raw_authors = detail.get("authors", [])
        authors: list[str] = []
        for a in raw_authors:
            if isinstance(a, dict):
                name = a.get("name", "")
                if name:
                    authors.append(name)
            elif isinstance(a, str) and a:
                authors.append(a)

        # Topics
        topics: list[str] = []
        for t in detail.get("topics", []):
            if isinstance(t, dict):
                name = t.get("name", "")
                if name:
                    topics.append(name)
            elif isinstance(t, str) and t:
                topics.append(t)

        # Dates
        versions = detail.get("versions", [])
        pub_date = _parse_date(detail.get("firstVersionDate") or detail.get("date"))
        most_recent = _parse_date(detail.get("latestPubDate") or detail.get("date"))

        # If versions available, extract dates from them
        if versions:
            version_dates = [_parse_date(v.get("date")) for v in versions]
            valid_dates = [d for d in version_dates if d is not None]
            if valid_dates:
                pub_date = pub_date or min(valid_dates)
                most_recent = most_recent or max(valid_dates)

        # URLs
        source_url = f"{EVERYCRS_BASE}/reports/{report_number}.html"
        pdf_url = None
        if versions:
            # Get latest version's PDF
            for fmt in versions[-1].get("formats", []):
                if isinstance(fmt, dict) and fmt.get("format") == "PDF":
                    pdf_url = fmt.get("url")
                    break

        # Extract bill references from title + summary
        search_text = f"{title} {summary or ''}"
        bill_refs = extract_bill_references(search_text)

        stmt = pg_insert(CrsReport).values(
            id=report_number,
            title=title,
            summary=summary,
            authors=authors or None,
            topics=topics or None,
            publication_date=pub_date,
            most_recent_date=most_recent,
            source_url=source_url,
            pdf_url=pdf_url,
            related_bill_ids=bill_refs or None,
            created_at=datetime.now(tz=UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "title": title,
                "summary": summary,
                "authors": authors or None,
                "topics": topics or None,
                "publication_date": pub_date,
                "most_recent_date": most_recent,
                "source_url": source_url,
                "pdf_url": pdf_url,
                "related_bill_ids": bill_refs or None,
                "updated_at": datetime.now(tz=UTC),
            },
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    def _cutoff_date(self) -> date:
        """Calculate the cutoff date for filtering reports."""
        now = datetime.now(tz=UTC)
        year = now.year
        month = now.month - self.months_back
        while month <= 0:
            month += 12
            year -= 1
        return date(year, month, 1)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
