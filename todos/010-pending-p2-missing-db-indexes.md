---
status: pending
priority: p2
issue_id: "010"
tags: [code-review, performance]
dependencies: []
---

# Missing Database Indexes on Filter Columns

## Problem Statement

API endpoints filter on `jurisdiction_id`, `legislative_session`, `status`, `subject`, and `party` columns, but no indexes exist on these columns. This will cause full table scans as data grows.

## Findings

- **performance-oracle (CRITICAL)**: Missing indexes on frequently filtered columns
- **architecture-strategist**: Database schema doesn't match query patterns

**Affected models:**
- `src/models/bill.py` — needs indexes on `jurisdiction_id`, `legislative_session`, `status`, `subject`
- `src/models/person.py` — needs indexes on `party`, `current_chamber`, `current_jurisdiction_id`

## Proposed Solutions

### Option A: Add indexes via Alembic migration (Recommended)
- Create migration adding indexes on all filter columns
- Use `index=True` on model columns or explicit `Index()` objects
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] Alembic migration adds indexes on all API filter columns
- [ ] Model definitions include `index=True` for filtered columns
- [ ] Migration is reversible
