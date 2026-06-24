"""Federal roll-call vote ingester (clerk.house.gov + senate.gov LIS).

Populates `vote_events` / `vote_records` for Congress 110-119, resolving every
voter (bioguide -> people.id) and bill (normalize_vote_ref -> generate_bill_id)
against existing rows. Unresolved voters/bills are SKIPPED and LOGGED, never
fabricated (Condorcet hard rule). v1 ingests bill-linked House votes; Senate is
Phase 2. Mirrors `src/ingestion/govinfo.py` conventions.
"""

import asyncio
import logging
import random
from collections import Counter

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseIngester
from src.ingestion.normalizer import generate_bill_id
from src.ingestion.vote_parsers import (
    build_member_map,
    house_vote_event_id,
    house_years_for_congress,
    is_bill_ref,
    normalize_vote_option,
    normalize_vote_ref,
    parse_house_index,
    parse_house_roll_xml,
    reconcile,
)
from src.models.bill import Bill
from src.models.person import Person
from src.models.vote import VoteEvent, VoteRecord

logger = logging.getLogger(__name__)

FETCH_BATCH = 80  # rolls fetched concurrently per batch; also the commit cadence


class VotesIngester(BaseIngester):
    """Ingest federal roll-call votes for one (congress, chamber)."""

    source_name = "votes"

    def __init__(
        self,
        session: AsyncSession,
        congress: int = 119,
        chamber: str = "house",
        concurrency: int = 8,
    ):
        super().__init__(session)
        self.congress = congress
        self.chamber = chamber
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={"User-Agent": settings.vote_ingester_user_agent},
        )
        self._sem = asyncio.Semaphore(concurrency)
        # resolution caches (loaded once per run)
        self._bill_ids: frozenset[str] = frozenset()
        self._member_map: dict[str, str] = {}
        self._collisions: set[str] = set()
        self._unresolved_bios: set[str] = set()
        self.metrics: dict[str, int] = Counter()

    async def close(self) -> None:
        await self.client.aclose()

    async def ingest(self) -> None:
        await self.start_run("full")
        try:
            await self._load_caches()
            if self.chamber == "house":
                await self._ingest_house()
            elif self.chamber == "senate":
                raise NotImplementedError("Senate vote ingestion is Phase 2")
            else:
                raise ValueError(f"unknown chamber: {self.chamber!r}")
            self._finalize_run()
            await self.finish_run("completed")
        except Exception:
            logger.exception(
                "Vote ingestion failed (congress=%s chamber=%s)", self.congress, self.chamber
            )
            await self.finish_run("failed")
            raise

    # ------------------------------------------------------------------
    # caches + resolution
    # ------------------------------------------------------------------

    async def _load_caches(self) -> None:
        """Load the global bill-id set and the collision-safe bioguide->people.id map."""
        res = await self.session.execute(select(Bill.id))
        self._bill_ids = frozenset(row[0] for row in res.all())

        res = await self.session.execute(
            select(Person.id, Person.bioguide_id).where(Person.bioguide_id.is_not(None))
        )
        self._member_map, self._collisions = build_member_map(list(res.all()))
        logger.info(
            "Loaded caches: %d bills, %d resolvable bioguides, %d collisions",
            len(self._bill_ids),
            len(self._member_map),
            len(self._collisions),
        )

    def _resolve_member(self, name_id: str) -> str | None:
        """bioguide -> people.id via the canonical map; None if absent or a collision."""
        return self._member_map.get(name_id)

    async def _existing_event_ids(self) -> set[str]:
        """Event ids already present for this (chamber, congress) — for per-event resumability.
        An existing event implies its records exist (event+records are inserted atomically)."""
        prefix = f"us-{self.chamber}-{self.congress}-"
        stmt = select(VoteEvent.id).where(VoteEvent.id.like(f"{prefix}%"))
        res = await self.session.execute(stmt)
        return {row[0] for row in res.all()}

    # ------------------------------------------------------------------
    # House path
    # ------------------------------------------------------------------

    async def _ingest_house(self) -> None:
        session_id = f"us-{self.congress}"
        existing = await self._existing_event_ids()

        for year in house_years_for_congress(self.congress):
            max_roll = await self._house_max_roll(year)
            if max_roll <= 0:
                logger.warning(
                    "No roll index for %d (Congress %d) — skipping year; surface for manual check",
                    year,
                    self.congress,
                )
                self.metrics["years_index_failed"] += 1
                continue

            roll_nums = [
                r
                for r in range(1, max_roll + 1)
                if house_vote_event_id(self.congress, year, r) not in existing
            ]
            logger.info(
                "Congress %d year %d: %d rolls (max %d), %d to fetch",
                self.congress, year, max_roll, max_roll, len(roll_nums),
            )

            for i in range(0, len(roll_nums), FETCH_BATCH):
                batch = roll_nums[i : i + FETCH_BATCH]
                xmls = await self._fetch_rolls(year, batch)
                for roll_num, xml_text in zip(batch, xmls, strict=True):
                    if xml_text is None:
                        self.metrics["rolls_404"] += 1
                        continue
                    await self._process_house_roll(year, roll_num, xml_text, session_id)
                await self.session.commit()

    async def _house_max_roll(self, year: int) -> int:
        """Highest roll number for a year, from the clerk index page."""
        url = f"{settings.house_clerk_evs_base_url}/{year}/index.asp"
        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                return parse_house_index(resp.text)
        except httpx.HTTPError as e:
            logger.warning("Failed to fetch House index for %d: %s", year, e)
        return 0

    async def _fetch_rolls(self, year: int, roll_nums: list[int]) -> list[str | None]:
        """Concurrently fetch a batch of roll XMLs (None for 404/failure)."""
        tasks = [self._fetch_roll(year, r) for r in roll_nums]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [None if isinstance(r, BaseException) else r for r in results]

    async def _fetch_roll(self, year: int, roll: int) -> str | None:
        """Fetch one roll XML. 404 -> None (skippable gap); 429 -> backoff; else retry."""
        url = f"{settings.house_clerk_evs_base_url}/{year}/roll{roll:03d}.xml"
        async with self._sem:
            for attempt in range(3):
                try:
                    resp = await self.client.get(url)
                    if resp.status_code == 404:
                        return None
                    if resp.status_code == 429:
                        wait = int(resp.headers.get("Retry-After", 30)) + random.uniform(0, 3)
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    return resp.text
                except httpx.HTTPError:
                    if attempt == 2:
                        logger.warning("Fetch failed for roll %d/%d", year, roll)
                        return None
                    await asyncio.sleep(2**attempt + random.uniform(0, 1))
        return None

    async def _process_house_roll(
        self, year: int, roll_num: int, xml_text: str, session_id: str
    ) -> None:
        parsed = parse_house_roll_xml(xml_text)
        if parsed is None:
            self.metrics["parse_errors"] += 1
            return
        if parsed.congress != self.congress:
            self.metrics["skipped_other_congress"] += 1
            return
        if not is_bill_ref(parsed.legis_num):
            self.metrics["skipped_out_of_scope"] += 1
            return

        bill_id = generate_bill_id("us", session_id, normalize_vote_ref(parsed.legis_num))
        if bill_id not in self._bill_ids:
            self.metrics["skipped_unresolved_bill"] += 1
            return

        event_id = house_vote_event_id(self.congress, year, roll_num)
        computed: Counter = Counter()
        dropped: Counter = Counter()
        seen: set[str] = set()
        records: list[dict] = []
        for name_id, raw_vote in parsed.casts:
            try:
                option = normalize_vote_option(raw_vote)
            except ValueError:
                logger.warning("Unknown vote option in %s: %r — quarantining", event_id, raw_vote)
                self.metrics["reconciliation_mismatch"] += 1
                return
            if name_id in seen:
                self.metrics["duplicate_member_in_source"] += 1
                continue
            seen.add(name_id)
            pid = self._resolve_member(name_id)
            if pid is None:
                dropped[option] += 1
                self._unresolved_bios.add(name_id)
                continue
            computed[option] += 1
            records.append({"vote_event_id": event_id, "person_id": pid, "option": option})

        if not reconcile(computed, dropped, parsed.official):
            logger.warning(
                "Reconcile mismatch %s: computed=%s dropped=%s official=%s",
                event_id, dict(computed), dict(dropped), parsed.official,
            )
            self.metrics["reconciliation_mismatch"] += 1
            return

        await self._upsert_vote(event_id, bill_id, parsed, records)
        self.metrics["events_created"] += 1
        self.metrics["records_created"] += len(records)
        self.metrics["members_resolved"] += sum(computed.values())
        self.metrics["members_dropped"] += sum(dropped.values())

    async def _upsert_vote(self, event_id: str, bill_id: str, parsed, records: list[dict]) -> None:
        """Atomic upsert of the event and all its records in one savepoint."""
        official = parsed.official
        other = official.get("present", 0) + official.get("not_voting", 0)
        async with self.session.begin_nested():
            event_set = {
                "vote_date": parsed.vote_date,
                "motion_text": parsed.vote_question,
                "result": parsed.vote_result,
                "yes_count": official.get("yea", 0),
                "no_count": official.get("nay", 0),
                "other_count": other,
            }
            ev_stmt = pg_insert(VoteEvent).values(
                id=event_id, bill_id=bill_id, chamber=parsed.chamber, **event_set
            )
            ev_stmt = ev_stmt.on_conflict_do_update(index_elements=["id"], set_=event_set)
            await self.session.execute(ev_stmt)

            if records:
                rec_stmt = pg_insert(VoteRecord).values(records)
                rec_stmt = rec_stmt.on_conflict_do_nothing(
                    index_elements=["vote_event_id", "person_id"]
                )
                await self.session.execute(rec_stmt)

    def _finalize_run(self) -> None:
        total = self.metrics["members_resolved"] + self.metrics["members_dropped"]
        rate = round(self.metrics["members_resolved"] / total, 4) if total else None
        if self.run:
            self.run.records_created = self.metrics["events_created"]
            self.run.records_updated = 0
            self.run.metadata_ = {
                "congress": self.congress,
                "chamber": self.chamber,
                "member_resolution_rate": rate,
                "distinct_unresolved_bioguides": len(self._unresolved_bios),
                **dict(self.metrics),
            }
        logger.info(
            "Votes done (Congress %d %s): %d events, %d records, resolution_rate=%s, "
            "skipped_bill=%d skipped_scope=%d mismatch=%d",
            self.congress, self.chamber,
            self.metrics["events_created"], self.metrics["records_created"], rate,
            self.metrics["skipped_unresolved_bill"], self.metrics["skipped_out_of_scope"],
            self.metrics["reconciliation_mismatch"],
        )
