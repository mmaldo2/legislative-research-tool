"""Congress legislators ingester.

Imports legislator data from the unitedstates/congress-legislators
GitHub repository (YAML format). Populates the people table with
bioguide IDs, party, chamber, and district info.
"""

import logging

import httpx
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import BaseIngester
from src.models.person import Person

logger = logging.getLogger(__name__)

# Raw YAML URLs from unitedstates/congress-legislators
CURRENT_LEGISLATORS_URL = (
    "https://theunitedstates.io/congress-legislators/legislators-current.json"
)


class CongressLegislatorsIngester(BaseIngester):
    source_name = "congress_legislators"

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.client = httpx.AsyncClient(timeout=60.0)

    async def ingest(self) -> None:
        """Import current Congress legislators."""
        await self.start_run("full")
        created = 0
        updated = 0

        try:
            resp = await self.client.get(CURRENT_LEGISLATORS_URL, follow_redirects=True)
            resp.raise_for_status()
            legislators = resp.json()

            for leg in legislators:
                was_created = await self._upsert_legislator(leg)
                if was_created:
                    created += 1
                else:
                    updated += 1

            await self.session.commit()

            if self.run:
                self.run.records_created = created
                self.run.records_updated = updated
            await self.finish_run("completed")
            logger.info(
                "Congress legislators: %d created, %d updated", created, updated
            )
        except Exception as e:
            logger.error("Congress legislators ingestion failed: %s", e)
            await self.finish_run("failed")
            raise

    async def _upsert_legislator(self, leg: dict) -> bool:
        """Upsert a single legislator. Returns True if created."""
        bio_id = leg.get("id", {}).get("bioguide", "")
        if not bio_id:
            return False

        name = leg.get("name", {})
        full_name = name.get("official_full", "")
        if not full_name:
            first = name.get("first", "")
            last = name.get("last", "")
            full_name = f"{first} {last}".strip()

        sort_name = name.get("last", full_name)

        # Current term info
        terms = leg.get("terms", [])
        current_term = terms[-1] if terms else {}
        party = current_term.get("party", None)
        chamber_type = current_term.get("type", "")
        chamber = "upper" if chamber_type == "sen" else "lower"
        state = current_term.get("state", "")
        district = current_term.get("district", None)

        jurisdiction_id = f"us-{state.lower()}" if state else None

        stmt = (
            pg_insert(Person)
            .values(
                id=bio_id,
                name=full_name,
                sort_name=sort_name,
                party=party,
                current_jurisdiction_id=jurisdiction_id,
                current_chamber=chamber,
                current_district=str(district) if district else None,
                bioguide_id=bio_id,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": full_name,
                    "sort_name": sort_name,
                    "party": party,
                    "current_jurisdiction_id": jurisdiction_id,
                    "current_chamber": chamber,
                    "current_district": str(district) if district else None,
                },
            )
            .returning(Person.id, text("xmax"))
        )
        result = await self.session.execute(stmt)
        row = result.one()
        return row.xmax == 0  # xmax=0 means INSERT, xmax!=0 means UPDATE

    async def close(self) -> None:
        await self.client.aclose()
