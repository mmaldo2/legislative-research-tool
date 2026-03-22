---
status: pending
priority: p2
issue_id: 153
tags: [code-review, security, streaming]
dependencies: []
---

# No SSE Connection Timeout — DoS Risk

## Problem

All three streaming endpoints return EventSourceResponse with no timeout, ping, or max duration. A client can hold connections indefinitely, exhausting server file descriptors. The agentic loop can run up to 10 rounds with no aggregate timeout.

## Fix

Add `ping=15` to EventSourceResponse, add `asyncio.timeout()` guard around the agentic loop.
