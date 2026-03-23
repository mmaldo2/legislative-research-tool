---
title: "MCP Server Integration for Agent SDK Tool Calls"
date: 2026-03-22
category: architecture
module: src/mcp, src/services/chat_service, src/search/engine
tags:
  - mcp
  - agent-sdk
  - tool-calls
  - search
  - subprocess
  - stdio-transport
severity: high
status: implemented
symptoms:
  - Agent SDK adapter could not make tool calls against the database
  - Assistant fell back to pre-fetch hack that misrepresented search capabilities
  - Follow-up queries lost tool awareness (Claude claimed tools were unavailable)
  - MCP subprocess hung for 30-60s on first search (BM25 cold start)
  - MCP tool calls silently blocked waiting for interactive permission confirmation
root_cause: >
  The Claude Agent SDK (subscription auth, no API key) had no mechanism to call
  research tools against PostgreSQL. The fix required an MCP server exposing tools
  via stdio, plus three critical fixes discovered during live testing: permission
  bypass for non-interactive mode, BM25 cold-start fallback, and tool-availability
  prompt anchoring.
---

# MCP Server Integration for Agent SDK Tool Calls

## Problem

The legislative research platform has two LLM auth paths:
1. **Standard**: `ANTHROPIC_API_KEY` set → Anthropic client → native tool-use in agentic loop
2. **SDK**: No API key → `ClaudeSDKClient` → Claude Agent SDK (subscription auth via `claude login`)

The SDK path could not support tool-use loops because `claude.exe` (spawned by the SDK) had no way to call back into our app's tool handlers. The temporary workaround was a pre-fetch hack that ran `search_bills` once before sending to Claude, injecting results as static context. The user explicitly rejected this: *"If the search is a rudimentary keyword search rather than letting the agent search our database, we're sort of misrepresenting what's going on behind the scenes."*

## Solution

### Architecture

An MCP server (`src/mcp/server.py`) exposes all 10 research tools via stdio transport. The Agent SDK spawns it as a subprocess, discovers tools via `tools/list`, and lets Claude call them in its built-in agentic loop.

```
FastAPI App → query(prompt, options=ClaudeAgentOptions(
    mcp_servers={"legis-research": StdioConfig(command="python", args=["-m", "src.mcp.server"])},
    permission_mode="bypassPermissions",
)) → Agent SDK spawns claude.exe → claude.exe spawns MCP server → Claude calls tools via MCP
```

**Key design decisions:**
- **Low-level MCP `Server` API** (not `FastMCP`) — reuses existing JSON schemas from `RESEARCH_TOOLS` directly via `_convert_schema()`
- **`McpStdioServerConfig`** — subprocess isolation, no greenlet concerns, matches IDE integration pattern
- **Agent SDK handles the agentic loop** — our code just calls `query()` and converts events to SSE
- **LLM tool gating** — `_LLM_TOOLS` set blocks `analyze_*` tools in SDK mode to prevent Claude-calling-Claude recursion

### Three Bugs Found During Live Testing

#### Bug 1: Permission Gate (tools silently blocked)

**Symptom:** Claude said "tools are unavailable" despite MCP being configured. MCP server log showed no tool calls at all.

**Root cause:** The Agent SDK defaults to an interactive permission model. Without `permission_mode="bypassPermissions"`, MCP tool calls are silently blocked waiting for terminal confirmation that never comes.

**Fix:** `src/services/chat_service.py`
```python
options = ClaudeAgentOptions(
    mcp_servers={...},
    system_prompt=system_prompt,
    permission_mode="bypassPermissions",  # Required for non-interactive usage
)
```

**Detection:** We added a file-based diagnostic log to the MCP server. When `mcp_server.log` showed zero tool calls despite the server starting, we knew the issue was upstream (SDK not routing calls to MCP).

#### Bug 2: BM25 Cold-Start Blocking (30-60s hang)

**Symptom:** First `search_bills` call hung indefinitely. The MCP log showed `Tool call: search_bills(...)` but never logged a result.

**Root cause:** Each `query()` call spawns a fresh MCP subprocess. The first `search_bills` call triggers `_ensure_bm25_built()`, which loads 100K+ bills from PostgreSQL and builds an in-memory index. This blocks for 30-60 seconds. The main FastAPI process pre-builds this at startup, but the subprocess starts cold.

