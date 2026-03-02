---
status: pending
priority: p2
issue_id: "110"
tags: [code-review, performance, database]
dependencies: ["102"]
---

# Add Composite Indexes for Filtered Trend Queries

## Problem Statement

The current migration only adds single-column indexes on `created_at` and `action_date`. The actual queries always combine date range with filters on `jurisdiction_id`, `session_id`, or `status`, followed by GROUP BY. Without composite indexes, PostgreSQL must choose between scanning the date index (wide range) or the filter index (then heap-fetch dates). At 100x+ scale, this causes multi-second queries.

## Findings

- **Performance Oracle (CRITICAL)**: Missing composite indexes force sequential scans at scale.
- Projected impact: 10x = 2-5s for topic queries, 100x = 10-30s (timeout).

**Affected file:** `migrations/versions/007_add_timeseries_indexes.py`

## Proposed Solutions

### Option A: Add composite indexes in the same migration (Recommended)
```python
op.create_index("ix_bills_jurisdiction_created_at", "bills", ["jurisdiction_id", "created_at"])
op.create_index("ix_bills_session_created_at", "bills", ["session_id", "created_at"])
op.create_index("ix_bill_actions_classification_gin", "bill_actions", ["classification"], postgresql_using="gin")
```
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] Composite index on `bills(jurisdiction_id, created_at)` added
- [ ] Composite index on `bills(session_id, created_at)` added
- [ ] GIN index on `bill_actions.classification` added
- [ ] All new indexes use CONCURRENTLY (per #102)
