---
status: pending
priority: p2
issue_id: "128"
tags: [code-review, composer, backend, reliability, testing]
dependencies: []
---

# Harden Composer Writes Against Concurrent Requests

## Problem Statement

The Phase 2 write paths rely on read-then-write checks without locking or integrity-error translation. Concurrent requests can race in ways that produce 500s or duplicate draft artifacts. The current tests patch the service layer, so these transaction and concurrency paths are not exercised.

## Findings

1. **`add_precedent()` does a duplicate read before insert** (`src/services/policy_workspace_service.py:190-218`). A concurrent duplicate request can still hit the unique constraint at commit time and bubble as an unhandled 500.
2. **`generate_outline_for_workspace()` checks `workspace.sections` before a potentially long LLM call, then inserts generations/sections later** (`src/services/policy_composer_service.py:202-231`). Two concurrent outline requests can both pass the precheck and then collide or create inconsistent outline artifacts.
3. **The route tests mock `generate_outline_for_workspace()` and `update_workspace_section()`** (`tests/test_api/test_policy_workspaces.py:192-302`), so they do not verify transaction behavior, IntegrityError handling, or “no partial sections on failure” with a real database session.

## Proposed Solutions

### Option A: Lock and translate integrity failures (Recommended)
1. Serialize outline generation per workspace with a row lock or explicit status transition.
2. Catch `IntegrityError` on precedent insert and return 409 rather than 500.
3. Add rollback handling around failed outline commits.
4. Add AsyncSession-backed integration tests for duplicate precedent adds and concurrent outline generation attempts.
- Effort: Medium
- Risk: Medium

### Option B: Add idempotency keys for outline generation
1. Accept or derive an idempotency token per outline request.
2. Reuse an existing pending/completed outline generation if the same request is retried.
3. Still keep database uniqueness/error translation as a backstop.
- Effort: Medium
- Risk: Medium

## Acceptance Criteria

- [ ] Duplicate precedent requests do not surface as 500s
- [ ] Outline generation is serialized or idempotent per workspace
- [ ] Failed outline writes leave no partial sections or orphan generations
- [ ] Integration tests cover real DB transaction behavior for composer writes

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-20 | Created | Found during Phase 1/2 composer review |
