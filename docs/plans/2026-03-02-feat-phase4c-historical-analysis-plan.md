---
title: "feat: Phase 4C — Historical Analysis"
type: feat
status: active
date: 2026-03-02
---

# Phase 4C: Historical Analysis

## Overview

Add time-series trend analysis to the legislative research platform: indexes for efficient time-bucketed queries, four aggregation API endpoints, an LLM-generated trend narrative, frontend charts with interactive filters, and CSV export. Independent of Phase 4B (webhooks/alerts) — builds on the same auth layer from Phase 4A.

**Scope:** Backend aggregation service + API endpoints, Alembic migration for indexes, LLM prompt for narrative generation, Next.js frontend page with recharts, CSV export.

## Problem Statement

The platform ingests bills, actions, and AI analyses across 50+ jurisdictions but provides no way to answer time-based questions:
- "How has legislative activity in California changed over the past 3 years?"
- "Which policy topics are trending across all states this quarter?"
- "How does the volume of passed legislation compare between sessions?"

Key columns (`bill_actions.action_date`, `bills.created_at`, `ai_analyses.created_at`) lack indexes, making aggregation queries full-table scans. No aggregation endpoints or visualization exists.

## Technical Approach

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (Next.js)                 │
│  /trends page → recharts charts + filter controls    │
│  URL-persisted filter state for shareability         │
└──────────────────────┬──────────────────────────────┘
                       │ fetchApi<TrendResponse>()
