---
title: "feat: MCP server for research tools (Bundle 0)"
type: feat
status: active
date: 2026-03-22
---

# MCP Server for Research Tools

## Overview

Build an MCP (Model Context Protocol) server that exposes our 10 legislative research tools so the Claude Agent SDK can make tool calls against our database. This is "Bundle 0" — the highest-priority work item because it unblocks the assistant's core agentic functionality for subscription-auth users (no API key).

Today, the assistant works with tool calls when `ANTHROPIC_API_KEY` is set (standard Anthropic client), but falls back to a pre-fetch hack when using the Agent SDK adapter. The user explicitly rejected that fallback: *"If the search is a rudimentary keyword search rather than letting the agent search our database, we're sort of misrepresenting what's going on behind the scenes."*

MCP bridges the gap. The Agent SDK's `query()` function natively supports MCP servers — it spawns the server, discovers tools, and lets Claude use them in its built-in agentic loop.

## Problem Statement

The `ClaudeSDKClient` adapter (`src/llm/claude_sdk_adapter.py`) routes LLM calls through the Agent SDK (subscription auth via `claude login`). This works for single-turn operations (compose, outline) but **cannot support tool-use loops** because:

1. The Agent SDK runs `claude.exe` as a subprocess
2. `claude.exe` has no way to call back into our app's tool handlers
3. The current workaround (pre-fetch search results, inject as context, disable tools) misrepresents what the system is doing

MCP solves this: our MCP server runs as a subprocess alongside `claude.exe`, and Claude calls tools via the MCP protocol.

## Proposed Solution

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  FastAPI App (main process)                         │
│                                                     │
│  POST /chat/stream                                  │
│    ├─ API key set? → Anthropic client               │
│    │   → stream_agentic_chat() (existing, unchanged)│
│    │                                                │
│    └─ No API key? → Agent SDK path (NEW)            │
│        → query(prompt, options=ClaudeAgentOptions(   │
│            mcp_servers={"legis": StdioConfig(        │
│              command="python",                       │
│              args=["-m", "src.mcp.server"]           │
│            )},                                      │
│            system_prompt=SYSTEM_PROMPT               │
│          ))                                         │
│        → Agent SDK spawns claude.exe                 │
│        → claude.exe spawns MCP server subprocess     │
│        → Claude calls tools via MCP protocol         │
│        → Events stream back to our app               │
│        → We convert to SSE format for frontend       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  MCP Server (subprocess, stdio transport)           │
│  python -m src.mcp.server                           │
│                                                     │
│  tools/list → returns 10 tools with JSON schemas    │
│  tools/call → dispatches to existing handlers:      │
│    ├─ search_bills      → hybrid_search (DB)        │
│    ├─ get_bill_detail   → bill lookup (DB)          │
│    ├─ list_jurisdictions → jurisdiction query (DB)  │
│    ├─ find_similar_bills → pgvector search (DB)     │
│    ├─ predict_bill_passage → ML model (DB + model)  │
│    ├─ analyze_version_diff → LLM analysis (DB+LLM)  │
│    ├─ analyze_constitutional → LLM analysis (DB+LLM)│
│    ├─ analyze_patterns  → LLM analysis (DB+LLM)    │
│    ├─ search_govinfo    → GovInfo API (HTTP)        │
│    └─ get_govinfo_document → GovInfo API (HTTP)     │
└─────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Low-level MCP `Server` API** (not `FastMCP`): Our tool schemas already exist in `RESEARCH_TOOLS` (Anthropic format). The low-level API lets us pass these schemas directly via `list_tools()` and dispatch via `call_tool()` — no schema re-specification or decorator repetition.

2. **`McpStdioServerConfig` for Agent SDK**: The MCP server runs as a subprocess spawned by the Agent SDK. This gives process isolation (no greenlet concerns), clean lifecycle management, and matches how IDEs use MCP.

3. **The Agent SDK handles the agentic loop**: Instead of trying to run our `stream_agentic_chat()` through the SDK adapter, we let the Agent SDK's built-in agentic loop do the work. Our `query()` call with MCP config is the entire interaction — the SDK handles tool discovery, tool calls, and iteration.

4. **Reuse existing tool handlers**: The MCP server imports `execute_tool` from `src/api/chat.py` and creates its own DB sessions per tool call (same pattern as `_execute_tool_with_session` in `chat_service.py`).

5. **Standalone and embedded use**: The server works both as a standalone process (`python -m src.mcp.server` for IDE/Claude Desktop integration) and as a subprocess spawned by the Agent SDK.

## Technical Approach

### Implementation Phases

#### Phase 1: MCP Server Core

Build the MCP server that exposes all 10 tools via stdio transport.

