"""GovInfo.gov federal bill ingester.

Fetches bill status and text from GovInfo's bulk data and API.
Primary source for federal legislation.
"""

import logging
import re
from datetime import UTC, date, datetime

import defusedxml.ElementTree as SafeET
import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseIngester
from src.ingestion.normalizer import (
    content_hash,
    generate_bill_id,
    generate_text_id,
    normalize_bill_status,
    normalize_identifier,
    word_count,
)
from src.models.bill import Bill
from src.models.bill_action import BillAction
from src.models.bill_text import BillText
from src.models.jurisdiction import Jurisdiction
from src.models.session import LegislativeSession

logger = logging.getLogger(__name__)

# Congress.gov API base
CONGRESS_API_BASE = "https://api.congress.gov/v3"

# GovInfo bulk data base
GOVINFO_BULK_BASE = "https://www.govinfo.gov/bulkdata"


class GovInfoIngester(BaseIngester):
    source_name = "govinfo"

    def __init__(self, session: AsyncSession, congress: int = 119):
        super().__init__(session)
        self.congress = congress
        self.client = httpx.AsyncClient(timeout=60.0)

    async def ingest(self) -> None:
        """Ingest federal bills from Congress.gov API + GovInfo."""
        await self.start_run("full")
        try:
            await self._ensure_jurisdiction()
            await self._ensure_session()
            await self._fetch_bills_from_congress_api()
            await self.finish_run("completed")
        except Exception as e:
            logger.error("GovInfo ingestion failed: %s", e)
            await self.finish_run("failed")
            raise

    async def _ensure_jurisdiction(self) -> None:
        """Ensure the 'us' federal jurisdiction exists."""
        result = await self.session.execute(select(Jurisdiction).where(Jurisdiction.id == "us"))
        if not result.scalar_one_or_none():
            self.session.add(
                Jurisdiction(
                    id="us",
                    name="United States",
                    classification="country",
                    abbreviation="US",
                )
            )
            await self.session.flush()

    async def _ensure_session(self) -> None:
        """Ensure the current Congress session exists."""
        session_id = f"us-{self.congress}"
        result = await self.session.execute(
            select(LegislativeSession).where(LegislativeSession.id == session_id)
        )
        if not result.scalar_one_or_none():
            self.session.add(
                LegislativeSession(
                    id=session_id,
                    jurisdiction_id="us",
                    name=f"{self.congress}th Congress",
                    identifier=str(self.congress),
                    classification="primary",
                )
            )
            await self.session.flush()

    async def _fetch_bills_from_congress_api(self) -> None:
        """Fetch bills from Congress.gov API."""
        if not settings.congress_api_key:
            logger.warning("No CONGRESS_API_KEY set — using GovInfo bulk fallback")
            await self._fetch_bills_from_govinfo_bulk()
            return

        offset = 0
        limit = 250
        session_id = f"us-{self.congress}"
        bills_created = 0
        bills_updated = 0

        while True:
            url = f"{CONGRESS_API_BASE}/bill/{self.congress}"
            params = {
                "api_key": settings.congress_api_key,
                "offset": offset,
                "limit": limit,
                "format": "json",
            }

            try:
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.error("Congress API request failed at offset %d: %s", offset, e)
                break

            data = resp.json()
            bills = data.get("bills", [])
            if not bills:
                break

            # Batch-prefetch old values for this page (1 query instead of N)
            page_bill_ids = []
            for bd in bills:
                bt = bd.get("type", "").lower()
                bn = bd.get("number", "")
                ident = normalize_identifier(f"{bt}{bn}")
                page_bill_ids.append(generate_bill_id("us", session_id, ident))
            await self._prefetch_old_values(page_bill_ids)

            for bill_data in bills:
                created = await self._upsert_bill_from_congress_api(bill_data, session_id)
                if created:
                    bills_created += 1
                else:
                    bills_updated += 1

            await self.session.commit()
            logger.info("Processed %d federal bills", offset + len(bills))

            # Check for more pages
            pagination = data.get("pagination", {})
            if offset + limit >= pagination.get("count", 0):
                break
            offset += limit

        if self.run:
            self.run.records_created = bills_created
            self.run.records_updated = bills_updated

    async def _upsert_bill_from_congress_api(self, bill_data: dict, session_id: str) -> bool:
        """Insert or update a bill from Congress.gov API response. Returns True if created."""
        bill_type = bill_data.get("type", "").lower()
        bill_number = bill_data.get("number", "")
        identifier = normalize_identifier(f"{bill_type}{bill_number}")
        bill_id = generate_bill_id("us", session_id, identifier)

        congress_bill_id = f"{bill_type}{bill_number}-{self.congress}"
        title = bill_data.get("title", "No title")

        # Determine status from latest action
        latest_action = bill_data.get("latestAction", {})
        status_text = latest_action.get("text", "")
        status = normalize_bill_status(status_text) if status_text else "introduced"

        # Snapshot current values for change tracking
        old_values = await self._get_old_values(bill_id)

        stmt = pg_insert(Bill).values(
            id=bill_id,
            jurisdiction_id="us",
            session_id=session_id,
            identifier=identifier,
            title=title,
            classification=["bill"] if bill_type in ("hr", "s") else ["resolution"],
            status=status,
            congress_bill_id=congress_bill_id,
            source_urls=[bill_data.get("url", "")],
            last_ingested_at=datetime.now(tz=UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "title": title,
                "status": status,
                "last_ingested_at": datetime.now(tz=UTC),
            },
        )
        result = await self.session.execute(stmt)

        # Track changes
        await self._track_changes(bill_id, old_values, {"title": title, "status": status})

        return result.rowcount > 0

    async def _fetch_bills_from_govinfo_bulk(self) -> None:
        """Fallback: fetch bill status from GovInfo bulk XML."""
        # GovInfo BILLSTATUS bulk data endpoint
        url = f"{GOVINFO_BULK_BASE}/BILLSTATUS/{self.congress}/hr"
        logger.info("Fetching GovInfo bulk bill status from %s", url)

        try:
            resp = await self.client.get(url, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("GovInfo bulk fetch failed: %s", e)
            return

        # GovInfo returns an XML sitemap with links to individual bill status XMLs
        # Parse the sitemap to get individual bill URLs
        try:
            root = SafeET.fromstring(resp.text)
        except SafeET.ParseError as e:
            logger.error("Failed to parse GovInfo bulk XML: %s", e)
            return

        # Process each bill status XML link from the sitemap
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        session_id = f"us-{self.congress}"
        count = 0

        for loc in root.findall(".//sm:loc", ns):
            bill_url = loc.text
            if not bill_url or not bill_url.endswith(".xml"):
                continue

            try:
                bill_resp = await self.client.get(bill_url)
                bill_resp.raise_for_status()
                await self._parse_bill_status_xml(bill_resp.text, session_id, bill_url)
                count += 1
                if count % 50 == 0:
                    await self.session.commit()
                    logger.info("Processed %d bill status XMLs", count)
            except Exception as e:
                logger.warning("Failed to process %s: %s", bill_url, e)

        await self.session.commit()
        logger.info("Completed GovInfo bulk ingestion: %d bills", count)

    async def _parse_bill_status_xml(self, xml_text: str, session_id: str, source_url: str) -> None:
        """Parse a BILLSTATUS XML document and upsert the bill."""
        try:
            root = SafeET.fromstring(xml_text)
        except SafeET.ParseError:
            return

        bill_el = root.find(".//bill")
        if bill_el is None:
            return

        bill_type = (bill_el.findtext("billType") or "hr").lower()
        bill_number = bill_el.findtext("billNumber") or ""
        identifier = normalize_identifier(f"{bill_type}{bill_number}")
        bill_id = generate_bill_id("us", session_id, identifier)
        title = bill_el.findtext("title") or "No title"

        # Extract subjects
        subjects = []
        for subj in bill_el.findall(".//legislativeSubjects/item/name"):
            if subj.text:
                subjects.append(subj.text)

        # Extract actions
        actions_data = []
        for action_el in bill_el.findall(".//actions/item"):
            action_date_str = action_el.findtext("actionDate")
            action_text = action_el.findtext("text") or ""
            if action_date_str and action_text:
                actions_data.append(
                    {
                        "date": action_date_str,
                        "text": action_text,
                        "chamber": action_el.findtext("actionCode") or "",
                    }
                )

        # Determine status from latest action
        status = "introduced"
        if actions_data:
            latest = actions_data[-1]["text"]
            status = normalize_bill_status(latest)

        # Snapshot current values for change tracking
        old_values = await self._get_old_values(bill_id)

        # Upsert bill
        stmt = pg_insert(Bill).values(
            id=bill_id,
            jurisdiction_id="us",
            session_id=session_id,
            identifier=identifier,
            title=title,
            classification=["bill"] if bill_type in ("hr", "s") else ["resolution"],
            subject=subjects or None,
            status=status,
            congress_bill_id=f"{bill_type}{bill_number}-{self.congress}",
            govinfo_package_id=source_url.split("/")[-1].replace(".xml", ""),
            source_urls=[source_url],
            last_ingested_at=datetime.now(tz=UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "title": title,
                "status": status,
                "subject": subjects or None,
                "last_ingested_at": datetime.now(tz=UTC),
            },
        )
        await self.session.execute(stmt)

        # Track changes
        await self._track_changes(
            bill_id, old_values, {"title": title, "status": status, "subject": subjects}
        )

        # Upsert actions
        for i, action in enumerate(actions_data):
            try:
                action_date = date.fromisoformat(action["date"])
            except ValueError:
                continue

            existing = await self.session.execute(
                select(BillAction).where(
                    BillAction.bill_id == bill_id,
                    BillAction.action_date == action_date,
                    BillAction.description == action["text"],
                )
            )
            if not existing.scalar_one_or_none():
                self.session.add(
                    BillAction(
                        bill_id=bill_id,
                        action_date=action_date,
                        description=action["text"],
                        action_order=i,
                    )
                )

    async def fetch_bill_text(self, bill: Bill) -> BillText | None:
        """Fetch bill text from GovInfo for a specific bill."""
        if not bill.govinfo_package_id:
            return None

        url = f"https://api.govinfo.gov/packages/{bill.govinfo_package_id}/htm"
        params = {"api_key": settings.congress_api_key} if settings.congress_api_key else {}

        try:
            resp = await self.client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError:
            return None

        text_content = resp.text
        text_id = generate_text_id(bill.id, "latest")

        bill_text = BillText(
            id=text_id,
            bill_id=bill.id,
            version_name="Latest",
            content_html=text_content,
            content_text=_strip_html(text_content),
            source_url=url,
            word_count=word_count(_strip_html(text_content)),
            content_hash=content_hash(text_content),
        )
        return bill_text

    async def close(self) -> None:
        await self.client.aclose()


_RE_HTML_TAG = re.compile(r"<[^>]+>")
_RE_WHITESPACE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    """Basic HTML tag stripping."""
    clean = _RE_HTML_TAG.sub(" ", html)
    clean = _RE_WHITESPACE.sub(" ", clean).strip()
    return clean
