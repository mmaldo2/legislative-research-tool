---
title: "feat: Autoresearch integration for bill outcome prediction"
type: feat
status: active
date: 2026-03-17
origin: docs/brainstorms/2026-03-17-autoresearch-integration-brainstorm.md
---

# feat: Autoresearch Integration for Bill Outcome Prediction

## Overview

Integrate a Karpathy-style autoresearch module into the legislative research tool to develop a bill outcome prediction model via autonomous experimentation. The work is structured as **thin shared prerequisites** (benefiting both Phase 4C historical analysis and autoresearch) followed by **parallel workstreams** where autoresearch runs independently alongside ongoing Phase 4B/4C work.

The prediction engine will surface probabilities like "this bill has a 34% chance of clearing committee" — a user-facing feature targeting policy researchers at organizations like FIRE, Students for Liberty, and Pelican Institute.

## Problem Statement / Motivation

Phase 3, Item 4 of the roadmap calls for "bill outcome prediction using historical passage data + features." Phase 4C (historical analysis) shares the same blocking prerequisite: **historical federal data with resolved outcomes**. Building the data foundation once avoids duplicate ingestion engineering and positions both workstreams for success (see brainstorm: `docs/brainstorms/2026-03-17-autoresearch-integration-brainstorm.md`).

Current state:
- GovInfo ingester only fetches Congress 119 (current), no historical backfill
- Bills have no `introduced_date` column — `created_at` reflects ingestion time, not legislative introduction
- GovInfo ingester does not extract sponsor/cosponsor data from BILLSTATUS XML
- Session records for historical congresses don't exist (no `start_date`/`end_date`)
- An LLM-based prediction exists (`POST /analyze/predict`) but has no ML model backing

## Proposed Solution

Three-phase approach with Phase 1 as shared infrastructure, Phase 2 as autoresearch sandbox setup, and Phase 3 as production promotion (deferred until experiments prove viability).

## Technical Approach

### Architecture

```
legislative-research-tool/
├── src/
│   ├── models/bill.py              # MODIFY: add introduced_date column
│   ├── schemas/bill.py             # MODIFY: expose introduced_date in responses
│   ├── ingestion/govinfo.py        # MODIFY: historical backfill, sponsors, introduced_date
│   ├── prediction/                 # NEW (Phase 3 only — after model promotion)
│   │   ├── __init__.py
│   │   ├── service.py              # Production inference wrapper
│   │   └── schemas.py              # ML prediction response models
│   └── api/prediction.py           # NEW (Phase 3 only — GET /bills/{id}/prediction)
├── autoresearch/                   # NEW: Self-contained R&D sandbox
│   ├── prepare.py                  # Fixed evaluation harness (raw psycopg2)
│   ├── train.py                    # Agent-modified model code
│   ├── program.md                  # Research director instructions
│   ├── promote.py                  # Bridge to src/prediction/
│   ├── requirements.txt            # Isolated ML dependencies
│   ├── baselines/
│   │   └── logistic_baseline.py
│   └── experiments/                # Timestamped experiment logs
├── migrations/versions/
│   └── 008_add_introduced_date.py  # NEW: shared prerequisite migration
├── scripts/
│   └── backfill_historical.py      # NEW: orchestrates historical congress backfill
└── tests/
    ├── test_ingestion/test_govinfo.py  # MODIFY: test historical + sponsor extraction
    └── test_api/test_bills.py          # MODIFY: test introduced_date field
```

### ERD — New/Modified Entities

```mermaid
erDiagram
    bills {
        string id PK
        string jurisdiction_id FK
        string session_id FK
        string identifier
        string title
        string status
        date status_date
        date introduced_date "NEW — backfilled from MIN(action_date)"
        string[] classification
        string[] subject
        datetime created_at
        datetime updated_at
    }

    sessions {
        string id PK
        string jurisdiction_id FK
        string name
        string identifier
        date start_date "POPULATED for historical congresses"
        date end_date "POPULATED for historical congresses"
    }

    sponsorships {
        int id PK
        string bill_id FK
        string person_id FK
        string classification "primary or cosponsor"
    }

    people {
        string id PK
        string name
        string party
        string bioguide_id
    }

    bills ||--o{ sponsorships : "has"
    sponsorships }o--|| people : "by"
    bills }o--|| sessions : "in"
```