┌──────────────────────┴──────────────────────────────┐
│                   API Layer (FastAPI)                 │
│  GET /trends/bills    — auth_deps (all tiers)        │
│  GET /trends/actions  — auth_deps (all tiers)        │
│  GET /trends/topics   — auth_deps (all tiers)        │
│  GET /trends/summary  — pro_deps  (pro+ tier)        │
│  Each endpoint accepts ?format=csv for export        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│              Service Layer (trend_service.py)         │
│  Time-bucketed aggregation via func.date_trunc()     │
│  In-process TTL cache (5 min) keyed by param hash    │
│  top_n parameter + "Other" bucket aggregation        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│              PostgreSQL (indexed tables)              │
│  ix_bill_actions_action_date                         │
│  ix_bills_created_at, ix_bills_updated_at            │
│  ix_ai_analyses_created_at                           │
│  ix_ingestion_runs_source_started_at (composite)     │
│  ix_bill_actions_bill_id_action_date (composite)     │
│  ix_bills_subject_gin (GIN for ARRAY containment)    │
└─────────────────────────────────────────────────────┘
```

### Key Design Decisions

**1. Date column for bill trend bucketing: `Bill.created_at`**
`Bill.created_at` reflects when the platform first knew about the bill. This is imperfect (bulk backfills create spikes), but it avoids an expensive subquery to `MIN(bill_actions.action_date)` per bill. The actions endpoint uses `BillAction.action_date` for actual legislative activity dates. A denormalized `introduced_date` column can be added in a future optimization pass.

**2. Default date range: last 24 months when omitted**
Unbounded queries across all-time data are expensive and produce noisy charts. Default to 24 months; allow explicit `date_from`/`date_to` override with no maximum cap.

**3. `top_n` parameter for high-cardinality dimensions (default 15)**
`group_by=topic` can produce hundreds of unique values. The `top_n` parameter (default 15, max 50) returns the top N dimensions by count and aggregates the rest into an "Other" bucket. This keeps response sizes bounded and charts readable.

**4. Zero-count periods omitted from response**
Standard SQL `GROUP BY` behavior — periods with no data are absent. The frontend fills missing periods with zero for continuous line charts. This is simpler, cheaper, and matches every existing endpoint's behavior.

**5. `/trends/topics` adds `share_pct` over `/trends/bills?group_by=topic`**
The topics endpoint enriches each bucket with `share_pct` (topic's proportion of total bills in that period). This makes it distinct from the bills endpoint and useful for "what percentage of bills are about education?" questions.

**6. In-process TTL cache for aggregation queries (5-minute TTL)**
Use `cachetools.TTLCache` keyed by a hash of all query parameters. Zero-infrastructure, good enough for initial scale. The same "last 24 months, monthly, by jurisdiction" default view hit by every user is served from cache after the first request.

**7. Period serialization: ISO date for period start**
`func.date_trunc` returns a timestamp. Serialize as ISO date string: `"2024-01-01"` for Jan 2024 (monthly), `"2024-04-01"` for Q2 2024 (quarterly), `"2024-01-01"` for 2024 (yearly). Frontend formats for display (e.g., "Jan 2024", "Q2 2024").

**8. CSV export via `?format=csv` query parameter**
Reuse the existing `_sanitize_csv()` from `src/api/export.py`. Add `format: str = Query("json", pattern="^(json|csv)$")` to each trend endpoint. When `format=csv`, return `StreamingResponse` with `text/csv` content type.

**9. LLM summary receives same-filter aggregation data**
The `/trends/summary` endpoint accepts the same filter params, internally runs the bills + actions + topics aggregations, and formats the results as LLM prompt context. This ensures the narrative reflects the user's current view.

### Data Model

No new tables. Phase 4C adds indexes to existing tables and queries them with aggregation functions.

**Indexes added (migration `007_add_timeseries_indexes`):**

| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| `bill_actions` | `ix_bill_actions_action_date` | btree | Action trend bucketing |
| `bill_actions` | `ix_bill_actions_bill_id_action_date` | btree (composite) | Bill-scoped action queries |
| `bills` | `ix_bills_created_at` | btree | Bill trend bucketing |
| `bills` | `ix_bills_updated_at` | btree | Freshness sorting |
| `bills` | `ix_bills_subject_gin` | GIN | ARRAY containment filter (`topic=X`) |
| `ai_analyses` | `ix_ai_analyses_created_at` | btree | Analysis trend bucketing |
| `ingestion_runs` | `ix_ingestion_runs_source_started_at` | btree (composite) | Ingestion monitoring |

### API Endpoints

#### `GET /api/v1/trends/bills`
Bill counts grouped by time bucket and dimension.

**Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `group_by` | `str` | `"jurisdiction"` | Dimension: `jurisdiction`, `topic`, `status`, `classification` |
| `bucket` | `str` | `"month"` | Time bucket: `month`, `quarter`, `year` |
| `date_from` | `date` | 24 months ago | Start of date range (inclusive) |
| `date_to` | `date` | today | End of date range (inclusive) |
| `jurisdiction` | `str?` | None | Filter to specific jurisdiction |
| `topic` | `str?` | None | Filter to bills containing this topic (ARRAY containment) |
| `session_id` | `str?` | None | Filter to specific legislative session |
| `top_n` | `int` | 15 | Max dimension values (rest aggregated as "Other") |
| `format` | `str` | `"json"` | Response format: `json` or `csv` |

**Response (JSON):**
```json
{
  "data": [
    {"period": "2024-01-01", "dimension": "us-ca", "count": 145},
    {"period": "2024-01-01", "dimension": "us-tx", "count": 132},
    {"period": "2024-01-01", "dimension": "Other", "count": 89}
  ],
  "meta": {
    "sources": ["govinfo", "openstates"],
    "last_updated": "2026-03-01T12:00:00Z",
    "total_count": 366,
    "bucket": "month",
    "group_by": "jurisdiction",
    "date_from": "2024-03-01",
    "date_to": "2026-03-01"
  }
}
```

#### `GET /api/v1/trends/actions`
Action counts grouped by time bucket and dimension. Uses `BillAction.action_date` for bucketing.

**Additional parameters:** Same as bills plus:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `action_type` | `str?` | None | Filter by action classification (e.g., `introduction`, `passage`) |

**Note:** Grouping by `jurisdiction` requires a JOIN to `bills` since `BillAction` has no `jurisdiction_id`.

#### `GET /api/v1/trends/topics`
Topic distribution over time with percentage share.

**Parameters:** Same as bills endpoint (minus `group_by` — always groups by topic).

**Response enrichment:** Each data point includes `share_pct`:
```json
{
  "data": [
    {"period": "2024-01-01", "dimension": "Education", "count": 45, "share_pct": 12.3},
    {"period": "2024-01-01", "dimension": "Healthcare", "count": 38, "share_pct": 10.4}
  ],
  "meta": { ... }
}
```

#### `GET /api/v1/trends/summary` (pro+ tier)
LLM-generated trend narrative from aggregated data.

**Parameters:** Same filter params as bills endpoint (determines what data to summarize).

**Response:**
```json
{
  "narrative": "Legislative activity across tracked jurisdictions...",
  "key_findings": [
    "California introduced 23% more bills in Q4 2025 vs Q4 2024",
    "Healthcare-related legislation saw the largest growth (+45%)"
  ],
  "period_covered": "2024-03 to 2026-03",
  "bills_analyzed": 12450,
  "confidence": 0.85
}
```

**Rate limit:** 5/minute (LLM cost protection).

### Implementation Phases

#### Phase 1: Migration + Service Layer

**New files:**
- `migrations/versions/007_add_timeseries_indexes.py`
- `src/services/trend_service.py`
- `src/schemas/trend.py`

**Tasks:**
1. Create Alembic migration with all 7 indexes (btree + GIN)
2. Build `TrendDataPoint`, `TrendTopicDataPoint`, `TrendResponse`, `TrendTopicResponse`, `TrendMeta`, `TrendSummaryResponse` Pydantic schemas
3. Implement `bill_count_by_period()` in trend_service — `func.date_trunc()` bucketing, `group_by` dispatch, `top_n` with "Other" aggregation, topic/classification ARRAY unnesting
4. Implement `action_count_by_period()` — JOIN to bills for jurisdiction grouping, `action_type` filter via ARRAY containment on `BillAction.classification`
5. Implement `topic_distribution_by_period()` — extends bill query with `share_pct` calculation
6. Add TTL cache wrapper using `cachetools.TTLCache`

**Key query pattern (bills by jurisdiction, monthly):**
```python
bucket_expr = func.date_trunc("month", Bill.created_at)
stmt = (
    select(
        bucket_expr.label("period"),
        Bill.jurisdiction_id.label("dimension"),
        func.count().label("count"),
    )
    .where(Bill.created_at.between(date_from, date_to))
    .group_by("period", "dimension")
    .order_by("period")
)
```

**Key query pattern (bills by topic — ARRAY unnest):**
```python
topic_col = func.unnest(Bill.subject).label("dimension")
stmt = (
    select(
        bucket_expr.label("period"),
        topic_col,
        func.count().label("count"),
    )
    .where(Bill.created_at.between(date_from, date_to), Bill.subject.isnot(None))
    .group_by("period", "dimension")
    .order_by("period")
)
```

**Key query pattern (actions by jurisdiction — JOIN):**
```python
stmt = (
    select(
        func.date_trunc(bucket, BillAction.action_date).label("period"),
        Bill.jurisdiction_id.label("dimension"),
        func.count().label("count"),
    )
    .join(Bill, BillAction.bill_id == Bill.id)
    .where(BillAction.action_date.between(date_from, date_to))
    .group_by("period", "dimension")
    .order_by("period")
)
```

#### Phase 2: API Endpoints + LLM Prompt

**New files:**
- `src/api/trends.py`
- `src/llm/prompts/trend_narrative_v1.py`

**Modified files:**
- `src/api/app.py` — mount trends router
- `src/llm/harness.py` — add `generate_trend_narrative()` method

**Tasks:**
1. Create `trends.py` router with 4 GET endpoints
2. Wire query params → service layer calls, handle `format=csv` via `StreamingResponse`
3. Mount router in `app.py`: bills/actions/topics with `auth_deps`, summary with `pro_deps`
4. Write `trend_narrative_v1.py` prompt — system prompt describing the role of a legislative analyst, user prompt template that formats aggregated data points into context
5. Add `generate_trend_narrative()` to harness — accepts aggregated data dict, formats prompt, calls Claude with `max_tokens=2048`, returns `TrendSummaryResponse`
6. Add rate limiting: `30/minute` for data endpoints, `5/minute` for summary

**Prompt structure (`trend_narrative_v1.py`):**
```python
PROMPT_VERSION = "trend-narrative-v1"

