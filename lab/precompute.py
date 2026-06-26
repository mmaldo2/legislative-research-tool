"""Precompute scaffolding for Family 1 (runs ONCE per run, before generation).

In-memory, no temp tables. Three once-per-run aggregates over the live DB:
  - overcount reconciliation: SUM(resolved records per bucket) must be <= the stored official
    count (stored counts are the canonical totals; vote_records are a RESOLVED SUBSET). An event
    that violates this, or whose official count is NULL, is CLASSIFIED into excluded_events
    (a data-quality signal + Family 10 seed), never silently dropped.
  - completed_congresses: congress identifiers whose session has ended (point-in-time gate).
  - total_vote_records: derived from the overcount aggregate so dataset_fingerprint need not
    scan the 5.4M-row table a second time.

Phase 1 Template #1 (vote_lookup) does NOT consume these sets — a single member's recorded
option is unambiguous even on an overcounted event. party_majority is RESERVED (a registry
DEFINITION, blessed with its consumer #4/#5/#6 — see docs/condorcet/registry-open-questions.md).
All SQL is engine-portable (it runs on DuckDB in the fixtures).
"""

from dataclasses import dataclass, field
from typing import Literal

from src.ingestion.vote_parsers import OPTION_BUCKETS

ExclusionReason = Literal["overcount", "missing_official_count"]

# Resolved vote_records.option -> the official stored-count bucket it reconciles against.
# (votes.py stores yes_count=yea, no_count=nay, other_count=present+not_voting.)
_BUCKET_OF = {
    "yea": "yes_count",
    "nay": "no_count",
    "present": "other_count",
    "not_voting": "other_count",
}
assert set(_BUCKET_OF) == set(OPTION_BUCKETS), "bucket map drifted from OPTION_BUCKETS"


@dataclass(frozen=True)
class Precomputed:
    # NOTE: `frozen=True` blocks reassignment, not mutation of these collections.
    excluded_events: dict[str, ExclusionReason] = field(default_factory=dict)
    completed_congresses: frozenset[str] = frozenset()
    total_vote_records: int = 0
    # Events whose resolved records reconcile EXACTLY against the stored official counts in every
    # bucket — the Group B/C completeness gate. STRICTLY stronger than "not in excluded_events":
    # an UNDERcount event (resolved < stored, no overcount/NULL) is in NEITHER set. A GROUP BY over
    # a non-complete event would undercount = fabrication-by-omission, so record-derived templates
    # sample only complete events (windowed templates require the WHOLE window complete — see
    # lab/templates._fully_complete_windows, which assembles windows from this set).
    complete_events: frozenset[str] = frozenset()
    # party_majority: see _party_majority() — a reserved registry DEFINITION.


def precompute(conn) -> Precomputed:
    cur = conn.cursor()

    # 1) resolved counts per (event, option) — one full scan, ~55-85K aggregate rows.
    cur.execute(
        'SELECT vote_event_id, "option", COUNT(*) '
        'FROM vote_records GROUP BY vote_event_id, "option"'
    )
    resolved: dict[str, dict[str, int]] = {}
    total = 0
    for event_id, option, count in cur.fetchall():
        resolved.setdefault(event_id, {})[option] = count
        total += count

    # 2) stored official totals per event; classify overcount / missing / complete.
    cur.execute("SELECT id, yes_count, no_count, other_count FROM vote_events")
    excluded: dict[str, ExclusionReason] = {}
    complete: set[str] = set()
    for event_id, yes_count, no_count, other_count in cur.fetchall():
        stored = {"yes_count": yes_count, "no_count": no_count, "other_count": other_count}
        resolved_bucket = {"yes_count": 0, "no_count": 0, "other_count": 0}
        for option, count in resolved.get(event_id, {}).items():
            bucket = _BUCKET_OF.get(option)
            if bucket is not None:
                resolved_bucket[bucket] += count
        has_overcount = False
        has_missing = False
        for bucket, stored_val in stored.items():
            if stored_val is None:  # explicit NULL arm BEFORE any comparison
                has_missing = True
            elif resolved_bucket[bucket] > stored_val:
                has_overcount = True
        if has_overcount:  # overcount wins — it is the active data bug
            excluded[event_id] = "overcount"
        elif has_missing:
            excluded[event_id] = "missing_official_count"
        elif all(resolved_bucket[b] == stored[b] for b in stored):
            # exact reconciliation (stored non-NULL here, resolved <= stored) -> complete.
            # An undercount event falls through to NEITHER excluded nor complete (by design).
            complete.add(event_id)

    # 3) completed congresses (point-in-time gate). One session row per congress (verified: 10
    #    sessions for Congresses 110-119), so the identifier alone is sufficient.
    cur.execute("SELECT identifier FROM sessions WHERE end_date IS NOT NULL")
    completed = frozenset(r[0] for r in cur.fetchall())

    return Precomputed(
        excluded_events=excluded,
        completed_congresses=completed,
        total_vote_records=total,
        complete_events=frozenset(complete),
    )


def _party_majority(conn):
    """RESERVED. 'Majority of a party on an event' is a registry DEFINITION, not a mechanical
    set — it is blessed with its consumer (#4/#5/#6), not frozen on spec. Three open questions
    must be resolved first (see docs/condorcet/registry-open-questions.md):
      1. denominator — voted-only vs present vs all-members;
      2. ties — 5-5 -> null / both / tie-break;
      3. absences — do not_voting / present count toward the denominator?
    """
    raise NotImplementedError(
        "party_majority is a reserved registry definition; resolve denominator/ties/absences "
        "with its consumer (#4/#5/#6). See docs/condorcet/registry-open-questions.md"
    )
