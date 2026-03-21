---
status: complete
priority: p1
issue_id: "049"
tags: [code-review, security, rate-limiting]
dependencies: []
---

# Missing Rate Limits on All Collection Endpoints

## Problem Statement

None of the 7 collection endpoints have rate limiting, unlike chat (30/min), compare (10/min), and export (10/min). An attacker can create unlimited collections and items, causing database exhaustion.

## Findings

1. POST /collections — no rate limit (can create unlimited collections)
2. POST /collections/{id}/items — no rate limit
3. PUT, DELETE endpoints also unprotected
4. All other write/LLM endpoints in the codebase have rate limits
5. Agent: Security Sentinel (H2)

## Proposed Solutions

### Option A: Add limiter decorators (Recommended)
- Add `@limiter.limit("30/minute")` to all collection write endpoints
- Consider per-client collection count cap (e.g., 100 collections)
- **Effort**: Small
- **Risk**: Low

## Technical Details

- **Files**: `src/api/collections.py`

## Acceptance Criteria

- [ ] All collection POST/PUT/DELETE endpoints have rate limits
- [ ] Rate limits are consistent with project patterns (30/min for CRUD)

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
- Related: todos/archive/003-complete-p1-no-rate-limiting.md