SYSTEM_PROMPT = """You are a legislative data analyst. Given aggregated
legislative trend data, produce a clear narrative summary highlighting
key trends, notable changes, and patterns. Be specific with numbers
and percentages. Note any data limitations."""

USER_PROMPT_TEMPLATE = """Analyze the following legislative trend data
covering {period_covered}:

## Bill Volume by {group_by} ({bucket}ly)
{bills_data}

## Action Volume ({bucket}ly)
{actions_data}

## Topic Distribution ({bucket}ly)
{topics_data}

Total bills analyzed: {total_bills}

Produce a narrative summary with:
1. Key findings (3-5 bullet points)
2. A 2-3 paragraph narrative covering the most significant trends
3. A confidence assessment (0.0-1.0) based on data coverage"""
```

#### Phase 3: Frontend

**New files:**
- `frontend/src/app/trends/page.tsx`
- `frontend/src/app/trends/trend-chart.tsx` (client component)
- `frontend/src/app/trends/trend-filters.tsx` (client component)

**Modified files:**
- `frontend/src/lib/api.ts` — add `fetchTrendBills()`, `fetchTrendActions()`, `fetchTrendTopics()`, `fetchTrendSummary()`
- `frontend/src/types/api.ts` — add `TrendDataPoint`, `TrendTopicDataPoint`, `TrendResponse`, `TrendTopicResponse`, `TrendMeta`, `TrendSummaryResponse`
- `frontend/src/components/site-header.tsx` — add Trends nav item with `TrendingUp` icon
- `frontend/package.json` — add `recharts` dependency

**Tasks:**
1. `npm install recharts` in frontend
2. Add TypeScript interfaces mirroring Pydantic schemas
3. Add API client functions for all 4 trend endpoints
4. Build `trend-filters.tsx` — dropdowns for `group_by`, `bucket`, `jurisdiction`, `topic`, date range picker; URL search params for state persistence
5. Build `trend-chart.tsx` — `ResponsiveContainer` + `LineChart` for time-series, `BarChart` (stacked) for topic/classification distributions; auto-selects chart type based on `group_by`
6. Build `page.tsx` — server component shell, Suspense boundary, filter state via `useSearchParams`, conditional "Generate Summary" button (shows for pro+ tier or dev mode)
7. Add "Export CSV" button that opens `?format=csv` URL in new tab
8. Add "Trends" to site header nav items
9. Handle empty states, loading skeletons, error banners

**Chart type mapping:**
| group_by | Chart Type | Rationale |
|----------|-----------|-----------|
| `jurisdiction` | Line chart | Compare trends across regions over time |
| `status` | Stacked bar | Show composition of bill statuses per period |
| `topic` | Stacked bar | Show topic distribution per period |
| `classification` | Stacked bar | Show bill type composition per period |

#### Phase 4: Tests

**New files:**
- `tests/test_api/test_trends.py`
- `tests/test_services/test_trend_service.py`

**Tasks:**
1. Service tests: test each aggregation function with mock session (bills, actions, topics)
2. Service tests: test `top_n` "Other" bucket aggregation
3. Service tests: test ARRAY unnesting for topic/classification
4. Service tests: test empty result handling (no bills in range)
5. Service tests: test date range defaults and bounds
6. Service tests: test cache hit/miss behavior
7. API tests: test each endpoint returns correct response shape
8. API tests: test `format=csv` returns CSV content type and valid data
9. API tests: test tier gating on summary endpoint (free → 403, pro → 200)
10. API tests: test rate limiting on summary endpoint
11. API tests: test query parameter validation (invalid bucket, invalid group_by)
12. Schema tests: test serialization roundtrips
13. LLM test: test prompt formatting with sample data
14. LLM test: test fallback on LLM failure

**Target: 25+ tests.**

## Alternative Approaches Considered

**Materialized views for pre-aggregated data** — Would guarantee sub-100ms queries. Rejected because the data volume doesn't justify the operational complexity of refresh schedules. In-process TTL cache achieves similar results for repeated queries. Revisit if query latency exceeds 500ms at scale.

**`introduced_date` denormalized column on bills** — Would give more accurate bucketing than `created_at`. Rejected for Phase 4C scope to avoid a data migration. Can be added as a follow-up with a backfill query: `UPDATE bills SET introduced_date = (SELECT MIN(action_date) FROM bill_actions WHERE bill_id = bills.id)`.

**Separate `/trends/bills/csv` export endpoints** — Rejected in favor of `?format=csv` on existing endpoints. Fewer routes, same functionality, consistent with REST conventions.

**Redis cache for aggregation** — Overkill for initial scale. `cachetools.TTLCache` is zero-infrastructure and sufficient for single-process deployment. Redis can be added later if horizontal scaling requires shared cache.

**Multi-dimensional group_by (e.g., jurisdiction + topic)** — Powerful but dramatically increases response size and chart complexity. Deferred to a future enhancement.

## Acceptance Criteria

### Functional Requirements

- [x] `GET /api/v1/trends/bills` returns bill counts grouped by time bucket and dimension
- [x] `GET /api/v1/trends/actions` returns action counts with bill JOIN for jurisdiction grouping
- [x] `GET /api/v1/trends/topics` returns topic distribution with `share_pct` field
- [x] `GET /api/v1/trends/summary` returns LLM-generated narrative (pro+ tier only)
- [x] All trend endpoints accept `bucket`, `date_from`, `date_to`, `jurisdiction`, `topic`, `session_id`, `top_n` parameters
- [x] `top_n` parameter aggregates remaining dimensions into "Other" bucket
- [x] `?format=csv` on any trend endpoint returns CSV download
- [x] ARRAY columns (`subject`, `classification`) unnested correctly for grouping
- [x] Topic filter uses ARRAY containment (`@>` operator) with GIN index
- [x] Free-tier users access bills/actions/topics endpoints; summary returns 403
- [ ] Frontend trend page with interactive charts (recharts)
- [ ] Frontend filter controls: group_by, bucket, jurisdiction, date range, topic
- [ ] Frontend URL state persistence for filter shareability
- [ ] Frontend empty state, loading skeleton, error handling
- [ ] "Trends" link in site header navigation

### Non-Functional Requirements

- [x] Trend aggregation queries < 500ms with indexes (measured with 100K+ bills)
- [x] In-process TTL cache reduces repeated query load (5-minute TTL)
- [x] LLM summary rate limited to 5/minute per API key
- [x] Data endpoints rate limited to 30/minute per API key
- [x] CSV export uses `_sanitize_csv()` for formula injection protection
- [x] Period strings serialized as ISO dates (`"2024-01-01"`)

### Quality Gates

- [x] 25+ new tests covering service layer, API endpoints, schemas, LLM prompt
- [x] All existing 410 tests continue to pass
- [x] Ruff lint + format clean
- [x] Alembic migration reversible (downgrade drops indexes)
- [x] No breaking changes to existing API endpoints

## Dependencies & Prerequisites

| Dependency | Status | Notes |
|-----------|--------|-------|
| Phase 4A complete (auth) | Done | Required for tier gating |
| PostgreSQL + pgvector | Done | docker-compose.yml |
| cachetools (new) | Needed | `pip install cachetools` — in-process TTL cache |
| recharts (new) | Needed | `npm install recharts` — frontend charting |

## Risk Analysis & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| `func.unnest()` on large ARRAY columns slow | High | GIN index on `Bill.subject`; `top_n` caps result size; TTL cache |
| `created_at` bucketing misleading after bulk backfill | Medium | Document limitation; actions endpoint uses `action_date` for accuracy |
| LLM token costs from trend summaries | Medium | Rate limit 5/min; cache aggregation data fed to LLM |
| High-cardinality topics overwhelming charts | Medium | `top_n` default 15 with "Other" bucket; frontend chart type selection |
| Concurrent users hammering same default view | Low | TTL cache serves repeated queries from memory |

## References & Research

### Internal References

- Phase 4 plan: `docs/plans/2026-03-01-feat-phase4-platform-scale-plan.md` (Phase 4C section, lines 389-461)
- Existing aggregation pattern: `src/services/jurisdiction_service.py` (func.count, group_by, unnest)
- Bill model: `src/models/bill.py` (created_at, subject ARRAY, classification ARRAY, status)
- BillAction model: `src/models/bill_action.py` (action_date, classification ARRAY, chamber)
- LLM harness: `src/llm/harness.py` (generate_report pattern with skip_store)
- Export CSV pattern: `src/api/export.py` (_sanitize_csv, StreamingResponse)
- P2 architecture rules: `docs/solutions/architecture/p2-refactor-findings-resolution.md`
- Router mounting: `src/api/app.py` (auth_deps vs pro_deps pattern)
- Schema wrapper: `src/schemas/common.py` (MetaResponse)
- Frontend stats pattern: `frontend/src/app/jurisdictions/[id]/stats-tab.tsx`
- Frontend API client: `frontend/src/lib/api.ts`
- Migration chain: `migrations/versions/006_add_delivery_queue_composite_index.py` (previous head)

### Related Work

- PR #16: Phase 4A — auth + orgs (foundation for tier gating)
- PR #17: Phase 4B — webhooks + alerts
- PR #18: P1-P3 review findings (enums, batch prefetch, encryption)
