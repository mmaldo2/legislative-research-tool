---
status: pending
priority: p2
issue_id: 177
tags: [code-review, performance, quality]
dependencies: []
---

# Document Collect-Then-Emit Streaming Limitation

## Problem Statement
`stream_sdk_agentic_chat()` in `src/services/chat_service.py:447-512` collects all Agent SDK events in a background thread before yielding SSE events. Users see nothing for 10-30+ seconds, then all text arrives at once. This is a known v1 trade-off but is not documented in code.

## Proposed Solutions
### Option A: Add clear code comment (Recommended for v1)
- **Effort**: Small (5 min)
- Add comment noting buffered streaming and link to future queue-based approach

### Option B: Implement queue-based real-time streaming (Future)
- **Effort**: Large
- Use `queue.Queue` between background thread and async generator

## Technical Details
- **File**: `src/services/chat_service.py:447-512`

## Acceptance Criteria
- [ ] Code has clear comment about the buffered streaming limitation
- [ ] Future optimization path documented

## Work Log
- 2026-03-22: Created from code review
