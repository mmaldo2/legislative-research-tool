---
status: pending
priority: p1
issue_id: "135"
tags: [code-review, composer, backend, data-integrity, migration]
dependencies: []
---

# accepted_revision_id Has No Foreign Key Constraint

## Problem Statement

`PolicyGeneration.accepted_revision_id` stores the ID of a `PolicySectionRevision` row but has no FK constraint. If a revision is deleted (via cascade from section deletion), the generation's `accepted_revision_id` becomes a dangling pointer with no database-level protection.

## Findings

1. **Model** at `src/models/policy_workspace.py:129` — plain `String` column, no `ForeignKey`
2. **Migration** at `migrations/versions/010_add_policy_workspace_tables.py:121` — no FK constraint
3. **Circular dependency**: revisions reference generations (generation_id FK), generations reference revisions (accepted_revision_id). Requires ALTER TABLE after both tables exist.

## Proposed Solutions

### Option A: Add FK via ALTER TABLE in migration (Recommended)
1. After creating both `policy_generations` and `policy_section_revisions`, add: `op.create_foreign_key("fk_generations_accepted_revision", "policy_generations", "policy_section_revisions", ["accepted_revision_id"], ["id"], ondelete="SET NULL")`
2. Update ORM model to use `ForeignKey("policy_section_revisions.id", ondelete="SET NULL")`
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] Database enforces FK on accepted_revision_id
- [ ] Deleting a revision sets accepted_revision_id to NULL
- [ ] Migration upgrade/downgrade works correctly

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-21 | Created | Found during code review by data integrity reviewer |
