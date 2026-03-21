---
status: pending
priority: p2
issue_id: "138"
tags: [code-review, composer, backend, performance]
dependencies: []
---

# Redundant Full Workspace Re-fetches After Mutations

## Problem Statement

Multiple service functions and endpoints re-fetch the entire workspace detail (3 selectinloads) after mutations, even when the response doesn't need the full graph. Each unnecessary re-fetch adds 4 DB round-trips.

## Findings

1. **`generate_outline_for_workspace`** re-fetches workspace at line 249 — workspace already in session identity map
2. **`update_workspace_section`** re-fetches at line 299 — response only needs one section
3. **`accept_policy_generation` endpoint** re-fetches at line 519 — section already returned by service
4. **`update_policy_workspace` endpoint** double-loads at lines 262-267 — only needs counts

## Proposed Solutions

### Option A: Return objects already in session (Recommended)
1. Remove re-fetch from `generate_outline_for_workspace` — return workspace from session
2. Build section response directly in `update_workspace_section` — no full reload
3. Remove re-fetch in `accept_policy_generation` — use returned section directly
4. Use count queries in `update_policy_workspace` instead of full detail load
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] No redundant full workspace reloads after mutations
- [ ] Response data is still correct

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-21 | Created | Found during code review by performance and simplicity reviewers |