### Implementation Phases

#### Phase 1: Shared Prerequisites (Foundation)

Everything here benefits both Phase 4C trends and autoresearch.

##### 1A. Migration — Add `introduced_date` to bills

**File to create:** `migrations/versions/008_add_introduced_date.py`

```python
# migrations/versions/008_add_introduced_date.py
"""Add introduced_date to bills table.

Revision ID: 008_add_introduced_date
Revises: 007_add_timeseries_indexes
Create Date: 2026-03-17
"""

revision = "008_add_introduced_date"
down_revision = "007_add_timeseries_indexes"

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column("bills", sa.Column("introduced_date", sa.Date(), nullable=True))
    # Backfill from earliest action per bill
    op.execute("""
        UPDATE bills b
        SET introduced_date = sub.earliest_date
        FROM (
            SELECT bill_id, MIN(action_date) AS earliest_date
            FROM bill_actions
            GROUP BY bill_id
        ) sub
        WHERE b.id = sub.bill_id AND b.introduced_date IS NULL
    """)
    # Concurrent index for queries
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_bills_introduced_date",
            "bills",
            ["introduced_date"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )

def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index("ix_bills_introduced_date", postgresql_concurrently=True)
    op.drop_column("bills", "introduced_date")
```

**Rationale for `MIN(action_date)` backfill:** The GovInfo ingester creates `BillAction` rows with `classification=NULL` (see `govinfo.py:340-347`). A classification-based backfill (`WHERE classification @> ARRAY['introduction']`) would match zero GovInfo rows. `MIN(action_date)` is the only reliable fallback for the existing data. For Congress.gov API-ingested bills, the earliest action is typically the introduction action, so this is accurate in practice.

**Files to modify:**
- `src/models/bill.py:24` — add `introduced_date: Mapped[date | None] = mapped_column(Date)` after `status_date`
- `src/schemas/bill.py` — add `introduced_date: date | None = None` to both `BillSummary` (line 17) and `BillDetailResponse` (line 51)

##### 1B. Extend GovInfo Ingester for Historical Backfill

**File to modify:** `src/ingestion/govinfo.py`

Changes required:

1. **Parameterize `_ensure_session()` to set `start_date` and `end_date` for historical congresses.**

   Each Congress runs approximately Jan 3 of the first odd year to Jan 3 of the next odd year. Use a lookup:

   ```python
   CONGRESS_DATES: dict[int, tuple[str, str]] = {
       110: ("2007-01-04", "2009-01-03"),
       111: ("2009-01-06", "2011-01-03"),
       112: ("2011-01-05", "2013-01-03"),
       113: ("2013-01-03", "2015-01-03"),
       114: ("2015-01-06", "2017-01-03"),
       115: ("2017-01-03", "2019-01-03"),
       116: ("2019-01-03", "2021-01-03"),
       117: ("2021-01-03", "2023-01-03"),
       118: ("2023-01-03", "2025-01-03"),
       119: ("2025-01-03", "2027-01-03"),
   }
   ```

2. **Extend `_fetch_bills_from_govinfo_bulk()` to iterate all bill types.**

   Currently only fetches `hr` (line 206). Must iterate:
   `["hr", "s", "hres", "sres", "hjres", "sjres", "hconres", "sconres"]`

