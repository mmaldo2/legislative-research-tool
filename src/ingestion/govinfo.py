"""GovInfo.gov federal bill ingester.

Fetches bill status and text from GovInfo's bulk data and API.
Primary source for federal legislation.
"""

import asyncio
import hashlib
import logging
import random
import re
from datetime import UTC, date, datetime

import defusedxml.ElementTree as SafeET
import httpx
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
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
from src.models.person import Person
from src.models.session import LegislativeSession
from src.models.sponsorship import Sponsorship

logger = logging.getLogger(__name__)

# Congress.gov API base
CONGRESS_API_BASE = "https://api.congress.gov/v3"

# GovInfo bulk data base
GOVINFO_BULK_BASE = "https://www.govinfo.gov/bulkdata"

# All federal bill types for bulk ingestion
BILL_TYPES = ["hr", "s", "hres", "sres", "hjres", "sjres", "hconres", "sconres"]

# Congress start/end dates for historical sessions
CONGRESS_DATES: dict[int, tuple[str, str]] = {
    110: ("2007-01-04", "2009-01-03"),
    111: ("2009-01-06", "2011-01-03"),
    112: ("2011-01-05", "2013-01-03"),
    113: ("2013-01-03", "2015-01-03"),
    114: ("2015-01-06", "2017-01-03"),
    115: ("2017-01-03", "2019-01-03"),
    116: ("2019-01-03", "2021-01-03"),
    117: ("2021-01-03", "2023-01-03"),
    118: ("2023-01-03", "2025-01-03"),
    119: ("2025-01-03", "2027-01-03"),
}


# Status precedence for determining best status from full action history.
# Higher value = more advanced in the legislative process.
STATUS_PRECEDENCE: dict[str, int] = {
    "introduced": 0,
    "other": 0,
    "in_committee": 1,
    "failed": 1,
    "withdrawn": 1,
    "passed_lower": 2,
    "passed_upper": 3,
    "enrolled": 4,
    "enacted": 5,
    "vetoed": 5,
}


def _parse_bill_type_number(congress_bill_id: str) -> tuple[str, str]:
    """Parse bill type and number from congress_bill_id (e.g., 'hr1234-118' -> ('hr', '1234'))."""
    stem = congress_bill_id.rsplit("-", 1)[0]  # "hr1234"
    # Split at the boundary between letters and digits
    match = re.match(r"^([a-z]+)(\d+)$", stem)
    if match:
        return match.group(1), match.group(2)
    return stem, ""