- [x] Create `src/mcp/__init__.py`
- [x] Create `src/mcp/server.py` with low-level MCP `Server`
  - `@server.list_tools()` → returns tools from `RESEARCH_TOOLS` (schema translation: `input_schema` → `inputSchema`)
  - `@server.call_tool()` → creates async DB session, instantiates `LLMHarness`, calls `execute_tool()`, returns `TextContent`
  - Error handling: tool errors return `TextContent` with error JSON (not MCP-level errors) so Claude can reason about them
  - `main()` entry point that runs `stdio_server()`
  - Logging configured to stderr (stdout is the MCP protocol channel)
- [x] Add `mcp>=1.20.0` to `pyproject.toml` dependencies
- [x] Add `legis-mcp = "src.mcp.server:main"` to `[project.scripts]`
- [ ] Verify server starts and responds to `tools/list` (manual test with `mcp dev`)

**`src/mcp/server.py` sketch:**

```python
"""MCP server exposing legislative research tools via stdio transport."""

import json
import logging
import sys

import mcp.types as types
from mcp.server.lowlevel import Server

from src.api.chat import execute_tool
from src.database import async_session_factory
from src.llm.tools import RESEARCH_TOOLS

# Route logs to stderr (stdout is the MCP protocol channel)
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

server = Server("legis-research")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=t["name"],
            description=t["description"],
            inputSchema=t["input_schema"],
        )
        for t in RESEARCH_TOOLS
    ]


@server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[types.TextContent]:
    from src.api.deps import get_anthropic_client
    from src.llm.harness import LLMHarness

    try:
        async with async_session_factory() as db:
            client = get_anthropic_client()
            harness = LLMHarness(db_session=db, client=client)
            result = await execute_tool(name, arguments, db, harness)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        error_json = json.dumps({"error": str(e)})
        return [types.TextContent(type="text", text=error_json)]


async def run_stdio():
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    import anyio
    anyio.run(run_stdio)


if __name__ == "__main__":
    main()
```

#### Phase 2: Agent SDK Integration

Wire the MCP server into the chat stream endpoint so the Agent SDK path uses real tools instead of the pre-fetch fallback.

- [x] Add `stream_sdk_agentic_chat()` to `src/services/chat_service.py`
  - Accepts `system_prompt`, `messages`, returns `AsyncGenerator[str, None]` (SSE events)
  - Calls `query()` with `ClaudeAgentOptions(mcp_servers=..., system_prompt=...)`
  - Runs in `asyncio.to_thread()` to avoid greenlet corruption (same pattern as adapter)
  - Converts Agent SDK events to our SSE format (`token`, `tool_status`, `done`)
  - Includes conversation history in the prompt (flatten messages like `_build_prompt()`)
- [x] Modify `src/api/chat.py` `chat_stream` endpoint
  - Replace the `use_sdk_fallback` branch (lines 607-665) with `stream_sdk_agentic_chat()` call
  - Remove the pre-fetch search code entirely
  - Keep the standard API path (`stream_agentic_chat`) completely unchanged
- [ ] Test end-to-end: user message → Agent SDK → MCP → tool call → DB query → response
- [x] Add SDK/MCP path to workspace chat endpoint (API surface parity)

**`stream_sdk_agentic_chat()` sketch:**

```python
async def stream_sdk_agentic_chat(
    *,
    system_prompt: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """Run agentic chat via Agent SDK with MCP tools.

    The Agent SDK handles the entire tool-use loop. We convert its
    events to our SSE format for the frontend.
    """
    import sys
    from pathlib import Path

    def _run_sync(prompt: str) -> list[dict]:
        """Run query() synchronously in a dedicated event loop/thread."""
        import asyncio as _asyncio
        from claude_agent_sdk import query, ClaudeAgentOptions

        options = ClaudeAgentOptions(
            mcp_servers={
                "legis-research": {
                    "command": sys.executable,
                    "args": ["-m", "src.mcp.server"],
                    "env": _inherit_env(),
                }
            },
            system_prompt=system_prompt,
        )

        async def _collect():
            events = []
            async for event in query(prompt=prompt, options=options):
                events.append(_serialize_event(event))
            return events

        loop = _asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_collect())
        finally:
            loop.close()

    # Build flat prompt from messages
    prompt = _build_prompt_for_sdk(messages)

    # Run in thread to avoid greenlet corruption
    events = await asyncio.to_thread(_run_sync, prompt)

    # Convert to SSE events
    full_text = ""
    tool_calls = []
    for event in events:
        if event["type"] == "text":
            full_text += event["text"]
            yield _sse_event("token", {"text": event["text"]})
        elif event["type"] == "tool_use":
            tool_calls.append(event)
            yield _sse_event("tool_status", {
                "status": "running",
                "description": _tool_description(event["name"]),
            })
        elif event["type"] == "tool_result":
            yield _sse_event("tool_status", {"status": "complete"})

    yield _sse_event("done", {
        "text": full_text,
        "tool_calls": tool_calls,
    })
```

