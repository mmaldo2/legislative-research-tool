"""Phase 1 (READ-ONLY) per-member roster spot-check vs the House Clerk (harness-lift study).

The count reconciliation (clerk_reconcile.py: gap=31, 100% procedural) proves our bill-linked
roll-call SET == the public set. It does NOT prove the per-(member, roll) OPTION is right: an
ingestion option-swap (yea<->nay, or a misbucketed present/not_voting) would leave the roll COUNT
identical while corrupting the member_summary / pairwise gold. So before the lift run trusts the
gold, this samples members x their rolls and compares OUR stored `vote_records.option` to the
Clerk's published roster vote, cast by cast. NEVER writes (SELECTs + GETs only). See REV 4.2 in
docs/plans/2026-06-29-feat-lab-harness-lift-ablation-plan.md.

Run: PYTHONPATH=. uv run python -m lab.experiments.lift_roster_spotcheck
"""

import asyncio

import httpx

from lab.experiments.clerk_reconcile import _EVS_BASE, _get
from lab.experiments.lift_instances import CHAMBER, CONGRESS, _house_member_ids
from lab.generate import hash_order, sample
from lab.harness import get_connection
from src.ingestion.vote_parsers import normalize_vote_option, parse_house_roll_xml

SEED = 42
MEMBER_SAMPLE = 5  # members drawn from the same seeded population the lift study samples
ROLLS_PER_MEMBER = 8  # rolls per member to fetch + compare cast-by-cast (~40 option checks)


def _bioguide(conn, person_id: str) -> str | None:
    cur = conn.cursor()
    cur.execute("SELECT bioguide_id FROM people WHERE id = %s", (person_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def _member_rolls(conn, person_id: str) -> list[tuple[str, str]]:
    """Our (vote_event_id, stored option) for this member's bill-linked 118-House records."""
    cur = conn.cursor()
    cur.execute(
        'SELECT ve.id, vr."option" '
        "FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN bills b ON b.id = ve.bill_id "
        "JOIN sessions s ON s.id = b.session_id "
        "WHERE vr.person_id = %s AND s.identifier = %s AND ve.chamber = %s",
        (person_id, CONGRESS, CHAMBER),
    )
    return [(r[0], r[1]) for r in cur.fetchall()]


def _year_roll(event_id: str) -> tuple[int, int] | None:
    """Parse `us-house-118-2023-0145` -> (2023, 145). None if it is not a House event id."""
    parts = event_id.split("-")
    if len(parts) != 5 or parts[0] != "us" or parts[1] != "house":
        return None
    try:
        return int(parts[3]), int(parts[4])
    except ValueError:
        return None


async def _clerk_option(client, sem, year: int, roll: int, bioguide: str) -> str | None:
    """The Clerk's canonical option for `bioguide` on (year, roll); None if unreachable/absent."""
    xml = await _get(client, f"{_EVS_BASE}/{year}/roll{roll:03d}.xml", sem)
    parsed = parse_house_roll_xml(xml) if xml else None
    if parsed is None:
        return None
    for name_id, raw in parsed.casts:
        if name_id == bioguide:
            try:
                return normalize_vote_option(raw)
            except ValueError:
                return None
    return None


async def main() -> None:
    conn = get_connection()
    members = sample(_house_member_ids(conn), MEMBER_SAMPLE, SEED)
    sem = asyncio.Semaphore(8)

    total, matched, mismatched, unresolved = 0, 0, 0, 0
    no_bioguide: list[str] = []
    mismatches: list[tuple] = []

    async with httpx.AsyncClient(
        timeout=30.0, headers={"User-Agent": "condorcet-lab/roster-spotcheck"}
    ) as client:
        for pid in members:
            bio = _bioguide(conn, pid)
            if not bio:
                no_bioguide.append(pid)
                continue
            roll_opt = dict(_member_rolls(conn, pid))
            for event_id in hash_order(list(roll_opt), SEED)[:ROLLS_PER_MEMBER]:
                stored = roll_opt[event_id]
                yr = _year_roll(event_id)
                if yr is None:
                    continue
                clerk_opt = await _clerk_option(client, sem, yr[0], yr[1], bio)
                total += 1
                if clerk_opt is None:
                    unresolved += 1
                elif clerk_opt == stored:
                    matched += 1
                else:
                    mismatched += 1
                    mismatches.append((pid, bio, event_id, stored, clerk_opt))
    conn.close()

    if total == 0:
        print(
            "Clerk roster unreachable in this env (network?) -- re-run where clerk.house.gov is "
            "reachable. (members sampled: "
            f"{len(members)}, with bioguide: {len(members) - len(no_bioguide)})"
        )
        return

    print(f"=== per-member roster spot-check: {CONGRESS}th House (READ-ONLY) ===")
    print(f"members sampled : {len(members)} (seed={SEED}); without bioguide_id: {no_bioguide}")
    print(
        f"casts compared  : {total}  (matched={matched} mismatched={mismatched} "
        f"unresolved={unresolved})"
    )
    if mismatches:
        print("OPTION-SWAP MISMATCHES (our stored option != Clerk roster -> gold is corrupted):")
        for pid, bio, event_id, ours, clerk in mismatches:
            print(f"   {event_id}: person={pid} bioguide={bio} ours={ours} clerk={clerk}")
    else:
        print(
            "NO option mismatches: our per-cast 118-House options match the Clerk roster -> the "
            "yea/nay/other count gold the lift study uses is trustworthy at the cast level."
        )


if __name__ == "__main__":
    asyncio.run(main())
