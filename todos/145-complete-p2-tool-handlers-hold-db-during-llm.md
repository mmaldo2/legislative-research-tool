---
status: pending
priority: p2
issue_id: 145
tags: [performance, code-review]
---

# Chat Tool Handlers Hold DB Sessions During LLM Calls (2-30s)

## Problem Statement

The chat tool handlers `analyze_version_diff`, `analyze_constitutional`, and
`analyze_patterns` keep a database session open while awaiting LLM harness calls that
take 2-30 seconds. This ties up connection pool slots and can exhaust the pool under
moderate concurrency.

## Findings

- These handlers follow a load-from-DB -> call-LLM -> persist pattern but hold the
  session across the entire span.
- `compose_section` was already refactored to a load-call-persist pattern that releases
  the session before the LLM call.
- The fix is a direct application of the same pattern already proven in the codebase.

## Technical Details

**Files:**
- `src/api/chat.py` — tool handler implementations

**Recommended fix:**
1. For each affected handler, split into three phases:
   - **Load**: open session, fetch required data, close session.
   - **Call**: invoke the LLM harness with no active DB session.
   - **Persist**: open a new session, write results, close session.
2. Follow the exact pattern used by `compose_section` as the reference implementation.

## Acceptance Criteria

- [ ] `analyze_version_diff`, `analyze_constitutional`, and `analyze_patterns` release
      DB sessions before LLM calls.
- [ ] No functional regression in tool handler outputs.
- [ ] Connection pool utilization under concurrent chat requests is reduced.