#### Phase 3: Testing, Cleanup & Documentation

- [ ] Add `tests/test_mcp_server.py` — integration test
  - Spawn MCP server as subprocess
  - Send `tools/list` request, verify 10 tools returned with correct schemas
  - Send `tools/call` for `list_jurisdictions`, verify valid JSON response
  - Send `tools/call` for `search_bills`, verify results
  - Test error handling (invalid tool name, missing required args)
- [ ] Remove dead pre-fetch fallback code from `src/api/chat.py`
- [ ] Update `CLAUDE.md` with MCP server info (commands, architecture note)
- [ ] Verify Claude Desktop configuration works (add config example)
- [ ] Manual end-to-end test: full assistant conversation with tool calls via SDK adapter

## System-Wide Impact

### Interaction Graph

```
User message → POST /chat/stream → SDK adapter check
  → asyncio.to_thread(_run_sync)
    → claude_agent_sdk.query(prompt, options)
      → spawns claude.exe subprocess
        → spawns python -m src.mcp.server subprocess
          → MCP server imports src.database (creates engine)
          → MCP server imports src.api.chat (execute_tool)
        → Claude sends tools/list → 10 tools returned
        → Claude sends tools/call(search_bills, {query: "..."})
          → MCP handler creates AsyncSession
          → calls execute_tool("search_bills", args, db, harness)
            → calls hybrid_search() → BM25 + pgvector
          → returns JSON result as TextContent
        → Claude may call more tools (up to Agent SDK limits)
        → Claude generates final text response
      → events stream back to _collect()
    → thread returns events list
  → main async loop converts to SSE events
  → StreamingResponse sends to frontend
```

### Error & Failure Propagation

| Error Source | How It Surfaces | Handling |
|---|---|---|
| MCP server fails to start | Agent SDK raises exception | Caught in `_run_sync`, yielded as SSE error event |
| DB connection fails in MCP | Tool handler raises, caught in `call_tool` | Returns error JSON as TextContent; Claude retries or reports |
| Tool handler exception | Caught in `call_tool` exception handler | Returns `{"error": "..."}` as TextContent |
| Agent SDK subprocess crash | `query()` raises exception | Caught in `asyncio.to_thread`, yielded as SSE error |
| Claude exceeds tool rounds | Agent SDK manages internally | Final text returned with partial results |
| Missing env vars (API keys) | Tool returns error JSON | Claude tells user which tool failed and why |

### State Lifecycle Risks

- **MCP server DB sessions**: Each `call_tool` creates and closes its own session via `async with async_session_factory()`. No sessions leak because the `async with` block guarantees cleanup.
- **LLM-powered tools**: `analyze_constitutional` etc. call `db.commit()` internally to cache results. This is safe — the `async with` block auto-commits on clean exit.
- **BM25 cold start**: First `search_bills` call in a new MCP server process triggers BM25 index build (~30-60s for large corpus). Mitigation: accept the latency for v1; the index is built once per MCP process lifetime.
- **Process cleanup**: When `claude.exe` terminates, the MCP server subprocess is killed. In-flight DB sessions are cleaned up by asyncpg's connection pool (connections are released on process exit).

### API Surface Parity

| Interface | Tool Support | Notes |
|---|---|---|
| `POST /chat/stream` (API key) | Full — `stream_agentic_chat()` | Unchanged |
| `POST /chat/stream` (SDK adapter) | Full — via MCP | **NEW** — replaces pre-fetch fallback |
| `POST /workspaces/{id}/chat/stream` | Full — both paths | Uses same client dispatch |
| Claude Desktop | Full — via MCP stdio | **NEW** — standalone MCP server |
| IDE (Cursor/VS Code) | Full — via MCP stdio | **NEW** — standalone MCP server |

## Acceptance Criteria

### Functional Requirements

- [ ] `python -m src.mcp.server` starts and responds to MCP protocol over stdio
- [ ] `tools/list` returns all 10 tools with correct names, descriptions, and schemas
- [ ] `tools/call` for each DB-only tool returns valid JSON results
- [ ] `tools/call` for GovInfo tools works when API key is set, returns error JSON when not
- [ ] `tools/call` for LLM-powered tools works when `ANTHROPIC_API_KEY` is set
- [ ] Assistant chat works end-to-end via SDK adapter: user asks question → Claude calls tools → gets real database results → responds with citations
- [ ] Pre-fetch fallback code is removed from `chat_stream`
- [ ] Standard API path (`ANTHROPIC_API_KEY` set) is completely unaffected
- [ ] Frontend streaming UX works: tool status indicators appear, tokens stream in real-time

