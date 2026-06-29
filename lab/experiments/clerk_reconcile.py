"""Phase 1 (READ-ONLY) gold-vs-Clerk reconciliation probe for the harness-lift study.

Quantifies the 118th-House bill-linked gap: our `vote_events` (bill-linked ONLY, because
`vote_events.bill_id` is NOT NULL) vs the Clerk's full published roll-call set. Reuses the
ingester's Clerk URL scheme + parsers. NEVER writes (SELECTs + GETs only). See
docs/plans/2026-06-29-feat-lab-gold-vs-clerk-reconciliation-plan.md.

Run: PYTHONPATH=. uv run python -m lab.experiments.clerk_reconcile
"""

import asyncio
import random

import httpx

from lab.harness import get_connection
from src.config import settings
from src.ingestion.normalizer import generate_bill_id
from src.ingestion.vote_parsers import (
    house_vote_event_id,
    house_years_for_congress,
    is_bill_ref,
    normalize_vote_ref,
    parse_house_index,
    parse_house_roll_xml,
)

CONGRESS = 118
SESSION_ID = f"us-{CONGRESS}"
_EVS_BASE = getattr(settings, "house_clerk_evs_base_url", "https://clerk.house.gov/evs")
COMPOSITION_SAMPLE = 40  # missing rolls to fetch + categorize (>= the ~31 gap -> categorize ALL)


async def _get(client, url, sem):
    """Polite GET (mirrors the ingester: 404 -> None, 429 -> backoff, retry). Never raises."""
    async with sem:
        for attempt in range(3):
            try:
                r = await client.get(url)
                if r.status_code == 404:
                    return None
                if r.status_code == 429:
                    delay = int(r.headers.get("Retry-After", 30)) + random.uniform(0, 3)
                    await asyncio.sleep(delay)
                    continue
                r.raise_for_status()
                return r.text
            except httpx.HTTPError:
                if attempt == 2:
                    return None
                await asyncio.sleep(2**attempt + random.uniform(0, 1))
    return None


def _our_house_event_ids(conn) -> set[str]:
    """Bill-linked 118-house vote_event ids (read-only)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT ve.id FROM vote_events ve "
        "JOIN bills b ON b.id = ve.bill_id JOIN sessions s ON s.id = b.session_id "
        "WHERE s.identifier = %s AND ve.chamber = 'house'",
        (str(CONGRESS),),
    )
    return {r[0] for r in cur.fetchall()}


def _bill_in_db(conn, bill_id: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM bills WHERE id = %s LIMIT 1", (bill_id,))
    return cur.fetchone() is not None


def _top_members(conn, k: int = 5):
    cur = conn.cursor()
    cur.execute(
        "SELECT p.name, COUNT(*) FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN bills b ON b.id = ve.bill_id JOIN sessions s ON s.id = b.session_id "
        "JOIN people p ON p.id = vr.person_id "
        "WHERE s.identifier = %s AND ve.chamber = 'house' "
        "GROUP BY p.name ORDER BY COUNT(*) DESC LIMIT %s",
        (str(CONGRESS), k),
    )
    return cur.fetchall()


async def main() -> None:
    years = house_years_for_congress(CONGRESS)
    sem = asyncio.Semaphore(8)
    conn = get_connection()
    present = _our_house_event_ids(conn)
    ours_count = len(present)

    clerk_by_year: dict[int, int] = {}
    missing: list[tuple[int, int]] = []
    comp: dict[str, int] = {}
    examples: list[tuple] = []

    async with httpx.AsyncClient(
        timeout=30.0, headers={"User-Agent": "condorcet-lab/reconcile"}
    ) as client:
        for year in years:
            idx = await _get(client, f"{_EVS_BASE}/{year}/index.asp", sem)
            clerk_by_year[year] = parse_house_index(idx) if idx else 0
            for roll in range(1, clerk_by_year[year] + 1):
                if house_vote_event_id(CONGRESS, year, roll) not in present:
                    missing.append((year, roll))

        clerk_total = sum(clerk_by_year.values())
        if clerk_total == 0:
            conn.close()
            print(
                "Clerk index unreachable in this env (network?) -- DB-side only: "
                f"our bill-linked {CONGRESS}-house vote_events = {ours_count}. "
                "Re-run where clerk.house.gov is reachable."
            )
            return

        stride = max(1, len(missing) // COMPOSITION_SAMPLE) if missing else 1
        for year, roll in missing[::stride][:COMPOSITION_SAMPLE]:
            xml = await _get(client, f"{_EVS_BASE}/{year}/roll{roll:03d}.xml", sem)
            parsed = parse_house_roll_xml(xml) if xml else None
            if parsed is None:
                cat, ref = "parse_fail", None
            elif parsed.congress != CONGRESS:
                cat, ref = "wrong_congress", parsed.legis_num
            elif not is_bill_ref(parsed.legis_num):
                cat, ref = "non_bill", parsed.legis_num
            else:
                bid = generate_bill_id("us", SESSION_ID, normalize_vote_ref(parsed.legis_num))
                cat = "ingested?!" if _bill_in_db(conn, bid) else "bill_not_ingested"
                ref = parsed.legis_num
            comp[cat] = comp.get(cat, 0) + 1
            examples.append((year, roll, cat, ref))

    top = _top_members(conn)
    conn.close()

    gap = clerk_total - ours_count
    gap_pct = (gap / clerk_total * 100) if clerk_total else 0.0
    print(f"=== gold-vs-Clerk reconciliation: {CONGRESS}th House (READ-ONLY) ===")
    print(f"Clerk roll-call total : {clerk_total}  (by year: {clerk_by_year})")
    print(f"Our bill-linked events: {ours_count}")
    print(f"GAP (Clerk - ours)    : {gap}  ({gap_pct:.1f}% of the Clerk total)")
    print(f"composition of {sum(comp.values())} sampled missing rolls: {comp}")
    for year, roll, cat, ref in examples:
        print(f"   {year} roll{roll:03d}: {cat:18} legis_num={ref}")
    print("top-5 members by our bill-linked 118-house record count (the gold the gap perturbs):")
    for name, c in top:
        print(f"   {c:4} records  {name}")
    print(
        f"\nIMPLIED per-member gold error ~= {gap_pct:.1f}% (members vote on ~all rolls): the true "
        f"Clerk count is ~{gap_pct:.0f}% above our (bill-linked) gold."
    )
    print(
        "\nQ2 read: gap <~3% -> gold ~ok; moderate -> re-scope the prompt to 'votes on "
        "legislation (bills)'; large -> the bill-linked framing distorts the task -> reconsider "
        "these as the first tasks."
    )


if __name__ == "__main__":
    asyncio.run(main())
