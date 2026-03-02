"""LegiScan weekly dataset ingester.

Downloads and processes weekly bulk JSON datasets from LegiScan.
Cross-references bills against existing records and detects coverage gaps.
"""

import io
import json
import logging
import zipfile
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseIngester
from src.ingestion.normalizer import generate_bill_id, normalize_identifier
from src.models.bill import Bill
from src.models.jurisdiction import Jurisdiction
from src.models.session import LegislativeSession

logger = logging.getLogger(__name__)

# LegiScan dataset API
LEGISCAN_API_BASE = "https://api.legiscan.com"

# LegiScan numeric status code -> canonical status string
LEGISCAN_STATUS_MAP: dict[int, str] = {
    1: "introduced",
    2: "engrossed",
    3: "enrolled",
    4: "enacted",
    5: "vetoed",
    6: "failed",
}

# Two-letter state abbreviation -> (jurisdiction_id, jurisdiction_name)
STATE_JURISDICTIONS: dict[str, tuple[str, str]] = {
    "AL": ("us-al", "Alabama"),
    "AK": ("us-ak", "Alaska"),
    "AZ": ("us-az", "Arizona"),
    "AR": ("us-ar", "Arkansas"),
    "CA": ("us-ca", "California"),
    "CO": ("us-co", "Colorado"),
    "CT": ("us-ct", "Connecticut"),
    "DE": ("us-de", "Delaware"),
    "FL": ("us-fl", "Florida"),
    "GA": ("us-ga", "Georgia"),
    "HI": ("us-hi", "Hawaii"),
    "ID": ("us-id", "Idaho"),
    "IL": ("us-il", "Illinois"),
    "IN": ("us-in", "Indiana"),
    "IA": ("us-ia", "Iowa"),
    "KS": ("us-ks", "Kansas"),
    "KY": ("us-ky", "Kentucky"),
    "LA": ("us-la", "Louisiana"),
    "ME": ("us-me", "Maine"),
    "MD": ("us-md", "Maryland"),
    "MA": ("us-ma", "Massachusetts"),
    "MI": ("us-mi", "Michigan"),
    "MN": ("us-mn", "Minnesota"),
    "MS": ("us-ms", "Mississippi"),
    "MO": ("us-mo", "Missouri"),
    "MT": ("us-mt", "Montana"),
    "NE": ("us-ne", "Nebraska"),
    "NV": ("us-nv", "Nevada"),
    "NH": ("us-nh", "New Hampshire"),
    "NJ": ("us-nj", "New Jersey"),
    "NM": ("us-nm", "New Mexico"),
    "NY": ("us-ny", "New York"),
    "NC": ("us-nc", "North Carolina"),
    "ND": ("us-nd", "North Dakota"),
    "OH": ("us-oh", "Ohio"),
    "OK": ("us-ok", "Oklahoma"),
    "OR": ("us-or", "Oregon"),
    "PA": ("us-pa", "Pennsylvania"),
    "RI": ("us-ri", "Rhode Island"),
    "SC": ("us-sc", "South Carolina"),
    "SD": ("us-sd", "South Dakota"),
    "TN": ("us-tn", "Tennessee"),
    "TX": ("us-tx", "Texas"),
    "UT": ("us-ut", "Utah"),
    "VT": ("us-vt", "Vermont"),
    "VA": ("us-va", "Virginia"),
    "WA": ("us-wa", "Washington"),
    "WV": ("us-wv", "West Virginia"),
    "WI": ("us-wi", "Wisconsin"),
    "WY": ("us-wy", "Wyoming"),
    "DC": ("us-dc", "District of Columbia"),
    "PR": ("us-pr", "Puerto Rico"),
    "US": ("us", "United States"),
}


def map_legiscan_status(status_code: int) -> str:
    """Map a LegiScan numeric status code to a canonical status string."""
    return LEGISCAN_STATUS_MAP.get(status_code, "other")


def parse_legiscan_bill(raw: dict) -> dict | None:
    """Parse a single bill dict from LegiScan weekly dataset JSON.

    Returns a normalized dict ready for upsert, or None if the record is invalid.
    """
    bill_id = raw.get("bill_id")
    bill_number = raw.get("bill_number", "")
    state = raw.get("state", "")
    title = raw.get("title", "")

    if bill_id is None or not bill_number or not state:
        return None

    session_info = raw.get("session", {})
    session_name = session_info.get("session_name", "")
    session_id_num = session_info.get("session_id")

    status_code = raw.get("status", 0)
    status = map_legiscan_status(status_code)

    status_date_str = raw.get("status_date", "")
    status_date: date | None = None
    if status_date_str:
        try:
            status_date = date.fromisoformat(status_date_str)
        except ValueError:
            pass

    description = raw.get("description", "")
    url = raw.get("url", "")

    return {
        "legiscan_id": bill_id,
        "bill_number": bill_number,
        "state": state.upper(),
        "title": title,
        "description": description,
        "session_name": session_name,
        "session_id_num": session_id_num,
        "status": status,
        "status_code": status_code,
        "status_date": status_date,
        "url": url,
    }