### Non-Functional Requirements

- [ ] MCP server starts in <5s (excluding BM25 build)
- [ ] Tool calls complete in <10s for DB-only tools
- [ ] No connection pool exhaustion under normal use (single concurrent user)
- [ ] Logs go to stderr, not stdout (preserving MCP protocol channel)

### Quality Gates

- [ ] `pytest tests/test_mcp_server.py` passes
- [ ] `ruff check src/mcp/` passes
- [ ] Manual demo: full assistant conversation with 2+ tool calls via SDK adapter

## Dependencies & Prerequisites

| Dependency | Status | Notes |
|---|---|---|
| `mcp` Python package (>=1.20.0) | Available on PyPI | Already a transitive dep of `claude-agent-sdk` |
| `claude-agent-sdk` with MCP support | Installed (v0.1.50) | Supports `McpStdioServerConfig` |
| PostgreSQL running locally | Required | For tool handlers that query DB |
| `claude login` completed | Required | For Agent SDK subscription auth |
| Existing tool handlers | Ready | `src/api/chat.py` — all 10 handlers working |

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| BM25 cold start makes first search slow (30-60s) | High | Medium | Accept for v1; keyword fallback still works. Future: pre-build in MCP lifespan |
| Agent SDK event format doesn't include tool call details | Medium | High | Inspect actual SDK events early in Phase 2; adjust SSE conversion |
| LLM-powered tools fail without API key in MCP process | Medium | Low | These tools fall back to `ClaudeSDKClient` in MCP process. If nested SDK calls fail, return error JSON — Claude still has DB-only tools |
| Agent SDK spawns new MCP server per `query()` call | High | Medium | Each query pays startup cost. Pool size kept small (2 connections). Future: `McpSdkServerConfig` for in-process optimization |
| Env vars not inherited by MCP subprocess | Low | High | Standard subprocess inherits parent env. Pass explicitly in `McpStdioServerConfig.env` as safety measure |
| `execute_tool` import pulls in FastAPI deps | Low | Low | Extra memory (~10MB) in MCP process but no functional impact |

## Future Considerations

1. **`McpSdkServerConfig` (in-process MCP)**: Run the MCP server in the same process as the FastAPI app, avoiding subprocess overhead. The low-level `Server` object is directly compatible. This eliminates BM25 cold start and shares the connection pool.

2. **Claude Desktop config**: Ship a `claude_desktop_config.json` template so users can add legislative research tools to Claude Desktop with one config change.

3. **Tool filtering by availability**: Only register tools whose dependencies are available (e.g., skip `search_govinfo` when no API key, skip `predict_bill_passage` when models not loaded).

4. **MCP resources**: Expose bill texts, jurisdiction lists, and workspace drafts as MCP resources (read-only data the LLM can access without tool calls).

5. **SSE transport**: Add HTTP-based MCP transport for remote access (web-based MCP clients, multi-user deployment).

## Sources & References

### Internal References

- Tool definitions: `src/llm/tools.py` (RESEARCH_TOOLS list, 10 tools with JSON schemas)
- Tool handlers: `src/api/chat.py:401` (`execute_tool` dispatcher + `_TOOL_HANDLERS` registry)
- SDK adapter: `src/llm/claude_sdk_adapter.py` (ClaudeSDKClient, greenlet workarounds)
- Chat service: `src/services/chat_service.py` (agentic loop, `_execute_tool_with_session`)
- Database: `src/database.py` (module-level engine + async_session_factory)
- Client selection: `src/api/deps.py:get_anthropic_client()` (API key → standard client, no key → SDK adapter)
- Pre-fetch fallback to revert: `src/api/chat.py:607-665`

### External References

- MCP Python SDK: `mcp` package (v1.26.0) — low-level `Server` API at `mcp.server.lowlevel`
- Agent SDK types: `claude_agent_sdk.types` — `ClaudeAgentOptions`, `McpStdioServerConfig`
- Agent SDK query: `claude_agent_sdk.query` — `query(prompt, options)` with MCP server support
- Agentic IDE research: `C:\Users\marcu\Downloads\agentic-ide-tool-call-architecture.md`
- Remaining work bundles: `docs/plans/2026-03-22-remaining-work-bundles.md`
- MCP specification: https://modelcontextprotocol.io

### Related Work

- Prior work: Composer v1.5 IDE integration (streaming, agentic chat, SDK adapter)
- Memory: `project_mcp_server_next.md` — prior session's analysis and next-step agreement
- Memory: `project_sdk_adapter.md` — SDK adapter architecture documentation
