---
date: 2026-06-24
topic: Federal roll-call vote ingester (Condorcet Track A prerequisite)
scope-mode: hold
status: approved
---

# Scope: Federal Roll-Call Vote Ingester

## Problem
The Condorcet Lab's Family 1 (roll-call retrieval/aggregation) — the highest-trust-value factual family — cannot run: `vote_events` and `vote_records` are empty (0 rows). The federal backfill ingested bills/people/sponsorships/actions via GovInfo, which does not carry roll-call votes. We must ingest federal roll-call votes (Congress 110–119, House + Senate) before any Family 1 work.

## In Scope
- New `src/ingestion/votes.py` (`VotesIngester(BaseIngester)`) populating `vote_events` + `vote_records`.
- Bill-linked roll-call votes for Congress 110–119, both chambers.
- Deterministic vote_event IDs; idempotent/resumable upserts via `pg_insert().on_conflict_*`.
- Member resolution via bioguide → `people.id`; canonical `option` normalization (yea/nay/present/absent).
- Integration into `scripts/backfill_historical.py` (a `--votes` step) mirroring the GovInfo pattern.

## Out of Scope
- Non-bill votes (nominations, procedural, quorum) — blocked by `vote_events.bill_id` NOT NULL; defer (needs a schema change).
- Family 1 task templates themselves (next phase, once votes load).
- State/Louisiana votes; IRT/ideal-point/MRP work (System 2).

## Key Constraints
- `vote_events.bill_id` NOT NULL FK and `vote_records.person_id` NOT NULL FK — every vote must resolve to an existing bill and person, or be skipped. Never fabricate (Condorcet hard rule).
- Senate XML keys members by LIS id, not bioguide → needs a lis→bioguide crosswalk; House clerk XML is bioguide-native and bill-linked.
- Engine-portable SQL; point-in-time discipline (Condorcet hard rules).

## Codebase Context
- Mirror `src/ingestion/govinfo.py`; extend `BaseIngester`. Reuse `_rate_limited_get()` backoff (consider extracting a shared helper).
- `people.id` = bioguide; `bills.id` = sha256("us:us-{congress}:{identifier}")[:16] / `congress_bill_id`.

## Open Questions
- Source strategy: House clerk.house.gov XML first (authoritative, bioguide- + bill-linked), then Senate via VoteView or senate.gov + lis→bioguide crosswalk — vs. VoteView bulk for both chambers up front. (Recommend clerk-House slice first.)
- First-loop "done" condition (deferred to the planning run).
