---
status: complete
priority: p1
issue_id: "126"
tags: [code-review, composer, backend, reliability, async]
dependencies: []
---

# Policy Workspace Guard Paths Rely on Async Lazy Loads

## Problem Statement

Several mutation paths fetch a `PolicyWorkspace` without eager-loading `sections`, then immediately branch on `workspace.sections` to enforce workflow rules. In this codebase the ORM base is plain `DeclarativeBase`, not `AsyncAttrs`, so these relationship touches can trigger unsupported async lazy loading and raise `MissingGreenlet` or equivalent runtime failures instead of returning the intended 400 response.

## Findings

1. **`get_workspace_for_client()` returns a bare workspace row** (`src/services/policy_workspace_service.py:120`) with no `selectinload(PolicyWorkspace.sections)`.
2. **`update_workspace()` reads `workspace.sections` for jurisdiction/template locks** (`src/services/policy_workspace_service.py:151-157`).
3. **`add_precedent()` and `remove_precedent()` also read `workspace.sections` for outline-state guards** (`src/services/policy_workspace_service.py:182`, `src/services/policy_workspace_service.py:231`).
4. **The current endpoint tests mock the service layer**, so they never exercise these real AsyncSession code paths (`tests/test_api/test_policy_workspaces.py`).

## Proposed Solutions

### Option A: Eager-load relationships before guard checks (Recommended)
1. Change `get_workspace_for_client()` to load `sections` anywhere mutation logic depends on them.
2. Keep the guard logic as-is once the relationship is guaranteed loaded.
3. Add an integration test that hits the real service with AsyncSession-backed models.
- Effort: Small
- Risk: Low

### Option B: Replace relationship truthiness with explicit existence queries
1. Stop reading `workspace.sections` in mutation services.
2. Use `SELECT EXISTS(...)` / count queries against `policy_sections`.
3. Add coverage for both pre-outline and post-outline branches.
- Effort: Medium
- Risk: Low

## Acceptance Criteria

- [ ] Workspace update no longer relies on an unloaded async relationship
- [ ] Precedent add/remove no longer relies on an unloaded async relationship
- [ ] Real service/integration tests cover the workflow guards with AsyncSession
- [ ] Post-outline mutations return controlled 400 responses instead of ORM runtime errors

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-20 | Created | Found during Phase 1/2 composer review |
