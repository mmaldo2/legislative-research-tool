---
status: pending
priority: p1
issue_id: 151
tags: [code-review, bug, streaming]
dependencies: []
---

# await on Async Generator Crashes compose/stream Endpoint

## Problem Statement

`stream_compose_section()` is an async generator (contains `yield`), but the API endpoint calls it with `event_gen = await stream_compose_section(...)`. You cannot `await` an async generator — this raises `TypeError` at runtime. The entire compose/stream endpoint is non-functional.

## Findings

- `src/api/policy_workspaces.py` line ~940: `event_gen = await stream_compose_section(...)`
- `stream_compose_section` is an async generator function (line ~493 in policy_composer_service.py) — it contains `yield` statements
- Even after removing `await`, the try/except wrapping the call won't catch validation errors raised inside the generator body (they execute lazily on first iteration, not at call time)
- Validation errors (PermissionError, LookupError, ValueError) from the load phase would propagate as unhandled errors during SSE streaming instead of clean HTTP 400/403/404

## Proposed Solutions

### Option A: Split into validation coroutine + generator (Recommended)
Restructure `stream_compose_section` to perform all validation in a regular coroutine, then return an async generator for the streaming phase. The API endpoint calls `await validate_and_prepare(...)` which raises HTTP errors normally, then gets back the generator.
- Pros: Clean error handling, proper HTTP status codes
- Cons: Small refactor
- Effort: Small

### Option B: Remove `await` and wrap EventSourceResponse in try/except
Remove the `await`, catch generator errors in the event_generator wrapper.
- Pros: Minimal change
- Cons: Errors during streaming return corrupt partial SSE responses instead of clean HTTP errors
- Effort: Small
- Risk: Poor error UX

## Acceptance Criteria

- [ ] `POST .../compose/stream` endpoint does not crash with TypeError
- [ ] Validation errors (missing workspace, missing section, invalid action_type) return proper HTTP 400/403/404 responses, not SSE error events
- [ ] Streaming works end-to-end for draft_section, rewrite, analyze_constitutional, analyze_patterns actions