3. **Extract sponsors from BILLSTATUS XML in `_parse_bill_status_xml()`.**

   GovInfo BILLSTATUS XML contains `<sponsors>` and `<cosponsors>` elements. Add extraction logic:

   ```python
   # In _parse_bill_status_xml(), after action extraction:
   for sponsor_el in bill_el.findall(".//sponsors/item"):
       bioguide = sponsor_el.findtext("bioguideId") or ""
       name = sponsor_el.findtext("fullName") or sponsor_el.findtext("firstName", "") + " " + sponsor_el.findtext("lastName", "")
       party = sponsor_el.findtext("party")
       # Upsert Person (by bioguide_id)
       # Upsert Sponsorship (classification="primary")

   for cosponsor_el in bill_el.findall(".//cosponsors/item"):
       # Same pattern, classification="cosponsor"
   ```

   Person IDs should use `bioguide_id` as the primary key for federal legislators (matching `congress_legislators.py` pattern). If `bioguide_id` is missing, generate a hash-based ID from name.

4. **Set `introduced_date` during upsert for newly-ingested bills.**

   In both `_upsert_bill_from_congress_api()` and `_parse_bill_status_xml()`, derive `introduced_date` from:
   - Congress API: `bill_data.get("introducedDate")` (available in API response)
   - Bulk XML: first action's `action_date`, or `<introducedDate>` element if present

   Add to both the `INSERT` values and `ON CONFLICT UPDATE` set.

5. **Add rate limiting with exponential backoff.**

   The Congress.gov API allows 5,000 req/hr. For bulk XML, GovInfo has generous limits but individual bill fetches are network-bound.

   ```python
   import asyncio
   import random

   async def _rate_limited_get(self, url, params=None, max_retries=3):
       for attempt in range(max_retries):
           try:
               resp = await self.client.get(url, params=params)
               if resp.status_code == 429:
                   retry_after = int(resp.headers.get("Retry-After", 60))
                   await asyncio.sleep(retry_after + random.uniform(0, 5))
                   continue
               resp.raise_for_status()
               return resp
           except httpx.HTTPError:
               if attempt == max_retries - 1:
                   raise
               await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
       return None
   ```

##### 1C. Historical Backfill Script

**File to create:** `scripts/backfill_historical.py`

Orchestrates running the GovInfo ingester for congresses 110-118:

```python
"""Backfill historical federal bills from Congress 110-118.

Usage: python -m scripts.backfill_historical [--start 110] [--end 118] [--api-only]
"""

import asyncio
import argparse
import logging
from src.database import async_session_factory
from src.ingestion.govinfo import GovInfoIngester

async def backfill(start: int, end: int, api_only: bool):
    for congress in range(start, end + 1):
        logging.info("Starting backfill for Congress %d", congress)
        async with async_session_factory() as session:
            ingester = GovInfoIngester(session, congress=congress)
            await ingester.ingest()
            await ingester.close()
        logging.info("Completed Congress %d", congress)
```

Key design decisions:
- One ingestion run per congress (matches `BaseIngester.start_run()` tracking)
- Logs progress per congress for resumability (if Congress 114 fails, resume with `--start 114`)
- `metadata_` JSONB on `IngestionRun` should store `{"congress": N}` for audit trail

##### 1D. Backfill `introduced_date` for Existing Data

After migration 008 runs the inline `UPDATE` for existing data, the backfill script should also ensure newly-ingested historical bills get `introduced_date` set during ingestion (covered by 1B.4 above).

**Acceptance criteria for Phase 1:**

- [x] Migration 008 adds `introduced_date` column and backfills from `MIN(action_date)`
- [x] `introduced_date` exposed in `BillSummary` and `BillDetailResponse` schemas
- [x] GovInfo ingester accepts any congress number and populates session `start_date`/`end_date`
- [x] GovInfo bulk XML path fetches all 8 bill types, not just `hr`
- [x] GovInfo `_parse_bill_status_xml()` extracts sponsors and cosponsors into `people` + `sponsorships`
- [x] GovInfo ingester sets `introduced_date` on newly-ingested bills
- [x] Rate limiting with exponential backoff on Congress.gov API calls
- [x] `scripts/backfill_historical.py` can run congresses 110-118 with resumability
- [ ] At least Congress 110-118 federal bills with actions, sponsors, and `introduced_date` in database
- [ ] Sessions for congresses 110-119 have `start_date` and `end_date` populated
- [x] Existing tests updated to reflect `introduced_date` field (mock helpers, schema tests)
- [x] New tests for sponsor extraction from BILLSTATUS XML
- [x] New tests for rate limiting and multi-bill-type bulk fetching

