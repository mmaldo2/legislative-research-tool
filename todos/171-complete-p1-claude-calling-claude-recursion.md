---
status: pending
priority: p1
issue_id: 171
tags: [code-review, architecture, security]
dependencies: []
---

# Claude-Calling-Claude Recursion Risk in MCP Server

## Problem Statement
When the MCP server runs in SDK mode (no `ANTHROPIC_API_KEY`), `get_anthropic_client()` returns a `ClaudeSDKClient`. LLM-powered tools (`analyze_constitutional`, `analyze_version_diff`, `analyze_patterns`) use this client via `LLMHarness`, spawning another Agent SDK subprocess — creating Claude-calling-Claude recursion with unbounded cost.

## Findings
- **Agent**: architecture-strategist
- **Evidence**: `src/mcp/server.py:58` calls `get_anthropic_client()` which falls back to `ClaudeSDKClient` when no API key. LLM tools at `src/api/chat.py:253-340` then invoke `harness` methods.
- **Impact**: Unbounded API cost multiplication, potential event loop nesting errors, degraded quality (inner SDK call has no MCP tools)

## Proposed Solutions
### Option A: Skip LLM-powered tools when no API key (Recommended)
- **Effort**: Small (20 min)
- **Risk**: Low — users lose 3 analysis tools in SDK mode but keep 7 data tools
- In `call_tool`, check if tool requires LLM and API key is missing → return error JSON explaining tool unavailable in subscription mode
- Data-only tools: pass `harness=None` to `execute_tool`

### Option B: Guard with API key check
- **Effort**: Small
- **Risk**: Low
- Check `settings.anthropic_api_key` before creating harness. If missing, pass `harness=None`. LLM tools return their own "harness required" error.

## Technical Details
- **File**: `src/mcp/server.py:52-65`
- **LLM tools**: `analyze_version_diff`, `analyze_constitutional`, `analyze_patterns`
- **Data tools**: `search_bills`, `get_bill_detail`, `list_jurisdictions`, `find_similar_bills`, `predict_bill_passage`, `search_govinfo`, `get_govinfo_document`

## Acceptance Criteria
- [ ] LLM-powered tools return clear error when no API key, not recursive SDK calls
- [ ] Data-only tools work normally regardless of API key presence
- [ ] No nested Agent SDK subprocess spawning

## Work Log
- 2026-03-22: Created from code review
