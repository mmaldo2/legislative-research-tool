---
title: "feat: Congress.gov API per-bill detail enrichment"
type: feat
status: active
date: 2026-03-18
---

# feat: Congress.gov API Per-Bill Detail Enrichment

## Overview

The historical backfill ingested 33K+ federal bills via the Congress.gov API list endpoint, but that endpoint only returns `title`, `latestAction.text`, and `introducedDate`. Bills lack full action history, sponsor/cosponsor data, and accurate final status. The autoresearch harness shows 0% positive rate because all bills appear as `introduced` — the `latestAction` text doesn't distinguish bills that passed committee from those that died.

This plan adds per-bill detail fetching to populate actions, sponsors, and derive accurate outcomes from complete action history.

## Problem Statement

The Congress.gov API has two levels:

| Endpoint | Returns | Current Use |
|---|---|---|
| `GET /bill/{congress}` (list) | title, type, number, latestAction, introducedDate, url | Used by `_fetch_bills_from_congress_api()` |
| `GET /bill/{congress}/{type}/{number}/actions` (detail) | Full action history with dates, classifications | **Not used** |
| `GET /bill/{congress}/{type}/{number}/cosponsors` (detail) | All cosponsors with bioguideId, party, state | **Not used** |

Without detail data:
- `bill_actions` table has 0 rows for API-ingested bills (only bulk XML bills get actions)
- `sponsorships` table has 0 rows for API-ingested bills
- `bills.status` is derived from `latestAction.text` alone — misses intermediate statuses
- `bills.introduced_date` is set correctly from the list endpoint but `status` is almost always `introduced` or `in_committee`

## Proposed Solution

Add an `enrich_bills()` method to `GovInfoIngester` that makes per-bill detail API calls for bills missing action history. This runs as a **second pass** after the list fetch, keeping the existing fast-list-then-enrich-details pattern clean.

### Architecture

```
_fetch_bills_from_congress_api()     # Existing: fast list fetch (250/page)
    └── _upsert_bill_from_congress_api()  # Existing: upsert bill metadata

enrich_bills()                       # NEW: detail enrichment pass
    ├── Find bills with 0 actions (need enrichment)
    ├── For each bill (rate-limited, batched):
    │   ├── GET /bill/{congress}/{type}/{number}/actions
    │   ├── GET /bill/{congress}/{type}/{number}/cosponsors
    │   ├── Bulk upsert actions (pg_insert on_conflict_do_nothing)
    │   ├── Bulk upsert sponsors (pg_insert on_conflict_do_nothing)
    │   └── Update bill.status from best action in full history
    └── Commit per batch (50 bills)
```

### Key Design Decisions

1. **Separate enrichment pass, not inline with list fetch.** The list fetch processes 250 bills/page in ~4s. Adding 2 detail calls per bill inline would make it 500+ calls per page, hitting rate limits immediately. A separate pass with its own rate control is cleaner and resumable.

2. **Only enrich bills with 0 actions.** This is the resumability mechanism — if enrichment is interrupted, re-running skips already-enriched bills. A bill with actions in `bill_actions` has already been enriched.

3. **Status determined by scanning all actions for "highest" status.** Define a precedence order: `enacted > vetoed > enrolled > passed_upper > passed_lower > in_committee > introduced`. Scan all actions through `normalize_bill_status()` and keep the highest.

4. **2 API calls per bill (actions + cosponsors).** Subjects and summaries are nice-to-have but not needed for autoresearch. Keeping it to 2 calls halves the API budget usage.

## Technical Approach

### Implementation

**File to modify:** `src/ingestion/govinfo.py`

#### 1. Add `enrich_bills()` method

```python
async def enrich_bills(self, batch_size: int = 50) -> None:
    """Fetch per-bill details (actions, cosponsors) for bills missing action history."""
    session_id = f"us-{self.congress}"

    # Find bills needing enrichment: have no actions in bill_actions
    stmt = (
        select(Bill.id, Bill.congress_bill_id)
        .where(Bill.session_id == session_id)
        .where(~Bill.id.in_(
            select(BillAction.bill_id).distinct()
        ))
    )
    result = await self.session.execute(stmt)
    bills_to_enrich = result.all()

    total = len(bills_to_enrich)
    logger.info("Enriching %d bills for Congress %d", total, self.congress)
    enriched = 0

    for i in range(0, total, batch_size):
        batch = bills_to_enrich[i:i + batch_size]
        for bill_id, congress_bill_id in batch:
            # Parse type and number from congress_bill_id (e.g., "hr1234-118")
            parts = congress_bill_id.rsplit("-", 1)[0]  # "hr1234"
            # Split type from number
            bill_type, bill_number = parse_bill_type_number(parts)

            await self._fetch_bill_actions(bill_id, bill_type, bill_number)
            await self._fetch_bill_cosponsors(bill_id, bill_type, bill_number)
            enriched += 1

        await self.session.commit()
        logger.info("Enriched %d/%d bills", min(i + batch_size, total), total)
```

#### 2. Add `_fetch_bill_actions()` method