**Fix:** `src/search/engine.py` — skip BM25 build, fall back to SQL ILIKE:
```python
if _bm25_index.is_built:
    bm25_results = _bm25_index.search(query, top_k=top_k * 2)
else:
    logger.info("BM25 not built, falling back to SQL keyword search")
    stmt = select(Bill.id).where(Bill.title.ilike(f"%{query}%")).limit(top_k * 2)
    result = await session.execute(stmt)
    bm25_results = [(row[0], 1.0) for row in result.all()]
```

#### Bug 3: Conversation History Poisoning

**Symptom:** First query worked (search returned results), but follow-up queries ("Who sponsored those bills?") failed — Claude refused to call `get_bill_detail`, saying tools were unavailable.

**Root cause:** Conversation history is flattened into the prompt. Prior assistant messages containing "I don't have access to tools" (from before fixes were applied) caused Claude to inherit that incorrect belief in subsequent `query()` calls.

**Fix:** `src/services/chat_service.py` — append tool-availability reminder after conversation history:
```python
prompt += (
    "\n\n<system>\nIMPORTANT: You have access to legislative research tools "
    "in this session via MCP. Use them to answer the user's question. "
    "Available tools include: search_bills, get_bill_detail, list_jurisdictions, "
    "find_similar_bills, predict_bill_passage, search_govinfo, get_govinfo_document. "
    "Always use tools to look up real data rather than relying on memory or prior "
    "conversation context.\n</system>"
)
```

## Prevention Strategies

### For Agent SDK + MCP Integration
1. **Always set `permission_mode` explicitly.** Never rely on SDK defaults. Add inline comments explaining why.
2. **Test the actual integration, not mocks.** Unit tests with mocked SDK clients would not have caught any of these three issues. The minimum viable test: spawn real MCP server → create real SDK runner → send prompt → assert tool call happens.
3. **Add a pre-flight tool echo test.** After initializing the SDK, send a throwaway prompt asking Claude to list tools. If MCP tools are absent, fail fast.

### For Subprocess-Based Tool Servers
1. **Startup must be fast** (<2s to respond to first protocol message). Defer heavy initialization.
2. **Add diagnostic logging to a file** (not just stderr, which disappears with the subprocess). This was how we diagnosed Bug 1.
3. **Fall back gracefully** when resources aren't available. SQL ILIKE instead of BM25 is lower quality but instant.
4. **Filter the subprocess environment** — only pass required variables via an explicit allowlist (`_MCP_ENV_ALLOWLIST`).

### For Conversation History
1. **History is untrusted input.** Prior assistant messages can contain incorrect claims. System prompt anchoring overrides them.
2. **Place reminders after history, not before.** Models weight recent context more heavily than distant context.
3. **Configuration changes invalidate history.** If tool configuration changes, start a new conversation.

## Files Changed

| File | Change |
|------|--------|
| `src/mcp/__init__.py` | New — package marker |
| `src/mcp/server.py` | New — MCP server with 10 tools via stdio |
| `src/services/chat_service.py` | New — `stream_sdk_agentic_chat()`, SDK prompt helpers, env filtering |
| `src/api/chat.py` | Modified — replaced pre-fetch fallback with MCP path |
| `src/api/policy_workspaces.py` | Modified — added SDK/MCP path for workspace chat parity |
| `src/search/engine.py` | Modified — BM25 fallback to SQL ILIKE |
| `pyproject.toml` | Modified — added `mcp>=1.20.0`, `legis-mcp` entry point |
| `tests/test_mcp/test_server.py` | New — 16 unit tests |
| `CLAUDE.md` | Modified — MCP server commands and architecture notes |

## Cross-References

- [Composer v1.5 IDE Integration](composer-v1.5-ide-integration.md) — predecessor architecture doc (load-call-persist pattern, streaming, SDK adapter)
- [P2 Refactor Findings](p2-refactor-findings-resolution.md) — service layer patterns extended here
- [MCP Server Plan](../../plans/2026-03-22-feat-mcp-server-research-tools-plan.md) — implementation plan with risk analysis
- [Remaining Work Bundles](../../plans/2026-03-22-remaining-work-bundles.md) — Bundle 0 (this work) + follow-on bundles
