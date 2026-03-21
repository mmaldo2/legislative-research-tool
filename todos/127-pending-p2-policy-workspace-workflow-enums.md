---
status: pending
priority: p2
issue_id: "127"
tags: [code-review, composer, backend, api, quality]
dependencies: []
---

# Constrain Policy Workspace Workflow Enums on the Backend

## Problem Statement

The composer API currently accepts and persists arbitrary string values for workspace and section workflow state. That means callers can set invalid statuses, skip intended state transitions, and leave the UI showing raw unknown values. Because Phase 1/2 are defining the workflow substrate, this should be enforced server-side rather than trusted to the frontend.

## Findings

1. **`PolicyWorkspaceUpdate.status` is an unconstrained string** (`src/schemas/policy_workspace.py:22`).
2. **The service writes that value directly to the model** (`src/services/policy_workspace_service.py:161-162`).
3. **The model stores `status` as a plain `String` for both workspaces and sections** (`src/models/policy_workspace.py:37`, `src/models/policy_workspace.py:92`).
4. **The frontend assumes a finite workflow vocabulary** and falls back to displaying raw unknown strings (`frontend/src/lib/composer.ts`).

## Proposed Solutions

### Option A: Use explicit enum/Literal validation and keep status mostly server-controlled (Recommended)
1. Introduce a shared enum/Literal set for workspace statuses and section statuses.
2. Restrict `PolicyWorkspaceUpdate.status` to the small set actually allowed in Phase 1/2.
3. Reject unsupported transitions such as arbitrary jumps into `drafting`.
4. Add DB-level check constraints if the project is comfortable enforcing these in the migration.
- Effort: Medium
- Risk: Low

### Option B: Remove client-controlled status updates in Phase 1/2
1. Drop `status` from the public update schema for now.
2. Let services own state transitions internally (`setup` -> `outline_ready`).
3. Reintroduce narrower transition endpoints later if needed.
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] Workspace status updates are validated against an explicit allowed set
- [ ] Invalid workflow values are rejected with 422/400 instead of being persisted
- [ ] Section/workspace status vocabularies are defined in one place
- [ ] UI no longer depends on fallback rendering for unexpected composer statuses

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-20 | Created | Found during Phase 1/2 composer review |
