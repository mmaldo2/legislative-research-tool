---
status: pending
priority: p2
issue_id: 175
tags: [code-review, quality, architecture]
dependencies: []
---

# Duplicated event_generator + Persist Pattern Across Endpoints

## Problem Statement
The `event_generator()` closure in `src/api/chat.py:608-656` and `src/api/policy_workspaces.py:881-923` are ~35 lines of nearly identical code. Both branch on `use_sdk`, parse done events, inject conversation_id, and persist assistant messages. Bug fixes in one location will be missed in the other.

## Proposed Solutions
### Option A: Extract shared helper to chat_service.py
- **Effort**: Medium
- Create `persist_and_relay_events(event_stream, conversation_id)` async generator
- Both endpoints wrap their event stream with this function

## Technical Details
- **Files**: `src/api/chat.py:608-656`, `src/api/policy_workspaces.py:881-923`

## Acceptance Criteria
- [ ] Single implementation of event relay + persistence logic
- [ ] Both chat and workspace endpoints use shared helper

## Work Log
- 2026-03-22: Created from code review