```python
async def _fetch_bill_actions(self, bill_id: str, bill_type: str, bill_number: str) -> None:
    """Fetch full action history for a bill and update status."""
    url = f"{CONGRESS_API_BASE}/bill/{self.congress}/{bill_type}/{bill_number}/actions"
    params = {"api_key": settings.congress_api_key, "limit": 250, "format": "json"}

    try:
        resp = await self._rate_limited_get(url, params=params)
    except httpx.HTTPError:
        logger.warning("Failed to fetch actions for %s/%s", bill_type, bill_number)
        return

    data = resp.json()
    actions = data.get("actions", [])

    # Bulk upsert actions
    action_values = []
    best_status = "introduced"
    for i, action in enumerate(actions):
        action_date_str = action.get("actionDate")
        action_text = action.get("text", "")
        if not action_date_str or not action_text:
            continue
        try:
            action_date = date.fromisoformat(action_date_str)
        except ValueError:
            continue

        action_values.append({
            "bill_id": bill_id,
            "action_date": action_date,
            "description": action_text,
            "action_order": i,
            "chamber": action.get("actionCode", ""),
        })

        # Track highest status from all actions
        action_status = normalize_bill_status(action_text)
        if STATUS_PRECEDENCE.get(action_status, 0) > STATUS_PRECEDENCE.get(best_status, 0):
            best_status = action_status

    if action_values:
        stmt = pg_insert(BillAction).values(action_values)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["bill_id", "action_date", "description"]
        )
        await self.session.execute(stmt)

    # Update bill status from full action history
    await self.session.execute(
        sa_update(Bill).where(Bill.id == bill_id).values(status=best_status)
    )
```

#### 3. Add `STATUS_PRECEDENCE` constant

```python
STATUS_PRECEDENCE: dict[str, int] = {
    "introduced": 0,
    "in_committee": 1,
    "passed_lower": 2,
    "passed_upper": 3,
    "enrolled": 4,
    "enacted": 5,
    "vetoed": 5,
    "failed": 1,
    "withdrawn": 1,
    "other": 0,
}
```

#### 4. Add `_fetch_bill_cosponsors()` method

Follow the same batched pattern as `_upsert_sponsors_from_xml()` but parsing JSON instead of XML. Use `_extract_sponsor_values_from_json()` to build person/sponsorship dicts, then bulk upsert.

#### 5. Wire into `ingest()` and backfill script

```python
async def ingest(self) -> None:
    await self.start_run("full")
    try:
        await self._ensure_jurisdiction()
        await self._ensure_session()
        await self._fetch_bills_from_congress_api()
        await self.enrich_bills()  # NEW: detail enrichment pass
        await self.finish_run("completed")
    except Exception as e:
        ...
```

Also add `--enrich-only` flag to `scripts/backfill_historical.py` for running enrichment on already-ingested congresses without re-fetching the list.

### Rate Limiting Math

- **Per bill:** 2 API calls (actions + cosponsors)
- **Congress.gov limit:** 5,000 req/hr (~83 req/min)
- **Per congress (~15K bills):** 30K API calls → ~6 hours per congress
- **All 9 congresses (110-118):** ~54 hours total at max safe rate
- **With existing `_rate_limited_get()`:** Automatic 429 backoff handles bursts. The ~4s per page (250 bills) from list fetch naturally spaces requests. Detail fetches add 2 calls per bill but are sequential within a batch.

**Optimization:** Only enrich bills classified as `['bill']` (skip resolutions) — reduces volume by ~40%.

## Acceptance Criteria

- [ ] `enrich_bills()` method fetches actions + cosponsors for bills missing action data
- [ ] `bill_actions` table populated with full action history from detail endpoint
- [ ] `sponsorships` + `people` tables populated with cosponsor data from detail endpoint
- [ ] `bills.status` updated using best status from full action history (STATUS_PRECEDENCE)
- [ ] Resumable: re-running skips bills that already have actions
- [ ] Rate limiting handled by existing `_rate_limited_get()` (429 backoff)
- [ ] `--enrich-only` flag on backfill script for enrichment without re-listing
- [ ] Batch commits every 50 bills (not per-bill)
- [ ] Progress logging: "Enriched X/Y bills" per batch
- [ ] Autoresearch `prepare.py` query returns non-zero positive rate after enrichment
- [ ] Tests for: action parsing from JSON, cosponsor parsing, status precedence logic

## Success Metrics

- `bills.status` distribution shows realistic outcomes: ~3-5% enacted, ~15-25% passed committee, ~70% introduced/failed
- Autoresearch baseline AUROC in 0.65-0.70 range (up from NaN)
- All 9 congresses (110-118) enriched with actions and cosponsors

## Dependencies & Risks

| Risk | Mitigation |
|---|---|
| 54 hours of API calls across all congresses | Run overnight; `--enrich-only` enables incremental runs |
| Congress.gov API outage mid-enrichment | Resumable by design (skip bills with actions) |
| Action text doesn't match `normalize_bill_status()` patterns | Log unmatched actions; iterate on patterns |
| Rate limit changes | `_rate_limited_get()` respects Retry-After header dynamically |

## Sources & References

- GovInfo ingester: `src/ingestion/govinfo.py:124-268`
- OpenStates detail fetch pattern: `src/ingestion/openstates.py:279-393`
- Status normalizer: `src/ingestion/normalizer.py:29-54`
- Backfill script: `scripts/backfill_historical.py`
- Congress.gov API docs: https://api.congress.gov
- Related PR: #20 (autoresearch prerequisites)
