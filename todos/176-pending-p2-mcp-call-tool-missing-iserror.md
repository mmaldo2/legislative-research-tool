---
status: pending
priority: p2
issue_id: 176
tags: [code-review, agent-native]
dependencies: []
---

# MCP call_tool Does Not Signal Errors via isError Flag

## Problem Statement
When a tool fails in `src/mcp/server.py:66-69`, the handler returns a `TextContent` with error JSON but does not set MCP's `isError` flag. MCP clients cannot programmatically distinguish tool failures from successful responses.

## Proposed Solutions
### Option A: Use ToolError exception from MCP SDK
- **Effort**: Small
- Raise `mcp.server.fastmcp.exceptions.ToolError` for tool failures
- Or construct CallToolResult with isError=True

## Technical Details
- **File**: `src/mcp/server.py:66-69`

## Acceptance Criteria
- [ ] Tool failures return responses with isError=True
- [ ] MCP clients can programmatically detect failures

## Work Log
- 2026-03-22: Created from code review