class GovInfoIngester(BaseIngester):
    source_name = "govinfo"

    def __init__(self, session: AsyncSession, congress: int = 119):
        super().__init__(session)
        self.congress = congress
        self.client = httpx.AsyncClient(timeout=60.0)

    async def ingest(self, enrich: bool = True) -> None:
        """Ingest federal bills from Congress.gov API + GovInfo.

        If enrich=True (default), also fetches per-bill details (actions,
        cosponsors) for bills missing action history.
        """
        await self.start_run("full")
        try:
            await self._ensure_jurisdiction()
            await self._ensure_session()
            await self._fetch_bills_from_congress_api()
            if enrich:
                await self.enrich_bills()
            await self.finish_run("completed")
        except Exception as e:
            logger.error("GovInfo ingestion failed: %s", e)
            await self.finish_run("failed")
            raise

    async def _ensure_jurisdiction(self) -> None:
        """Ensure the 'us' federal jurisdiction exists (idempotent upsert)."""
        stmt = pg_insert(Jurisdiction).values(
            id="us",
            name="United States",
            classification="country",
            abbreviation="US",
        )
        stmt = stmt.on_conflict_do_nothing()
        await self.session.execute(stmt)
        await self.session.flush()

    async def _ensure_session(self) -> None:
        """Ensure the Congress session exists with start/end dates."""
        session_id = f"us-{self.congress}"
        dates = CONGRESS_DATES.get(self.congress)
        start_date = date.fromisoformat(dates[0]) if dates else None
        end_date = date.fromisoformat(dates[1]) if dates else None

        stmt = pg_insert(LegislativeSession).values(
            id=session_id,
            jurisdiction_id="us",
            name=f"{self.congress}th Congress",
            identifier=str(self.congress),
            classification="primary",
            start_date=start_date,
            end_date=end_date,
        )
        # Only overwrite dates when we have values — avoid erasing data from other ingesters
        if start_date is not None:
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={"start_date": start_date, "end_date": end_date},
            )
        else:
            stmt = stmt.on_conflict_do_nothing()
        await self.session.execute(stmt)
        await self.session.flush()

    async def _rate_limited_get(
        self, url: str, params: dict | None = None, max_retries: int = 3
    ) -> httpx.Response:
        """HTTP GET with exponential backoff and 429 handling.

        429 responses do NOT count against the retry budget — they signal
        rate limiting, not failure.
        """
        failures = 0
        while True:
            try:
                resp = await self.client.get(url, params=params, follow_redirects=True)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    logger.warning("Rate limited, waiting %ds", retry_after)
                    await asyncio.sleep(retry_after + random.uniform(0, 5))
                    continue  # Do NOT increment failures
                resp.raise_for_status()
                return resp
            except httpx.HTTPError:
                failures += 1
                if failures >= max_retries:
                    raise
                wait = 2**failures + random.uniform(0, 1)
                logger.warning(
                    "Request failed, retrying in %.1fs (%d/%d)", wait, failures, max_retries
                )
                await asyncio.sleep(wait)

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
                resp = await self._rate_limited_get(url, params=params)
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

        # Extract introduced date from API response
        introduced_date_str = bill_data.get("introducedDate")
        introduced_date = None
        if introduced_date_str:
            try:
                introduced_date = date.fromisoformat(introduced_date_str)
            except ValueError:
                pass

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
            introduced_date=introduced_date,
            congress_bill_id=congress_bill_id,
            source_urls=[bill_data.get("url", "")],
            last_ingested_at=datetime.now(tz=UTC),
        )
        update_set: dict = {
            "title": title,
            "status": status,
            "last_ingested_at": datetime.now(tz=UTC),
        }
        if introduced_date is not None:
            update_set["introduced_date"] = introduced_date
        stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_set)
        result = await self.session.execute(stmt)

        # Track changes
        await self._track_changes(bill_id, old_values, {"title": title, "status": status})

        return result.rowcount > 0

    async def _fetch_bills_from_govinfo_bulk(self) -> None:
        """Fallback: fetch bill status from GovInfo bulk XML for all bill types."""
        session_id = f"us-{self.congress}"
        total_count = 0

        for bill_type in BILL_TYPES:
            url = f"{GOVINFO_BULK_BASE}/BILLSTATUS/{self.congress}/{bill_type}"
            logger.info("Fetching GovInfo bulk %s from %s", bill_type, url)

            try:
                resp = await self._rate_limited_get(url)
            except httpx.HTTPError as e:
                logger.warning("GovInfo bulk fetch failed for %s: %s", bill_type, e)
                continue

            try:
                root = SafeET.fromstring(resp.text)
            except SafeET.ParseError as e:
                logger.error("Failed to parse GovInfo bulk XML for %s: %s", bill_type, e)
                continue

            # Process each bill status XML link from the sitemap
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            count = 0

            for loc in root.findall(".//sm:loc", ns):
                bill_url = loc.text
                if not bill_url or not bill_url.endswith(".xml"):
                    continue

                try:
                    bill_resp = await self._rate_limited_get(bill_url)
                    await self._parse_bill_status_xml(bill_resp.text, session_id, bill_url)
                    count += 1
                    if count % 50 == 0:
                        await self.session.commit()
                        logger.info("Processed %d %s bill status XMLs", count, bill_type)
                except Exception as e:
                    logger.warning("Failed to process %s: %s", bill_url, e)

            await self.session.commit()
            logger.info("Completed %s bulk ingestion: %d bills", bill_type, count)
            total_count += count

        logger.info("Total GovInfo bulk ingestion: %d bills across all types", total_count)

    async def _parse_bill_status_xml(
        self, xml_text: str, session_id: str, source_url: str
    ) -> None:
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

        # Derive introduced_date from XML element or first action
        introduced_date = None
        intro_date_str = bill_el.findtext("introducedDate")
        if intro_date_str:
            try:
                introduced_date = date.fromisoformat(intro_date_str)
            except ValueError:
                pass
        if not introduced_date and actions_data:
            try:
                introduced_date = date.fromisoformat(actions_data[0]["date"])
            except ValueError:
                pass

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
            introduced_date=introduced_date,
            congress_bill_id=f"{bill_type}{bill_number}-{self.congress}",
            govinfo_package_id=source_url.split("/")[-1].replace(".xml", ""),
            source_urls=[source_url],
            last_ingested_at=datetime.now(tz=UTC),
        )
        update_set: dict = {
            "title": title,
            "status": status,
            "subject": subjects or None,
            "last_ingested_at": datetime.now(tz=UTC),
        }
        if introduced_date is not None:
            update_set["introduced_date"] = introduced_date
        stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_set)
        await self.session.execute(stmt)

        # Track changes
        await self._track_changes(
            bill_id, old_values, {"title": title, "status": status, "subject": subjects}
        )

        # Bulk upsert actions (1 query instead of N SELECT-before-INSERTs)
        action_values = []
        for i, action in enumerate(actions_data):
            try:
                action_date = date.fromisoformat(action["date"])
            except ValueError:
                continue
            action_values.append(
                {
                    "bill_id": bill_id,
                    "action_date": action_date,
                    "description": action["text"],
                    "action_order": i,
                }
            )
        if action_values:
            action_stmt = pg_insert(BillAction).values(action_values)
            action_stmt = action_stmt.on_conflict_do_nothing(
                index_elements=["bill_id", "action_date", "description"],
            )
            await self.session.execute(action_stmt)

        # Extract and bulk upsert sponsors/cosponsors
        await self._upsert_sponsors_from_xml(bill_el, bill_id)

    async def _upsert_sponsors_from_xml(self, bill_el, bill_id: str) -> None:
        """Extract sponsors and cosponsors from BILLSTATUS XML and bulk upsert."""
        person_values = []
        sponsorship_values = []

        for sponsor_el in bill_el.findall(".//sponsors/item"):
            pv, sv = self._extract_sponsor_values(sponsor_el, bill_id, "primary")
            if pv:
                person_values.append(pv)
                sponsorship_values.append(sv)

        for cosponsor_el in bill_el.findall(".//cosponsors/item"):
            pv, sv = self._extract_sponsor_values(cosponsor_el, bill_id, "cosponsor")
            if pv:
                person_values.append(pv)
                sponsorship_values.append(sv)

        # Bulk upsert persons (1 query for all sponsors of this bill)
        # Use COALESCE to avoid overwriting existing party with NULL
        if person_values:
            stmt = pg_insert(Person).values(person_values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": stmt.excluded.name,
                    "party": func.coalesce(stmt.excluded.party, Person.party),
                },
            )
            await self.session.execute(stmt)

        # Bulk insert sponsorships (1 query for all sponsors of this bill)
        if sponsorship_values:
            sp_stmt = pg_insert(Sponsorship).values(sponsorship_values)
            sp_stmt = sp_stmt.on_conflict_do_nothing(
                index_elements=["bill_id", "person_id", "classification"],
            )
            await self.session.execute(sp_stmt)

    @staticmethod
    def _extract_sponsor_values(
        el, bill_id: str, classification: str
    ) -> tuple[dict | None, dict | None]:
        """Extract Person + Sponsorship values from an XML element."""
        bioguide = el.findtext("bioguideId") or ""
        first_name = el.findtext("firstName") or ""
        last_name = el.findtext("lastName") or ""
        full_name = el.findtext("fullName") or f"{first_name} {last_name}".strip()
        party = el.findtext("party")

        if not full_name:
            return None, None

        # Use bioguide_id as Person primary key (matching congress_legislators pattern).
        # Fall back to hash-based ID if bioguide is missing.
        if bioguide:
            person_id = bioguide
        else:
            person_id = hashlib.sha256(full_name.encode()).hexdigest()[:16]

        person_dict = {
            "id": person_id,
            "name": full_name,
            "sort_name": last_name or full_name,
            "party": party,
            "bioguide_id": bioguide or None,
        }
        sponsorship_dict = {
            "bill_id": bill_id,
            "person_id": person_id,
            "classification": classification,
        }
        return person_dict, sponsorship_dict

    # ------------------------------------------------------------------
    # Per-bill detail enrichment (actions + cosponsors from detail API)
    # ------------------------------------------------------------------

    async def enrich_bills(self, batch_size: int = 50) -> None:
        """Fetch per-bill details for bills missing action history.

        This is a second pass after the list fetch. Bills that already have
        actions in bill_actions are skipped (resumability).
        """
        if not settings.congress_api_key:
            logger.warning("Cannot enrich without CONGRESS_API_KEY")
            return

        session_id = f"us-{self.congress}"

        # Find bills needing enrichment: bills in this session with no actions
        enriched_bill_ids = select(BillAction.bill_id).distinct()
        stmt = (
            select(Bill.id, Bill.congress_bill_id)
            .where(Bill.session_id == session_id)
            .where(Bill.congress_bill_id.is_not(None))
            .where(~Bill.id.in_(enriched_bill_ids))
        )
        result = await self.session.execute(stmt)
        bills_to_enrich = result.all()

        total = len(bills_to_enrich)
        if total == 0:
            logger.info("All bills for Congress %d already enriched", self.congress)
            return

        logger.info("Enriching %d bills for Congress %d", total, self.congress)
        enriched = 0

        for i in range(0, total, batch_size):
            batch = bills_to_enrich[i : i + batch_size]
            for bill_id, congress_bill_id in batch:
                bill_type, bill_number = _parse_bill_type_number(congress_bill_id)
                if not bill_number:
                    continue
                await self._fetch_bill_actions(bill_id, bill_type, bill_number)
                await self._fetch_bill_cosponsors(bill_id, bill_type, bill_number)
                enriched += 1

            await self.session.commit()
            done = min(i + batch_size, total)
            logger.info("Enriched %d/%d bills", done, total)

        logger.info(
            "Enrichment complete: %d bills enriched for Congress %d", enriched, self.congress
        )

    async def _fetch_bill_actions(
        self, bill_id: str, bill_type: str, bill_number: str
    ) -> None:
        """Fetch full action history for a bill and update status."""
        url = f"{CONGRESS_API_BASE}/bill/{self.congress}/{bill_type}/{bill_number}/actions"
        params = {
            "api_key": settings.congress_api_key,
            "limit": 250,
            "format": "json",
        }

        try:
            resp = await self._rate_limited_get(url, params=params)
        except httpx.HTTPError:
            logger.warning("Failed to fetch actions for %s/%s", bill_type, bill_number)
            return

        data = resp.json()
        actions = data.get("actions", [])
        if not actions:
            return

        # Build action values and track best status
        action_values = []
        best_status = "introduced"
        for i, action in enumerate(actions):
            action_date_str = action.get("actionDate")
            action_text = action.get("text", "")
            if not action_date_str or not action_text:
                continue
            try:
                action_date = date.fromisoformat(action_date_str)
            except ValueError:
                continue

            action_values.append(
                {
                    "bill_id": bill_id,
                    "action_date": action_date,
                    "description": action_text,
                    "action_order": i,
                    "chamber": action.get("sourceSystem", {}).get("name", ""),
                }
            )

            # Track highest-precedence status from all actions
            action_status = normalize_bill_status(action_text)
            if STATUS_PRECEDENCE.get(action_status, 0) > STATUS_PRECEDENCE.get(
                best_status, 0
            ):
                best_status = action_status

        # Bulk upsert actions
        if action_values:
            stmt = pg_insert(BillAction).values(action_values)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["bill_id", "action_date", "description"],
            )
            await self.session.execute(stmt)

        # Update bill status from full action history
        await self.session.execute(
            sa_update(Bill).where(Bill.id == bill_id).values(status=best_status)
        )

    async def _fetch_bill_cosponsors(
        self, bill_id: str, bill_type: str, bill_number: str
    ) -> None:
        """Fetch cosponsors from Congress.gov detail endpoint and bulk upsert."""
        url = (
            f"{CONGRESS_API_BASE}/bill/{self.congress}/{bill_type}/{bill_number}/cosponsors"
        )
        params = {
            "api_key": settings.congress_api_key,
            "limit": 250,
            "format": "json",
        }

        try:
            resp = await self._rate_limited_get(url, params=params)
        except httpx.HTTPError:
            logger.warning("Failed to fetch cosponsors for %s/%s", bill_type, bill_number)
            return

        data = resp.json()
        cosponsors = data.get("cosponsors", [])
        if not cosponsors:
            return

        person_values = []
        sponsorship_values = []

        for cosponsor in cosponsors:
            bioguide = cosponsor.get("bioguideId", "")
            first_name = cosponsor.get("firstName", "")
            last_name = cosponsor.get("lastName", "")
            full_name = cosponsor.get("fullName", "") or f"{first_name} {last_name}".strip()
            party = cosponsor.get("party")

            if not full_name:
                continue

            person_id = bioguide if bioguide else hashlib.sha256(
                full_name.encode()
            ).hexdigest()[:16]

            person_values.append(
                {
                    "id": person_id,
                    "name": full_name,
                    "sort_name": last_name or full_name,
                    "party": party,
                    "bioguide_id": bioguide or None,
                }
            )
            sponsorship_values.append(
                {
                    "bill_id": bill_id,
                    "person_id": person_id,
                    "classification": "cosponsor",
                }
            )

        if person_values:
            stmt = pg_insert(Person).values(person_values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": stmt.excluded.name,
                    "party": func.coalesce(stmt.excluded.party, Person.party),
                },
            )
            await self.session.execute(stmt)

        if sponsorship_values:
            sp_stmt = pg_insert(Sponsorship).values(sponsorship_values)
            sp_stmt = sp_stmt.on_conflict_do_nothing(
                index_elements=["bill_id", "person_id", "classification"],
            )
            await self.session.execute(sp_stmt)

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
