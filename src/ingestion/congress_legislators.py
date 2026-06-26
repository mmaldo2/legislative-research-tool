"""Congress legislators ingester.

Imports legislator data from the unitedstates/congress-legislators GitHub repository (YAML).
Two entrypoints:
  - ingest():              current legislators -> people (party = most-recent term, as before).
  - ingest_term_history(): current + historical -> person_party_spans (per-span vote-time party).

NB: the legacy `theunitedstates.io/.../*.json` host is 410 Gone; the source is now the raw YAML
on GitHub (parsed with pyyaml). The two files share the same schema.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import httpx
import yaml
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import BaseIngester
from src.models.person import Person
from src.models.person_party_span import PersonPartySpan

logger = logging.getLogger(__name__)

_RAW_BASE = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main"
CURRENT_LEGISLATORS_URL = f"{_RAW_BASE}/legislators-current.yaml"
HISTORICAL_LEGISLATORS_URL = f"{_RAW_BASE}/legislators-historical.yaml"

# Faithful normalization of the dataset's party strings. NOT coerced — an unrecognized value is
# collected and surfaced (the run fails) rather than silently mapped. (3a.0 probe: across all 1,290
# voters the only non-D/R/I value was Amash's "Libertarian".)
PARTY_CODES = {"Democrat": "D", "Republican": "R", "Independent": "I", "Libertarian": "L"}


@dataclass(frozen=True)
class PartySpan:
    """A contiguous party affiliation. `end_date` is an EXCLUSIVE upper bound (half-open)."""

    party: str  # D | R | I | L
    start_date: date
    end_date: date


class UnknownPartyError(Exception):
    """Raised at end-of-run when one or more party/term values could not be normalized."""


def _terms_to_spans(leg: dict, anomalies: list[tuple[str, str]]) -> list[PartySpan]:
    """PURE: a legislator dict -> contiguous half-open party spans.

    A term with a `party_affiliations` list -> one span per entry (covers mid-term switches like
    Specter); otherwise one span per term. `end_date` is EXCLUSIVE, built as
    `min(next_span.start, inclusive_end + 1 day)` so adjacent spans that share a boundary day are
    disjoint (the boundary day belongs to the *later* span). Unnormalizable values are appended to
    `anomalies` (collected, never coerced).
    """
    bio = leg.get("id", {}).get("bioguide", "")
    raw: list[tuple[date, date, str]] = []  # (start, inclusive_end, party_code)
    for term in leg.get("terms", []):
        for entry in term.get("party_affiliations") or [term]:
            start, end, party = entry.get("start"), entry.get("end"), entry.get("party")
            if not start or not end or party is None:
                anomalies.append((bio, f"missing start/end/party: {start!r}/{end!r}/{party!r}"))
                continue
            code = PARTY_CODES.get(party)
            if code is None:
                anomalies.append((bio, party))
                continue
            raw.append((date.fromisoformat(start), date.fromisoformat(end), code))

    raw.sort(key=lambda r: r[0])
    spans: list[PartySpan] = []
    for i, (start, incl_end, code) in enumerate(raw):
        nxt = raw[i + 1][0] if i + 1 < len(raw) else None
        end_excl = min(nxt, incl_end + timedelta(days=1)) if nxt else incl_end + timedelta(days=1)
        spans.append(PartySpan(party=code, start_date=start, end_date=end_excl))
    return spans


def _assert_disjoint(bio: str, spans: list[PartySpan]) -> None:
    """Guard the half-open invariant: spans sorted by start must not share a start or overlap."""
    ordered = sorted(spans, key=lambda s: s.start_date)
    for a, b in zip(ordered, ordered[1:], strict=False):
        if a.start_date == b.start_date:
            raise ValueError(f"{bio}: two spans share start_date {a.start_date}")
        if a.end_date > b.start_date:
            raise ValueError(f"{bio}: overlapping spans {a} / {b}")


class CongressLegislatorsIngester(BaseIngester):
    source_name = "congress_legislators"

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.client = httpx.AsyncClient(timeout=180.0)

    async def _fetch_yaml(self, url: str) -> list:
        resp = await self.client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return yaml.safe_load(resp.text)

    async def ingest(self) -> None:
        """Import current Congress legislators into `people` (party = most-recent term)."""
        await self.start_run("full")
        created = 0
        updated = 0
        try:
            legislators = await self._fetch_yaml(CURRENT_LEGISLATORS_URL)
            for leg in legislators:
                if await self._upsert_legislator(leg):
                    created += 1
                else:
                    updated += 1
            await self.session.commit()
            if self.run:
                self.run.records_created = created
                self.run.records_updated = updated
            await self.finish_run("completed")
            logger.info("Congress legislators: %d created, %d updated", created, updated)
        except Exception as e:
            logger.error("Congress legislators ingestion failed: %s", e)
            await self.finish_run("failed")
            raise

    async def ingest_term_history(self) -> None:
        """Backfill `person_party_spans` (vote-time party) from current + historical legislators.

        Voter-scoped (spans written only for bioguides already in `people`). REPLACE-not-merge:
        all spans are computed in memory first, then written in ONE transaction (DELETE-all +
        bulk INSERT) so a re-run is idempotent and can never accumulate phantom/overlapping spans.
        """
        await self.start_run("full")
        try:
            legislators = await self._fetch_yaml(CURRENT_LEGISLATORS_URL)
            legislators += await self._fetch_yaml(HISTORICAL_LEGISLATORS_URL)
            people_ids = set((await self.session.execute(select(Person.id))).scalars().all())

            anomalies: list[tuple[str, str]] = []
            rows: list[dict] = []
            members = 0
            skipped = 0
            for leg in legislators:
                bio = leg.get("id", {}).get("bioguide", "")
                if not bio or bio not in people_ids:  # not a voter we track -> skip
                    skipped += 1
                    continue
                spans = _terms_to_spans(leg, anomalies)
                if not spans:
                    continue
                _assert_disjoint(bio, spans)
                members += 1
                rows.extend(
                    {
                        "person_id": bio,
                        "party": s.party,
                        "start_date": s.start_date,
                        "end_date": s.end_date,
                    }
                    for s in spans
                )

            if anomalies:  # surface, never coerce — fail the whole run with the full list
                await self.finish_run("failed")
                raise UnknownPartyError(
                    f"{len(anomalies)} unnormalizable party/term value(s): {anomalies[:50]}"
                )

            # Atomic replace: clear then bulk-insert (chunked).
            await self.session.execute(delete(PersonPartySpan))
            for i in range(0, len(rows), 1000):
                await self.session.execute(pg_insert(PersonPartySpan).values(rows[i : i + 1000]))
            await self.session.commit()

            if self.run:
                self.run.records_created = len(rows)
            await self.finish_run("completed")
            logger.info(
                "person_party_spans: %d spans for %d members (%d legislators skipped: not voters)",
                len(rows),
                members,
                skipped,
            )
        except Exception as e:
            logger.error("Term-history ingestion failed: %s", e)
            await self.finish_run("failed")
            raise

    async def _upsert_legislator(self, leg: dict) -> bool:
        """Upsert a single legislator into `people`. Returns True if created."""
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
