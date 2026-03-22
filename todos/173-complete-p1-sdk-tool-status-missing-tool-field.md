---
status: pending
priority: p1
issue_id: 173
tags: [code-review, quality, agent-native]
dependencies: []
---

# SDK Path tool_status SSE Events Missing 'tool' Field

## Problem Statement
In `src/services/chat_service.py:494-499`, the SDK path's `tool_status` SSE events omit the `tool` field that the standard path includes. The completion event also omits `tool` and `description`. This breaks frontend parity between the two code paths.

## Findings
- **Agent**: agent-native-reviewer
- **Evidence**: Standard path at `chat_service.py:256` includes `{"tool": tool_name, ...}`. SDK path at line 494 only has `{"status": "running", "description": ...}`.
- **Impact**: Frontend cannot identify which tool is running. Per-tool status indicators broken for SDK users.

## Proposed Solutions
### Option A: Add tool field to SDK path events (Recommended)
- **Effort**: Small (5 min)
- **Risk**: None
- Add `"tool": event["name"]` to the tool_status running event
- Add `"tool": event["name"]` to the tool_status complete event

## Technical Details
- **File**: `src/services/chat_service.py:494-499`

## Acceptance Criteria
- [ ] SDK path tool_status events include `tool` field matching standard path shape
- [ ] Frontend shows correct tool name in status indicators for both paths

## Work Log
- 2026-03-22: Created from code review