---

#### Phase 2: Autoresearch Module Setup

Self-contained sandbox that reads from the production database via raw psycopg2 (see brainstorm: keeps clean separation from ORM layer).

##### 2A. `autoresearch/requirements.txt`

```
lightgbm>=4.0
scikit-learn>=1.4
pandas>=2.1
psycopg2-binary>=2.9
numpy>=1.26
```

Isolated from the main `pyproject.toml` — install with `pip install -r autoresearch/requirements.txt`.

##### 2B. `autoresearch/prepare.py` — Fixed Harness

Adapts the integration plan's SQL to match the **actual schema** (see brainstorm: prepare.py written against actual schema, not roadmap assumptions).

**Critical adaptations from integration plan → actual schema:**

| Integration Plan Column | Actual Schema | Notes |
|---|---|---|
| `b.ai_summary` | Not on Bill model | Available via `ai_analyses` table (`analysis_type='summary'`) — join or skip for baseline |
| `b.ai_topics` | Not on Bill model | Available via `ai_analyses` table (`analysis_type='classify'`) — join or skip |
| `b.ai_constitutional_flags` | Not on Bill model | Same as above |
| `b.embedding` | Not on Bill model | Embeddings not stored on bills table — skip for baseline |
| `s.start_date` | `sessions.start_date` | Will be populated after Phase 1B |
| `ba.classification` | `bill_actions.classification` | Usually NULL for GovInfo data — don't rely on it for label derivation |

**Training label definition** (resolves SpecFlow Gap 10):

```python
# The target: did this bill advance beyond committee?
# Based on actual normalize_bill_status() values in normalizer.py:
POSITIVE_STATUSES = {"passed_lower", "passed_upper", "enrolled", "enacted", "vetoed"}
NEGATIVE_STATUSES = {"introduced", "in_committee", "failed", "withdrawn"}
EXCLUDED_STATUSES = {"other"}  # Ambiguous — drop from training

# Additional constraint: only include bills from completed congresses
# (a bill at "in_committee" in an active congress might still pass)
# Use sessions.end_date < NOW() to filter
```

**Database connection string** (resolves SpecFlow Gap 13):

```python
import os
import re

def get_db_url():
    """Read DATABASE_URL and strip asyncpg dialect for psycopg2 compatibility."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://legis:legis_dev@localhost:5432/legis"
    )
    return re.sub(r"\+asyncpg", "", url)
```

**Temporal split using `introduced_date`:**

```python
# Use introduced_date (populated in Phase 1) with session end_date as guard
TRAIN_END = "2022-12-31"
VAL_START = "2023-01-01"
VAL_END = "2023-12-31"
TEST_START = "2024-01-01"
TEST_END = "2024-12-31"

def split_data(df):
    # Drop bills with NULL introduced_date (can't assign to a split)
    df = df.dropna(subset=["introduced_date"])
    train = df[df["introduced_date"] <= TRAIN_END]
    val = df[(df["introduced_date"] >= VAL_START) & (df["introduced_date"] <= VAL_END)]
    test = df[(df["introduced_date"] >= TEST_START) & (df["introduced_date"] <= TEST_END)]
    return train, val, test
```

**Core feature extraction query** (against actual schema):

