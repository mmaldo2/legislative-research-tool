---
status: pending
priority: p3
issue_id: 180
tags: [code-review, testing]
dependencies: []
---

# Add call_tool Integration Tests for MCP Server

## Problem Statement
Current tests cover schema conversion and tool registration but not `call_tool()` execution or error handling. The `except Exception` handler at `src/mcp/server.py:66` could silently swallow programming errors without detection.

## Proposed Solutions
### Option A: Add mocked call_tool tests
- **Effort**: Medium
- Mock async_session_factory and execute_tool
- Test happy path returns TextContent
- Test exception path returns structured error JSON
- Test unknown tool name handling

## Technical Details
- **File**: `tests/test_mcp/test_server.py`

## Acceptance Criteria
- [ ] Test that call_tool returns TextContent for valid tool calls
- [ ] Test that call_tool returns error JSON for failures
- [ ] Test that unknown tool names are handled gracefully

## Work Log
- 2026-03-22: Created from code review
