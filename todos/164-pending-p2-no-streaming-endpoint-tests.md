---
status: pending
priority: p2
issue_id: 164
tags: [code-review, testing, streaming]
dependencies: []
---

# No Test Coverage for Streaming Endpoints

## Problem

The sync endpoints have test coverage but none of the three streaming endpoints are tested. Regressions in event format, persistence, or conversation_id injection would go undetected.

## Fix

Add tests that consume the SSE stream from the test client and verify event types, ordering, done event content, and persistence.
