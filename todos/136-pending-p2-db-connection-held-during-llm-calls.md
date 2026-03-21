---
status: pending
priority: p2
issue_id: "136"
tags: [code-review, composer, backend, performance, scalability]
dependencies: []
---

# DB Connection Held Idle During Multi-Second LLM Calls

## Problem Statement

`compose_section` and `generate_outline_for_workspace` hold an AsyncSession (and thus a DB connection pool slot) across the entire LLM round-trip (2-10 seconds). With the default pool size of 5, just 5 concurrent compose requests exhaust the pool and block all other database access application-wide.

## Findings

1. **compose_section** at `src/services/policy_composer_service.py:319-412` — session held across `harness.draft_policy_section()`
2. **generate_outline_for_workspace** at `src/services/policy_composer_service.py:187-252` — session held across `harness.generate_policy_outline()`
3. **LLM harness uses `skip_store=True`** for policy operations — no session dependency during LLM call
4. **Pool starvation is a cliff, not gradual** — 5 concurrent users = complete DoS

## Proposed Solutions

### Option A: Split into load-call-persist phases (Recommended)
1. Load all needed data and extract to local variables
2. Make LLM call (session idle but still in scope — keep duration minimal)
3. Persist result
- Effort: Medium
- Risk: Low

### Option B: Separate connection pool for LLM endpoints
1. Create a dedicated session factory with its own pool for composer endpoints
- Effort: Medium
- Risk: Medium

## Acceptance Criteria

- [ ] DB connection is not held idle during LLM API calls
- [ ] Concurrent compose requests do not starve other endpoints

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-21 | Created | Found during code review by performance reviewer |