```sql
WITH bill_features AS (
    SELECT
        b.id AS bill_id,
        b.jurisdiction_id,
        b.session_id,
        b.identifier,
        b.title,
        b.classification,
        b.subject,
        b.status,
        b.introduced_date,
        s.start_date AS session_start,
        s.end_date AS session_end
    FROM bills b
    JOIN sessions s ON b.session_id = s.id
    WHERE b.jurisdiction_id = 'us'                     -- federal only
      AND s.end_date IS NOT NULL                       -- completed congresses only
      AND s.end_date < CURRENT_DATE
      AND b.introduced_date IS NOT NULL
      AND b.status IS NOT NULL
      AND b.status != 'other'                          -- exclude ambiguous
      AND b.classification @> ARRAY['bill']            -- exclude resolutions
),
sponsor_features AS (
    SELECT
        sp.bill_id,
        p.party AS sponsor_party,
        COUNT(DISTINCT sp2.person_id) AS cosponsor_count,
        COUNT(DISTINCT CASE WHEN p2.party != p.party THEN sp2.person_id END)
            AS bipartisan_cosponsor_count
    FROM sponsorships sp
    JOIN people p ON sp.person_id = p.id
    WHERE sp.classification = 'primary'
    LEFT JOIN sponsorships sp2
        ON sp2.bill_id = sp.bill_id AND sp2.classification = 'cosponsor'
    LEFT JOIN people p2 ON sp2.person_id = p2.id
    GROUP BY sp.bill_id, p.party
),
action_features AS (
    SELECT
        ba.bill_id,
        COUNT(*) AS action_count,
        MIN(ba.action_date) AS first_action_date,
        MAX(ba.action_date) AS last_action_date
    FROM bill_actions ba
    GROUP BY ba.bill_id
)
SELECT
    bf.*,
    -- Target variable
    CASE WHEN bf.status IN ('passed_lower','passed_upper','enrolled','enacted','vetoed')
         THEN 1 ELSE 0 END AS committee_passage,
    -- Sponsor features
    sf.sponsor_party,
    COALESCE(sf.cosponsor_count, 0) AS cosponsor_count,
    COALESCE(sf.bipartisan_cosponsor_count, 0) AS bipartisan_cosponsor_count,
    -- Action features
    COALESCE(af.action_count, 0) AS action_count,
    af.first_action_date,
    af.last_action_date
FROM bill_features bf
LEFT JOIN sponsor_features sf ON bf.bill_id = sf.bill_id
LEFT JOIN action_features af ON bf.bill_id = af.bill_id
ORDER BY bf.introduced_date, bf.bill_id;
```

##### 2C. `autoresearch/train.py` — Starting Point

Use the integration plan's `train.py` as-is (see `autoresearch_integration_plan.md`, lines 346-471). Baseline LightGBM with basic features. The agent will iterate from here.

##### 2D. `autoresearch/program.md` — Research Director

Use the integration plan's `program.md` as-is (lines 477-557), with one update: reference the actual column names and note that LLM-enriched features require a join to `ai_analyses` table rather than columns on `bills`.

##### 2E. `autoresearch/promote.py` — Stub

A placeholder that documents the promotion contract. Fully implemented in Phase 3 once a model meets quality bar.

```python
"""
promote.py — Promote best autoresearch model to production.

Reads: autoresearch/experiments/summary.jsonl for best AUROC
Writes: src/prediction/ module with inference wrapper

Not yet implemented — run experiments first, then build this.
"""
# TODO: Implement after model quality threshold is determined
```

**Acceptance criteria for Phase 2:**

- [x] `autoresearch/` directory created with `prepare.py`, `train.py`, `program.md`, `promote.py`, `requirements.txt`
- [x] `prepare.py` SQL matches actual schema column names (verified against `src/models/`)
- [x] `prepare.py` strips `+asyncpg` from `DATABASE_URL` for psycopg2 compatibility
- [x] Training label uses `POSITIVE_STATUSES` / `NEGATIVE_STATUSES` from actual `normalize_bill_status()` values
- [x] Temporal split uses `introduced_date` with NULL-dropping guard
- [x] Only includes bills from completed congresses (sessions with `end_date < NOW()`)
- [ ] `train.py` runs successfully against the database after Phase 1 backfill
- [ ] Experiment logging creates timestamped directories with `metrics.json` and code snapshot
- [ ] Baseline experiment achieves AUROC in expected 0.65-0.70 range (sanity check)

---

#### Phase 3: Production Promotion (Deferred)

Only implemented after autoresearch experiments prove viability. Promotion threshold emerges from experimentation (see brainstorm).

##### 3A. `src/prediction/` Module

