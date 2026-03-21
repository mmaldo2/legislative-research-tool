---
status: pending
priority: p2
issue_id: "140"
tags: [code-review, composer, backend, data-integrity, concurrency]
dependencies: []
---

# TOCTOU Race Condition on Double-Accept of Generation

## Problem Statement

`accept_generation` checks `generation.accepted_revision_id is not None` in Python after loading from DB. Two concurrent requests can both pass this check, creating duplicate revisions and overwriting the accepted_revision_id.

## Findings

1. **Guard check** at `src/services/policy_composer_service.py:432` — Python-level, not DB-level
2. **No SELECT FOR UPDATE** — concurrent reads see stale state
3. **Result**: duplicate PolicySectionRevision rows, broken audit trail

## Proposed Solutions

### Option A: SELECT FOR UPDATE on generation row (Recommended)
1. Load the single generation with `.with_for_update()` instead of scanning workspace.generations
- Effort: Small
- Risk: Low

### Option B: Partial unique index
1. `CREATE UNIQUE INDEX ON policy_generations (id) WHERE accepted_revision_id IS NOT NULL`
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] Concurrent accept requests on same generation result in exactly one revision
- [ ] Second request receives a 400 error

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-21 | Created | Found during code review by data integrity reviewer |
