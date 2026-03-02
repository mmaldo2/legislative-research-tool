---
status: pending
priority: p1
issue_id: "102"
tags: [code-review, database, migration, production-safety]
dependencies: []
---

# Use CREATE INDEX CONCURRENTLY in Migration 007

## Problem Statement

All 7 indexes in `007_add_timeseries_indexes.py` use standard `CREATE INDEX`, which acquires `ACCESS EXCLUSIVE` locks on the target table for the duration of index creation. On a production database with existing data, this blocks all reads and writes to `bills`, `bill_actions`, `ai_analyses`, and `ingestion_runs` tables.

Additionally, the GIN index on `bills.subject` should be a partial index (`WHERE subject IS NOT NULL`) since the column is nullable and all queries filter out NULLs.

## Findings

- **Data Integrity Guardian (HIGH)**: Table-level locks will block reads/writes during index creation. Use `postgresql_concurrently=True` and run outside a transaction.
- **Data Integrity Guardian**: GIN index includes NULL entries wastefully. Should use a partial index.
- **Data Integrity Guardian**: Add `if_not_exists=True` for idempotency in case of partial failures.

**Affected file:** `migrations/versions/007_add_timeseries_indexes.py`

## Proposed Solutions

### Option A: CONCURRENTLY with autocommit block (Recommended)
Use `op.get_context().autocommit_block()` and `postgresql_concurrently=True` for all indexes. Add `if_not_exists=True` for idempotency. Make GIN index partial.
- Pros: No table locks, safe for production, idempotent
- Cons: Cannot run inside a transaction; if one index fails, partial state remains
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] All 7 indexes use `postgresql_concurrently=True`
- [ ] Migration runs outside a transaction (`autocommit_block`)
- [ ] GIN index includes `postgresql_where="subject IS NOT NULL"`
- [ ] All indexes include `if_not_exists=True`
- [ ] Downgrade also uses concurrent drop
