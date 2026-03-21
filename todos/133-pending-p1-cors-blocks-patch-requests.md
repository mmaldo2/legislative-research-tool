---
status: pending
priority: p1
issue_id: "133"
tags: [code-review, composer, backend, bug, cors]
dependencies: []
---

# CORS Middleware Blocks PATCH Requests

## Problem Statement

The CORS middleware in `src/api/app.py` line 69 configures `allow_methods=["GET", "POST", "PUT", "DELETE"]` but does not include `"PATCH"`. This branch adds two PATCH endpoints (update workspace, update section). Browsers will send a CORS preflight OPTIONS request for PATCH which the middleware will reject, making these endpoints unreachable from any cross-origin frontend.

## Findings

1. **`allow_methods` missing PATCH** in `src/api/app.py:69` — pre-existing limitation exposed by this branch
2. **Two new PATCH endpoints affected**: `update_policy_workspace` and `patch_policy_workspace_section`

## Proposed Solutions

### Option A: Add PATCH to allow_methods (Recommended)
1. Add `"PATCH"` to the `allow_methods` list in `src/api/app.py`
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] CORS middleware allows PATCH method
- [ ] Browser preflight for PATCH endpoints succeeds

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-21 | Created | Found during code review by Python reviewer |
