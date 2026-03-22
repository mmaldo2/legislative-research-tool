---
status: pending
priority: p2
issue_id: 158
tags: [code-review, reliability, streaming]
dependencies: []
---

# Uncaught Exception in event_generator Skips Message Persistence

## Problem

The persistence block in `event_generator()` closures (chat.py, policy_workspaces.py) runs after the stream completes. If the stream generator raises an exception or the client disconnects, persistence is skipped. User message is committed but assistant response is lost, leaving orphaned user messages.

## Fix

Wrap persistence in a `finally` block.
