---
status: pending
priority: p1
issue_id: 170
tags: [code-review, security]
dependencies: []
---

# MCP call_tool Exception Handler Leaks Internal State

## Problem Statement
The `call_tool` handler in `src/mcp/server.py:66-69` catches all exceptions and serializes `str(e)` into the MCP response. This can leak database hostnames, connection strings, internal file paths, table/column names, and SQL fragments to any MCP client.

## Findings
- **Agent**: security-sentinel
- **Evidence**: `error_json = json.dumps({"error": f"Tool '{name}' failed: {e}"})` at line 68
- **Impact**: Information disclosure — asyncpg connection errors include hostnames, SQLAlchemy errors include table names

## Proposed Solutions
### Option A: Return generic error message (Recommended)
- **Effort**: Small (5 min)
- **Risk**: None
- Change to: `json.dumps({"error": f"Tool '{name}' encountered an internal error."})`
- Keep detailed exception in server-side logs (already logged at line 67)

## Technical Details
- **File**: `src/mcp/server.py:66-69`

## Acceptance Criteria
- [ ] MCP error responses do not contain exception details
- [ ] Detailed errors still logged to stderr via logger.exception

## Work Log
- 2026-03-22: Created from code review
