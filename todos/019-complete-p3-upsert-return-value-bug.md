---
status: complete
priority: p3
issue_id: "019"
tags: [code-review, bug]
dependencies: []
---

# Legislator Upsert Return Value Always True

## Problem Statement

`CongressLegislatorsIngester._upsert_legislator()` returns `result.rowcount > 0` to distinguish creates from updates, but `ON CONFLICT DO UPDATE` always returns `rowcount=1` (the row was affected either way). So `created` count is always equal to total legislators, and `updated` is always 0.

## Findings

- **kieran-python-reviewer (MEDIUM)**: Upsert return value is misleading

**Affected file:** `src/ingestion/congress_legislators.py:112`

## Proposed Solutions

### Option A: Use xmax trick (Recommended for PostgreSQL)
```python
# PostgreSQL: xmax = 0 means INSERT, xmax != 0 means UPDATE
stmt = pg_insert(Person).values(...).on_conflict_do_update(...).returning(Person.id, text("xmax"))
result = await self.session.execute(stmt)
row = result.one()
return row.xmax == 0  # True if INSERT
```
- **Effort**: Small
- **Risk**: Low (PostgreSQL-specific but that's our target DB)

### Option B: Check existence first
- SELECT before INSERT/UPDATE
- **Effort**: Small
- **Risk**: Race condition between check and insert

## Acceptance Criteria

- [ ] Created vs updated counts are accurate
- [ ] Status output shows meaningful numbers
