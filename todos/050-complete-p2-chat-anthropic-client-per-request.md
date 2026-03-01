---
status: complete
priority: p2
issue_id: "050"
tags: [code-review, performance, architecture]
dependencies: []
---

# Chat Creates New Anthropic Client Per Request + No Cost Tracking

## Problem Statement

The chat endpoint creates a new `anthropic.AsyncAnthropic()` client on every request (no connection pooling, socket leaks) and bypasses the `LLMHarness` entirely, so chat LLM costs are invisible to the `CostTracker`.

## Findings

1. `client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)` inside the request handler — new connection pool per request (`src/api/chat.py` ~line 290)
2. `LLMHarness.__init__` also creates a client per injection — same issue (`src/llm/harness.py` line 36)
3. Chat makes up to 10 LLM API calls per request, none tracked by CostTracker
4. Under 50+ concurrent sessions: file descriptor exhaustion, TLS overhead
5. Agents: Performance Oracle (CRITICAL-4), Architecture Strategist (H, I), Python Reviewer (#10)

## Proposed Solutions

### Option A: Singleton Anthropic client in deps.py (Recommended)
- Create module-level singleton or cached dependency for AsyncAnthropic
- Inject via `get_llm_harness` and use `harness.client` in chat
- Wire chat rounds through `harness.cost_tracker.record()`
- **Effort**: Medium
- **Risk**: Low

## Technical Details

- **Files**: `src/api/chat.py`, `src/llm/harness.py`, `src/api/deps.py`

## Acceptance Criteria

- [ ] Single Anthropic client shared across all requests
- [ ] Chat LLM calls appear in cost tracking
- [ ] No inline `import anthropic` in function body

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
