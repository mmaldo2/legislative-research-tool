---
status: pending
priority: p3
issue_id: 181
tags: [code-review, security, performance]
dependencies: []
---

# Add Tool Name Validation at MCP Boundary

## Problem Statement
The MCP `call_tool` handler at `src/mcp/server.py:50-65` allocates a DB session, Anthropic client, and LLMHarness before checking if the tool name is valid. Invalid tool names waste resources.

## Proposed Solutions
### Option A: Early allowlist check
- **Effort**: Small (10 min)
- Check `name` against `_TOOL_HANDLERS` keys before allocating resources
- Return error JSON immediately for unknown tools

## Technical Details
- **File**: `src/mcp/server.py:50-65`

## Acceptance Criteria
- [ ] Unknown tool names rejected before DB session creation
- [ ] Valid tools still execute normally

## Work Log
- 2026-03-22: Created from code review
