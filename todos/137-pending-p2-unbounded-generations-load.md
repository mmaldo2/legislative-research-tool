---
status: pending
priority: p2
issue_id: "137"
tags: [code-review, composer, backend, performance]
dependencies: []
---

# Unbounded Generations Eagerly Loaded on Every Composer Operation

## Problem Statement

`get_workspace_for_composer` eagerly loads ALL generations (`selectinload(PolicyWorkspace.generations)`) for every operation, but most callers don't need them. After 50+ compose actions, this loads megabytes of JSONB output_payload and provenance data unnecessarily.

## Findings

1. **`get_workspace_for_composer`** loads all generations — `src/services/policy_composer_service.py:64`
2. **`compose_section`** never accesses `workspace.generations`
3. **`update_workspace_section`** never accesses `workspace.generations`
4. **`accept_generation`** needs only one generation by ID
5. **Only the detail endpoint** needs the latest outline generation

## Proposed Solutions

### Option A: Remove generations from default loader (Recommended)
1. Remove `selectinload(PolicyWorkspace.generations)` from `get_workspace_for_composer`
2. Load latest outline generation with a targeted `LIMIT 1` query for the detail endpoint
3. Load single generation by ID for `accept_generation`
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] Composer operations do not load all generations
- [ ] Detail endpoint still shows outline metadata
- [ ] Accept endpoint still finds the correct generation

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-21 | Created | Found during code review by performance reviewer |
