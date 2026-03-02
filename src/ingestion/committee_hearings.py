"""Committee hearing ingester using Congress.gov API.

Fetches hearing data from the Congress.gov /hearing endpoint and upserts
into the committee_hearings table with optional bill linking.
"""

import hashlib
import logging
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseIngester
from src.models.bill import Bill
from src.models.committee_hearing import CommitteeHearing, HearingBillLink

logger = logging.getLogger(__name__)

CONGRESS_API_BASE = "https://api.congress.gov/v3"


def _generate_hearing_id(congress: int, chamber: str, jacket_number: str) -> str:
    """Generate a stable hearing ID from congress/chamber/jacket."""
    raw = f"hearing-{congress}-{chamber}-{jacket_number}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _normalize_chamber(chamber: str | None) -> str | None:
    """Normalize chamber string to lowercase canonical form."""
    if not chamber:
        return None
    lower = chamber.lower().strip()
    mapping = {
        "senate": "senate",
        "s": "senate",
        "house": "house",
        "h": "house",
        "joint": "joint",
        "house of representatives": "house",
    }
    return mapping.get(lower, lower)


class CommitteeHearingIngester(BaseIngester):
    """Ingester for committee hearing data from Congress.gov API."""

    source_name = "committee_hearings"

    def __init__(self, session: AsyncSession, congress: int = 119):
        super().__init__(session)
        self.congress = congress
        self.client = httpx.AsyncClient(timeout=60.0)

    async def ingest(self) -> None:
        """Ingest committee hearings from Congress.gov API."""
        await self.start_run("full")
        try:
            await self._fetch_hearings()
            await self.finish_run("completed")
        except Exception as e:
            logger.error("Committee hearings ingestion failed: %s", e)
            await self.finish_run("failed")
            raise

    async def _fetch_hearings(self) -> None:
        """Fetch hearings list from Congress.gov API and process each."""
        if not settings.congress_api_key:
            logger.warning("No CONGRESS_API_KEY set — cannot fetch hearings")
            return

        offset = 0
        limit = 250
        hearings_created = 0
        hearings_updated = 0

        while True:
            url = f"{CONGRESS_API_BASE}/hearing/{self.congress}"
            params: dict[str, str | int] = {
                "api_key": settings.congress_api_key,
                "offset": offset,
                "limit": limit,
                "format": "json",
            }

            try:
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.error("Congress API hearings request failed at offset %d: %s", offset, e)
                break

            data = resp.json()
            hearings = data.get("hearings", [])
            if not hearings:
                break

            for hearing_data in hearings:
                created = await self._upsert_hearing(hearing_data)
                if created:
                    hearings_created += 1
                else:
                    hearings_updated += 1

            await self.session.commit()
            logger.info(
                "Processed %d committee hearings (offset %d)",
                len(hearings),
                offset,
            )

            # Check for more pages
            pagination = data.get("pagination", {})
            total = pagination.get("count", 0)
            if offset + limit >= total:
                break
            offset += limit

        if self.run:
            self.run.records_created = hearings_created
            self.run.records_updated = hearings_updated

        logger.info(
            "Hearings ingestion complete: %d created, %d updated",
            hearings_created,
            hearings_updated,
        )

    async def _upsert_hearing(self, hearing_data: dict) -> bool:
        """Upsert a single hearing record. Returns True if newly created."""
        chamber = _normalize_chamber(hearing_data.get("chamber"))
        jacket_number = str(hearing_data.get("jacketNumber", hearing_data.get("number", "")))
        congress = hearing_data.get("congress", self.congress)

        hearing_id = _generate_hearing_id(congress, chamber or "unknown", jacket_number)

        # Parse hearing date
        hearing_date = self._parse_date(hearing_data.get("date"))

        # Build committee name from the data
        committee_raw = hearing_data.get("committee")
        if isinstance(committee_raw, str):
            committee_name = committee_raw
        elif isinstance(committee_raw, dict):
            committee_name = committee_raw.get("name", "Unknown Committee")
        else:
            committee_name = "Unknown Committee"

        committee_code = None
        if isinstance(hearing_data.get("committee"), dict):
            committee_code = hearing_data["committee"].get("systemCode")

        title = hearing_data.get("title", "Untitled Hearing")
        location = hearing_data.get("location")

        # Build URL from the hearing detail link
        hearing_url = hearing_data.get("url")
        if not hearing_url and hearing_data.get("detailUrl"):
            hearing_url = hearing_data["detailUrl"]

        stmt = pg_insert(CommitteeHearing).values(
            id=hearing_id,
            committee_name=committee_name,
            committee_code=committee_code,
            chamber=chamber,
            title=title,
            hearing_date=hearing_date,
            location=location,
            url=hearing_url,
            congress=congress,
            jacket_number=jacket_number,
            created_at=datetime.now(tz=UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "committee_name": committee_name,
                "committee_code": committee_code,
                "title": title,
                "hearing_date": hearing_date,
                "location": location,
                "url": hearing_url,
            },
        )
        result = await self.session.execute(stmt)
        created = result.rowcount > 0

        # Attempt to fetch hearing detail for bill associations
        await self._fetch_and_link_bills(hearing_id, congress, chamber or "", jacket_number)

        return created

    async def _fetch_and_link_bills(
        self,
        hearing_id: str,
        congress: int,
        chamber: str,
        jacket_number: str,
    ) -> None:
        """Fetch hearing detail to discover associated bills and create links."""
        if not jacket_number or not chamber:
            return

        # Map chamber name to API path
        chamber_path = {
            "senate": "senate",
            "house": "house",
            "joint": "joint",
        }.get(chamber, chamber)

        url = f"{CONGRESS_API_BASE}/hearing/{congress}/{chamber_path}/{jacket_number}"
        params: dict[str, str | int] = {
            "api_key": settings.congress_api_key,
            "format": "json",
        }

        try:
            resp = await self.client.get(url, params=params)
            if resp.status_code != 200:
                return
        except httpx.HTTPError:
            return

        detail = resp.json()
        hearing_detail = detail.get("hearing", {})

        # Look for associated bills in the detail response
        associated_bills = hearing_detail.get("associatedBills", [])
        if not associated_bills:
            associated_bills = hearing_detail.get("bills", [])

        for bill_ref in associated_bills:
            bill_type = (bill_ref.get("type", "") or "").lower()
            bill_number = str(bill_ref.get("number", ""))
            bill_congress = bill_ref.get("congress", congress)

            if not bill_type or not bill_number:
                continue

            # Try to find the bill in our database
            congress_bill_id = f"{bill_type}{bill_number}-{bill_congress}"
            result = await self.session.execute(
                select(Bill).where(Bill.congress_bill_id == congress_bill_id)
            )
            bill = result.scalar_one_or_none()
            if not bill:
                continue

            # Upsert the link
            link_stmt = pg_insert(HearingBillLink).values(
                hearing_id=hearing_id,
                bill_id=bill.id,
            )
            link_stmt = link_stmt.on_conflict_do_nothing(index_elements=["hearing_id", "bill_id"])
            await self.session.execute(link_stmt)

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        """Parse a date string from the API in various formats."""
        if not date_str:
            return None
        # Try ISO format first
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        # Try ISO parse as fallback
        try:
            return date.fromisoformat(date_str[:10])
        except ValueError:
            logger.warning("Could not parse hearing date: %s", date_str)
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
