---
status: pending
priority: p2
issue_id: 148
tags: [architecture, code-review]
---

# No Server-Side Generation Rejection Endpoint

## Problem Statement

Generation rejection is UI-only — it clears React state without recording the decision
on the server. This means rejected generations cannot be audited, analytics cannot track
rejection rates, and a page refresh may resurface a rejected generation.

## Findings

- The frontend clears local state when a user rejects a generated section.
- No API endpoint exists to persist the rejection.
- The `PolicyGeneration` model has no `rejected_at` or equivalent field.

## Technical Details

**Files:**
- `src/api/policy_workspaces.py` — needs new rejection endpoint
- `src/models/policy_workspace.py` — needs `rejected_at` timestamp column

**Recommended fix:**
1. Add a `rejected_at: DateTime | None` column to the `PolicyGeneration` model (with
   an Alembic migration).
2. Create `POST /policy-workspaces/{workspace_id}/generations/{generation_id}/reject`
   that sets `rejected_at = now()`.
3. Exclude rejected generations from any "current generation" queries.
4. Update the frontend rejection flow to call the new endpoint.

## Acceptance Criteria

- [ ] `rejected_at` column exists on the `PolicyGeneration` model with migration.
- [ ] Reject endpoint returns 200 and sets `rejected_at`.
- [ ] Rejected generations are excluded from active generation queries.
- [ ] Frontend calls the reject endpoint on user action.
