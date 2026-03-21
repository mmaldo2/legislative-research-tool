---
status: pending
priority: p1
issue_id: "134"
tags: [code-review, composer, backend, data-integrity, orm]
dependencies: []
---

# Dual delete-orphan Cascade on PolicyGeneration Causes ORM Errors

## Problem Statement

`PolicyGeneration` is claimed as a child by two relationships with `cascade="all, delete-orphan"`: `PolicyWorkspace.generations` and `PolicySection.generations`. SQLAlchemy's delete-orphan semantics mean deleting a section will cascade-delete its generations at the ORM level, even though the database FK uses `ondelete="SET NULL"` to preserve them. This destroys the audit trail of AI generations when sections are removed.

## Findings

1. **`PolicyWorkspace.generations`** at `src/models/policy_workspace.py:52-56` — `cascade="all, delete-orphan"`
2. **`PolicySection.generations`** at `src/models/policy_workspace.py:98-101` — `cascade="all, delete-orphan"`
3. **DB FK** uses `ondelete="SET NULL"` on `section_id`, intending to preserve generations when sections are deleted
4. **ORM contradicts DB** — delete-orphan will cascade-delete generations when sections are removed

## Proposed Solutions

### Option A: Remove delete-orphan from PolicySection.generations (Recommended)
1. Change `PolicySection.generations` cascade to `"save-update, merge"` with `passive_deletes=True`
2. Keep `cascade="all, delete-orphan"` only on `PolicyWorkspace.generations` (workspace owns lifecycle)
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] Deleting a section does not delete its generations
- [ ] Deleting a workspace still cascades to all generations
- [ ] DB-level SET NULL on section_id works as intended

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-21 | Created | Found during code review by data integrity reviewer |
