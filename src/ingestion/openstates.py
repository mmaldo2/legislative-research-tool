"""Open States / Plural Policy state bill ingester.

Fetches bill data from the Open States v3 API.
Primary source for state legislation.
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
from src.ingestion.normalizer import (
    generate_bill_id,
    generate_text_id,
    normalize_bill_status,
)
from src.models.bill import Bill
from src.models.bill_action import BillAction
from src.models.bill_text import BillText
from src.models.jurisdiction import Jurisdiction
from src.models.person import Person
from src.models.session import LegislativeSession
from src.models.sponsorship import Sponsorship

logger = logging.getLogger(__name__)

# State abbreviation to jurisdiction ID mapping
STATE_JURISDICTIONS = {
    "al": ("us-al", "Alabama"), "ak": ("us-ak", "Alaska"),
    "az": ("us-az", "Arizona"), "ar": ("us-ar", "Arkansas"),
    "ca": ("us-ca", "California"), "co": ("us-co", "Colorado"),
    "ct": ("us-ct", "Connecticut"), "de": ("us-de", "Delaware"),
    "fl": ("us-fl", "Florida"), "ga": ("us-ga", "Georgia"),
    "hi": ("us-hi", "Hawaii"), "id": ("us-id", "Idaho"),
    "il": ("us-il", "Illinois"), "in": ("us-in", "Indiana"),
    "ia": ("us-ia", "Iowa"), "ks": ("us-ks", "Kansas"),
    "ky": ("us-ky", "Kentucky"), "la": ("us-la", "Louisiana"),
    "me": ("us-me", "Maine"), "md": ("us-md", "Maryland"),
    "ma": ("us-ma", "Massachusetts"), "mi": ("us-mi", "Michigan"),
    "mn": ("us-mn", "Minnesota"), "ms": ("us-ms", "Mississippi"),
    "mo": ("us-mo", "Missouri"), "mt": ("us-mt", "Montana"),
    "ne": ("us-ne", "Nebraska"), "nv": ("us-nv", "Nevada"),
    "nh": ("us-nh", "New Hampshire"), "nj": ("us-nj", "New Jersey"),
    "nm": ("us-nm", "New Mexico"), "ny": ("us-ny", "New York"),
    "nc": ("us-nc", "North Carolina"), "nd": ("us-nd", "North Dakota"),
    "oh": ("us-oh", "Ohio"), "ok": ("us-ok", "Oklahoma"),
    "or": ("us-or", "Oregon"), "pa": ("us-pa", "Pennsylvania"),
    "ri": ("us-ri", "Rhode Island"), "sc": ("us-sc", "South Carolina"),
    "sd": ("us-sd", "South Dakota"), "tn": ("us-tn", "Tennessee"),
    "tx": ("us-tx", "Texas"), "ut": ("us-ut", "Utah"),
    "vt": ("us-vt", "Vermont"), "va": ("us-va", "Virginia"),
    "wa": ("us-wa", "Washington"), "wv": ("us-wv", "West Virginia"),
    "wi": ("us-wi", "Wisconsin"), "wy": ("us-wy", "Wyoming"),
    "dc": ("us-dc", "District of Columbia"),
    "pr": ("us-pr", "Puerto Rico"),
}


class OpenStatesIngester(BaseIngester):
    source_name = "openstates"

    def __init__(
        self,
        session: AsyncSession,
        states: list[str] | None = None,
    ):
        super().__init__(session)
        self.states = states or ["ca", "tx", "ny"]  # pilot states
        self.client = httpx.AsyncClient(
            base_url=settings.openstates_api_url,
            timeout=60.0,
            headers={"X-API-KEY": settings.openstates_api_key},
        )

    async def ingest(self) -> None:
        """Ingest state bills from Open States API."""
        await self.start_run("full")
        bills_created = 0
        bills_updated = 0

        try:
            for state_abbr in self.states:
                state_abbr = state_abbr.lower()
                if state_abbr not in STATE_JURISDICTIONS:
                    logger.warning(f"Unknown state abbreviation: {state_abbr}")
                    continue

                jur_id, jur_name = STATE_JURISDICTIONS[state_abbr]
                await self._ensure_jurisdiction(jur_id, jur_name, state_abbr.upper())

                created, updated = await self._fetch_state_bills(state_abbr, jur_id)
                bills_created += created
                bills_updated += updated
                logger.info(
                    f"Completed {state_abbr.upper()}: {created} created, {updated} updated"
                )

            if self.run:
                self.run.bills_created = bills_created
                self.run.bills_updated = bills_updated
            await self.finish_run("completed")
        except Exception as e:
            logger.error(f"Open States ingestion failed: {e}")
            await self.finish_run("failed")
            raise

    async def _ensure_jurisdiction(
        self, jur_id: str, name: str, abbreviation: str
    ) -> None:
        result = await self.session.execute(
            select(Jurisdiction).where(Jurisdiction.id == jur_id)
        )
        if not result.scalar_one_or_none():
            self.session.add(
                Jurisdiction(
                    id=jur_id,
                    name=name,
                    classification="state",
                    abbreviation=abbreviation,
                )
            )
            await self.session.flush()

    async def _fetch_state_bills(
        self, state_abbr: str, jurisdiction_id: str
    ) -> tuple[int, int]:
        """Fetch bills for a state from Open States API. Returns (created, updated)."""
        created = 0
        updated = 0
        page = 1
        per_page = 20

        # Map Open States jurisdiction format
        os_jurisdiction = f"ocd-jurisdiction/country:us/state:{state_abbr}/government"

        while True:
            try:
                resp = await self.client.get(
                    "/bills",
                    params={
                        "jurisdiction": os_jurisdiction,
                        "page": page,
                        "per_page": per_page,
                    },
                )
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.error(f"Open States API error for {state_abbr} page {page}: {e}")
                break

            data = resp.json()
            results = data.get("results", [])
            if not results:
                break

            for bill_data in results:
                was_created = await self._upsert_bill(bill_data, jurisdiction_id)
                if was_created:
                    created += 1
                else:
                    updated += 1

            await self.session.commit()

            # Check pagination
            pagination = data.get("pagination", {})
            if page >= pagination.get("max_page", 1):
                break
            page += 1

        return created, updated

    async def _upsert_bill(self, bill_data: dict, jurisdiction_id: str) -> bool:
        """Insert or update a bill from Open States response. Returns True if created."""
        identifier = bill_data.get("identifier", "")
        os_session = bill_data.get("session", "")
        title = bill_data.get("title", "No title")
        openstates_id = bill_data.get("id", "")

        # Ensure session exists
        session_id = f"{jurisdiction_id}-{os_session}"
        result = await self.session.execute(
            select(LegislativeSession).where(LegislativeSession.id == session_id)
        )
        if not result.scalar_one_or_none():
            self.session.add(
                LegislativeSession(
                    id=session_id,
                    jurisdiction_id=jurisdiction_id,
                    name=os_session,
                    identifier=os_session,
                    classification="primary",
                )
            )
            await self.session.flush()

        bill_id = generate_bill_id(jurisdiction_id, session_id, identifier)

        # Classification
        classification = bill_data.get("classification", [])
        subject = bill_data.get("subject", [])

        # Determine status from latest action
        actions = bill_data.get("latest_action_description", "")
        status = normalize_bill_status(actions) if actions else "introduced"

        stmt = pg_insert(Bill).values(
            id=bill_id,
            jurisdiction_id=jurisdiction_id,
            session_id=session_id,
            identifier=identifier,
            title=title,
            classification=classification or None,
            subject=subject or None,
            status=status,
            openstates_id=openstates_id,
            source_urls=bill_data.get("sources", []),
            last_ingested_at=datetime.now(tz=UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "title": title,
                "status": status,
                "subject": subject or None,
                "last_ingested_at": datetime.now(tz=UTC),
            },
        )
        result = await self.session.execute(stmt)
        was_created = result.rowcount > 0

        # Fetch full bill detail for texts, actions, sponsors
        await self._fetch_bill_detail(openstates_id, bill_id)

        return was_created

    async def _fetch_bill_detail(self, openstates_id: str, bill_id: str) -> None:
        """Fetch full bill detail including texts, actions, and sponsors."""
        if not openstates_id:
            return

        try:
            resp = await self.client.get(
                f"/bills/{openstates_id}",
                params={"include": "abstracts,actions,sponsorships,versions"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch bill detail {openstates_id}: {e}")
            return

        detail = resp.json()

        # Process text versions
        for version in detail.get("versions", []):
            version_name = version.get("note", "Unknown")
            text_id = generate_text_id(bill_id, version_name)

            existing = await self.session.execute(
                select(BillText).where(BillText.id == text_id)
            )
            if existing.scalar_one_or_none():
                continue

            # Get the first URL that looks like text
            links = version.get("links", [])
            source_url = links[0].get("url", "") if links else ""

            self.session.add(
                BillText(
                    id=text_id,
                    bill_id=bill_id,
                    version_name=version_name,
                    source_url=source_url,
                )
            )

        # Process actions
        for i, action in enumerate(detail.get("actions", [])):
            action_date_str = action.get("date", "")
            description = action.get("description", "")
            if not action_date_str or not description:
                continue

            try:
                action_date = date.fromisoformat(action_date_str[:10])
            except ValueError:
                continue

            existing = await self.session.execute(
                select(BillAction).where(
                    BillAction.bill_id == bill_id,
                    BillAction.action_date == action_date,
                    BillAction.description == description,
                )
            )
            if not existing.scalar_one_or_none():
                classification = action.get("classification", [])
                self.session.add(
                    BillAction(
                        bill_id=bill_id,
                        action_date=action_date,
                        description=description,
                        classification=classification or None,
                        chamber=action.get("organization", {}).get(
                            "classification", None
                        ),
                        action_order=i,
                    )
                )

        # Process sponsors
        for sponsor_data in detail.get("sponsorships", []):
            person_name = sponsor_data.get("name", "")
            if not person_name:
                continue

            person_id = sponsor_data.get("person", {}).get("id", "")
            if not person_id:
                # Generate a stable ID from name + jurisdiction
                person_id = hashlib.sha256(person_name.encode()).hexdigest()[:16]

            # Ensure person exists
            existing = await self.session.execute(
                select(Person).where(Person.id == person_id)
            )
            if not existing.scalar_one_or_none():
                self.session.add(
                    Person(
                        id=person_id,
                        name=person_name,
                        openstates_id=sponsor_data.get("person", {}).get("id"),
                    )
                )
                await self.session.flush()

            # Add sponsorship
            classification = sponsor_data.get("classification", "cosponsor")
            existing_sp = await self.session.execute(
                select(Sponsorship).where(
                    Sponsorship.bill_id == bill_id,
                    Sponsorship.person_id == person_id,
                    Sponsorship.classification == classification,
                )
            )
            if not existing_sp.scalar_one_or_none():
                self.session.add(
                    Sponsorship(
                        bill_id=bill_id,
                        person_id=person_id,
                        classification=classification,
                    )
                )

    async def close(self) -> None:
        await self.client.aclose()