- `src/prediction/service.py` — loads model artifact, runs inference, returns structured prediction
- `src/prediction/schemas.py` — Pydantic response model for ML predictions (distinct from LLM `PredictionOutput`)

##### 3B. API Endpoint

- `src/api/prediction.py` — `GET /bills/{id}/prediction` (follows flat router convention, not nested)
- Auth tier: TBD (likely pro+ to match existing `POST /analyze/predict`)
- Rate limited: `30/minute` (matching trends pattern)
- Response includes: `committee_passage_probability`, `model_version`, `key_factors` (feature importances)

##### 3C. Model Artifact Storage

- Format: LightGBM `booster.save_model()` text file (or whatever the best experiment produces)
- Location: configurable path via `src/config.py` setting
- Loaded at startup, not per-request

**Acceptance criteria for Phase 3 (future):**

- [ ] `src/prediction/` module with service layer and schemas
- [ ] `GET /bills/{id}/prediction` endpoint registered in `app.py` with auth tier
- [ ] Response extends `MetaResponse` with model version and training metadata
- [ ] 503 response when no model loaded; 422 when bill lacks required features
- [ ] Existing LLM prediction (`POST /analyze/predict`) unchanged — both coexist
- [ ] Tests for prediction endpoint with mocked service layer

## System-Wide Impact

### Interaction Graph

- Phase 1 migration modifies the `bills` table schema → all bill-reading code paths see a new nullable column, but none break (additive change)
- GovInfo ingester changes add sponsor extraction → creates `Person` and `Sponsorship` records during ingestion → existing sponsor-display code in bill detail API benefits
- Autoresearch reads from the production DB but writes nothing to it (read-only sandbox)
- Production promotion (Phase 3) adds a new API router → mounted in `app.py` alongside existing routers

### Error Propagation

- Historical backfill failure at any congress: script logs and moves to next congress, or stops for manual resume
- `prepare.py` SQL errors: fail fast with clear error (no silent data corruption)
- Model serving errors: 503 if model not loaded, 422 if bill lacks features, both with structured error responses

### State Lifecycle Risks

- **Partial backfill**: If backfill dies mid-congress, the `IngestionRun` record is marked `failed`. Bills already upserted remain (idempotent). Resume by re-running that congress.
- **Concurrent ingestion + autoresearch**: `prepare.py` reads a snapshot. Minor inconsistency is acceptable for R&D — not worth the complexity of `REPEATABLE READ` isolation for a training pipeline.
- **New bills missing `introduced_date`**: Mitigated by updating the ingester (Phase 1B.4) to set `introduced_date` during upsert for all new ingestions.

### API Surface Parity

- Existing `POST /analyze/predict` (LLM-based) — unchanged
- New `GET /bills/{id}/prediction` (ML-based) — Phase 3 only
- Both can coexist. The ML prediction is faster and cheaper; the LLM prediction provides richer natural-language explanation.

## Alternative Approaches Considered

1. **Unified "Historical Intelligence" workstream** — Rejected: couples R&D sandbox to platform release cadence, slowing both down (see brainstorm).
2. **Autoresearch-first, 4C follows** — Rejected: 4C is already in flight and benefits equally from backfill. Shared prereqs are more efficient.
3. **Use existing ORM for autoresearch** — Rejected: autoresearch is an R&D sandbox that should stay self-contained with raw psycopg2 (see brainstorm).
4. **Extend LLM harness for prediction** — Rejected: prediction is tabular ML, not LLM-based. New `src/prediction/` module is cleaner (see brainstorm).

## Dependencies & Prerequisites

