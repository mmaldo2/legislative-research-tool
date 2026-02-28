---
status: pending
priority: p2
issue_id: "018"
tags: [code-review, quality]
dependencies: []
---

# IngestionRun Reuses bills_created Field for People Count

## Problem Statement

`CongressLegislatorsIngester` stores the people created/updated count in `self.run.bills_created` and `self.run.bills_updated` fields. This is semantically incorrect and will produce misleading status output.

## Findings

- **kieran-python-reviewer (MEDIUM)**: Field name mismatch
- **code-simplicity-reviewer**: Semantic confusion

**Affected files:**
- `src/ingestion/congress_legislators.py:53-54`
- `src/models/ingestion_run.py` — needs generic field names

## Proposed Solutions

### Option A: Rename fields to generic names (Recommended)
- Rename `bills_created` → `records_created`, `bills_updated` → `records_updated`
- Alembic migration to rename columns
- **Effort**: Small
- **Risk**: Low (requires migration)

### Option B: Add separate people_created/updated fields
- **Effort**: Small
- **Risk**: Low but adds more columns

## Acceptance Criteria

- [ ] Field names accurately describe their content
- [ ] Status command shows correct labels for each source type