def extract_bills_from_zip(zip_bytes: bytes) -> list[dict]:
    """Extract and parse bill JSON files from a LegiScan weekly dataset ZIP.

    The ZIP typically contains a directory structure like:
        <state_abbr>/<session>/bill/<bill_file>.json

    Each JSON file has a top-level "bill" key containing the bill data.
    """
    bills: list[dict] = []

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if not name.endswith(".json"):
                    continue
                # Skip non-bill files (e.g., people, votes, sessions metadata)
                name_lower = name.lower()
                if "/bill/" not in name_lower and "\\bill\\" not in name_lower:
                    # Also accept files at top level that look like bill data
                    if "people" in name_lower or "vote" in name_lower:
                        continue

                try:
                    raw_bytes = zf.read(name)
                    data = json.loads(raw_bytes)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Failed to parse %s in ZIP: %s", name, e)
                    continue

                # LegiScan wraps bill data in a top-level "bill" key
                bill_raw = data.get("bill", data)
                parsed = parse_legiscan_bill(bill_raw)
                if parsed:
                    bills.append(parsed)
    except zipfile.BadZipFile:
        logger.error("Downloaded file is not a valid ZIP archive")

    return bills


class LegiScanIngester(BaseIngester):
    """Ingests weekly bulk datasets from LegiScan.

    Downloads ZIP archives containing per-bill JSON files, parses them,
    and upserts into the bills table using legiscan_id as the cross-reference.
    Detects coverage gaps where LegiScan has bills not yet in our database.
    """

    source_name = "legiscan"

    def __init__(
        self,
        session: AsyncSession,
        states: list[str] | None = None,
    ):
        super().__init__(session)
        self.states = [s.upper() for s in states] if states else None
        self.client = httpx.AsyncClient(timeout=120.0)
        self.gaps: list[dict] = []

    async def ingest(self) -> None:
        """Run the LegiScan weekly dataset ingestion pipeline."""
        await self.start_run("weekly")
        bills_created = 0
        bills_updated = 0

        try:
            dataset_list = await self._fetch_dataset_list()
            if not dataset_list:
                logger.warning("No LegiScan datasets available")
                await self.finish_run("completed")
                return

            for dataset_meta in dataset_list:
                state_abbr = dataset_meta.get("state_abbr", "").upper()

                # Skip states not in our filter list
                if self.states and state_abbr not in self.states:
                    continue

                if state_abbr not in STATE_JURISDICTIONS:
                    logger.warning("Unknown state in LegiScan dataset: %s", state_abbr)
                    continue

                zip_bytes = await self._download_dataset(dataset_meta)
                if not zip_bytes:
                    continue

                bills = extract_bills_from_zip(zip_bytes)
                logger.info(
                    "Extracted %d bills from LegiScan dataset for %s",
                    len(bills),
                    state_abbr,
                )

                for bill_data in bills:
                    created = await self._upsert_bill(bill_data)
                    if created:
                        bills_created += 1
                    else:
                        bills_updated += 1

                await self.session.commit()

            if self.run:
                self.run.records_created = bills_created
                self.run.records_updated = bills_updated
                if self.gaps:
                    self.run.metadata_ = {"gaps_detected": len(self.gaps)}

            if self.gaps:
                logger.info(
                    "Gap detection: %d bills in LegiScan not matched in DB",
                    len(self.gaps),
                )
                for gap in self.gaps[:20]:  # Log first 20 gaps
                    logger.info(
                        "  GAP: %s %s (%s) — legiscan_id=%d",
                        gap["state"],
                        gap["bill_number"],
                        gap["session_name"],
                        gap["legiscan_id"],
                    )

            await self.finish_run("completed")

        except Exception as e:
            logger.error("LegiScan ingestion failed: %s", e)
            await self.finish_run("failed")
            raise

    async def _fetch_dataset_list(self) -> list[dict]:
        """Fetch the list of available weekly datasets from LegiScan API."""
        if not settings.legiscan_api_key:
            logger.error("LEGISCAN_API_KEY not configured — cannot download datasets")
            return []

        try:
            resp = await self.client.get(
                LEGISCAN_API_BASE,
                params={
                    "key": settings.legiscan_api_key,
                    "op": "getDatasetList",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch LegiScan dataset list: %s", e)
            return []

        data = resp.json()
        if data.get("status") != "OK":
            logger.error("LegiScan API error: %s", data.get("alert", {}).get("message", "unknown"))
            return []

        dataset_list = data.get("datasetlist", {})
        # datasetlist is a dict keyed by index or state; convert to list
        if isinstance(dataset_list, dict):
            return list(dataset_list.values())
        return dataset_list

    async def _download_dataset(self, dataset_meta: dict) -> bytes | None:
        """Download a single dataset ZIP from LegiScan."""
        session_id = dataset_meta.get("session_id")
        access_key = dataset_meta.get("access_key", "")

        if not session_id or not access_key:
            logger.warning("Dataset metadata missing session_id or access_key")
            return None

        try:
            resp = await self.client.get(
                LEGISCAN_API_BASE,
                params={
                    "key": settings.legiscan_api_key,
                    "op": "getDataset",
                    "id": session_id,
                    "access_key": access_key,
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(
                "Failed to download LegiScan dataset (session_id=%s): %s",
                session_id,
                e,
            )
            return None

        data = resp.json()
        if data.get("status") != "OK":
            logger.error("LegiScan dataset download error: %s", data.get("alert", {}))
            return None

        # The dataset ZIP is base64-encoded in the response
        import base64

        zip_b64 = data.get("dataset", {}).get("zip")
        if not zip_b64:
            logger.error("No ZIP data in LegiScan dataset response")
            return None

        try:
            return base64.b64decode(zip_b64)
        except Exception as e:
            logger.error("Failed to decode LegiScan ZIP base64: %s", e)
            return None

    async def _upsert_bill(self, bill_data: dict) -> bool:
        """Insert or update a bill from parsed LegiScan data.

        Returns True if a new record was created, False if updated.
        Also performs gap detection: if the bill cannot be matched to an
        existing record by jurisdiction+session+identifier, it is logged as a gap.
        """
        state = bill_data["state"]
        jur_id, jur_name = STATE_JURISDICTIONS[state]

        await self._ensure_jurisdiction(jur_id, jur_name, state)

        # Build session ID
        session_name = bill_data["session_name"]
        session_id = f"{jur_id}-{session_name}"
        await self._ensure_session(session_id, jur_id, session_name)

        identifier = normalize_identifier(bill_data["bill_number"])
        bill_id = generate_bill_id(jur_id, session_id, identifier)

        title = bill_data["title"]
        if bill_data["description"] and bill_data["description"] != title:
            title = bill_data["title"]

        status = bill_data["status"]
        status_date = bill_data["status_date"]
        legiscan_id = bill_data["legiscan_id"]
        url = bill_data["url"]

        # Gap detection: check if this bill already exists by natural key
        existing = await self.session.execute(
            select(Bill.id).where(
                Bill.jurisdiction_id == jur_id,
                Bill.session_id == session_id,
                Bill.identifier == identifier,
            )
        )
        is_gap = existing.scalar_one_or_none() is None

        if is_gap:
            # Check if it also doesn't exist by legiscan_id — true gap
            existing_by_legiscan = await self.session.execute(
                select(Bill.id).where(Bill.legiscan_id == legiscan_id)
            )
            if existing_by_legiscan.scalar_one_or_none() is None:
                self.gaps.append(
                    {
                        "state": state,
                        "bill_number": bill_data["bill_number"],
                        "session_name": session_name,
                        "legiscan_id": legiscan_id,
                        "identifier": identifier,
                    }
                )

        # Snapshot current values for change tracking
        old_values = await self._get_old_values(bill_id)

        # Upsert
        stmt = pg_insert(Bill).values(
            id=bill_id,
            jurisdiction_id=jur_id,
            session_id=session_id,
            identifier=identifier,
            title=title,
            status=status,
            status_date=status_date,
            legiscan_id=legiscan_id,
            source_urls=[url] if url else None,
            last_ingested_at=datetime.now(tz=UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "title": title,
                "status": status,
                "status_date": status_date,
                "legiscan_id": legiscan_id,
                "source_urls": [url] if url else None,
                "last_ingested_at": datetime.now(tz=UTC),
            },
        )
        result = await self.session.execute(stmt)

        # Track changes
        await self._track_changes(
            bill_id,
            old_values,
            {"title": title, "status": status, "status_date": status_date},
        )

        return result.rowcount > 0

    async def _ensure_jurisdiction(self, jur_id: str, name: str, abbreviation: str) -> None:
        """Ensure a state jurisdiction record exists."""
        result = await self.session.execute(select(Jurisdiction).where(Jurisdiction.id == jur_id))
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

    async def _ensure_session(
        self, session_id: str, jurisdiction_id: str, session_name: str
    ) -> None:
        """Ensure a legislative session record exists."""
        result = await self.session.execute(
            select(LegislativeSession).where(LegislativeSession.id == session_id)
        )
        if not result.scalar_one_or_none():
            self.session.add(
                LegislativeSession(
                    id=session_id,
                    jurisdiction_id=jurisdiction_id,
                    name=session_name,
                    identifier=session_name,
                    classification="primary",
                )
            )
            await self.session.flush()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