| Dependency | Blocks | Status |
|---|---|---|
| Docker Postgres running | All phases | Available (docker-compose.yml exists) |
| Congress.gov API key | Phase 1B (API path) | Env var `CONGRESS_API_KEY` |
| Migration 007 applied | Phase 1A | Complete (committed) |
| Phase 1 backfill complete | Phase 2 experiments | Blocked on Phase 1 |
| Autoresearch experiments proving viability | Phase 3 | Blocked on Phase 2 |

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Congress.gov API rate limits during backfill | High | Backfill takes days | Rate limiter with exponential backoff; use bulk XML path as primary |
| Bulk XML missing bill types (only `hr`) | Certain | 50% of bills missed | Iterate all 8 bill types in `_fetch_bills_from_govinfo_bulk()` |
| Sponsors not in BILLSTATUS XML for older congresses | Medium | Weaker model features | Degrade gracefully — cosponsor count features become 0 for bills without sponsor data |
| `introduced_date` inaccurate (MIN action_date != true intro) | Low | Temporal split noise | Acceptable for R&D; can refine later with Congress API `introducedDate` field |
| Autoresearch AUROC plateaus below 0.70 | Medium | Model not worth promoting | Feature engineering priorities in `program.md` address this; abandon if data quality insufficient |
| Hash collision in 16-hex bill IDs across 90K+ bills | Very low | Duplicate bill records | Monitor for conflicts; 64-bit space gives ~0.2% collision probability across 90K bills |

## Success Metrics

- Phase 1: Historical federal data (congresses 110-118) fully ingested with actions, sponsors, and `introduced_date`
- Phase 2: Autoresearch baseline runs and produces AUROC in 0.65-0.70 range
- Phase 2+: After 50-100 experiments, AUROC reaches 0.75-0.85 range with good calibration (Brier < 0.20)
- Phase 3: Production prediction endpoint serves sub-100ms responses with calibrated probabilities

## Testing Plan

**Phase 1 tests:**
- `tests/test_ingestion/test_govinfo.py` — extend with: multi-bill-type bulk fetch, sponsor extraction from XML, `introduced_date` population, rate limiting behavior
- `tests/test_api/test_bills.py` — update `_mock_bill()` helper to include `introduced_date`, verify field in list/detail responses
- Migration test: verify 008 applies cleanly and backfill UPDATE works on test data

**Phase 2 tests:**
- Manual: run `python autoresearch/prepare.py` → verify DB connection and data loading
- Manual: run `python autoresearch/train.py` → verify baseline experiment completes with sane metrics
- Verify experiment directory created with `metrics.json` and `train.py` snapshot

**Phase 3 tests (future):**
- `tests/test_api/test_prediction.py` — prediction endpoint with mocked service, auth tier enforcement, error cases (no model, missing features)
- `tests/test_services/test_prediction_service.py` — model loading, inference, feature validation

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-03-17-autoresearch-integration-brainstorm.md](docs/brainstorms/2026-03-17-autoresearch-integration-brainstorm.md) — Key decisions: federal-only backfill, raw psycopg2 sandbox, new `src/prediction/` module, `introduced_date` column, separate requirements.txt
- **Integration plan:** `C:\Users\marcu\Downloads\autoresearch_integration_plan.md` — Full autoresearch module specification with prepare.py, train.py, program.md code

### Internal References

- Roadmap Phase 3 Item 4: `AI_Legislative_Research_Tool_Roadmap.md:470`
- Bill model: `src/models/bill.py:10-44`
- GovInfo ingester: `src/ingestion/govinfo.py:42-391`
- Status normalizer: `src/ingestion/normalizer.py:29-54`
- Existing LLM prediction: `src/api/analysis.py:333-394`
- Prediction schema: `src/schemas/analysis.py:149-170`
- Migration pattern (concurrent indexes): `migrations/versions/007_add_timeseries_indexes.py`
- Migration pattern (add column): `migrations/versions/004_add_org_apikey_tables.py`
- Phase 4C historical analysis plan: `docs/plans/2026-03-02-feat-phase4c-historical-analysis-plan.md`

### Pending TODOs Relevant

- `todos/102-pending-p1-migration-concurrently.md` — use `postgresql_concurrently=True` for indexes
- `todos/110-pending-p2-add-composite-indexes.md` — composite indexes for filtered aggregations
- `todos/106-pending-p2-trendmeta-extend-metaresponse.md` — extend MetaResponse for new endpoints
