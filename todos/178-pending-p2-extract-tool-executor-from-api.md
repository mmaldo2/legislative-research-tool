---
status: pending
priority: p2
issue_id: 178
tags: [code-review, architecture]
dependencies: []
---

# Extract Tool Executor from API Layer

## Problem Statement
`execute_tool()`, `_TOOL_HANDLERS`, and all `_tool_*` handler functions live in `src/api/chat.py` (API layer). Both `src/mcp/server.py` and `src/services/chat_service.py` import from this API module, creating an upward dependency. The MCP subprocess loads the entire FastAPI router module as a side effect.

## Proposed Solutions
### Option A: Move to src/services/tool_executor.py
- **Effort**: Medium
- Extract execute_tool + handlers to dedicated service module
- Update imports in chat.py, chat_service.py, server.py

## Technical Details
- **Files**: `src/api/chat.py:54-413` (tool handlers + dispatch)
- **Importers**: `src/mcp/server.py`, `src/services/chat_service.py`

## Acceptance Criteria
- [ ] Tool execution logic in services layer, not API layer
- [ ] MCP subprocess no longer imports FastAPI router modules
- [ ] All existing tests pass

## Work Log
- 2026-03-22: Created from code review
