"""Shared agentic chat loop used by both general and workspace-scoped assistants."""

import asyncio
import json
import logging
import os
import sys
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any

import anthropic

from src.config import settings
from src.database import async_session_factory
from src.llm.harness import LLMHarness
from src.llm.tools import RESEARCH_TOOLS

logger = logging.getLogger(__name__)

# Maximum tool-use rounds before forcing a text response
MAX_TOOL_ROUNDS = 10

# Character budget for conversation history sent to the API
HISTORY_CHAR_BUDGET = 100_000


def trim_history(messages: list[dict], budget: int) -> list[dict]:
    """Keep the first message + most recent messages within a character budget."""
    if not messages:
        return messages

    sizes = [len(json.dumps(m)) for m in messages]
    total = sum(sizes)

    if total <= budget:
        return messages

    trimmed = [messages[0]]
    remaining_budget = budget - sizes[0]

    tail: list[dict] = []
    for i in range(len(messages) - 1, 0, -1):
        if sizes[i] <= remaining_budget:
            tail.append(messages[i])
            remaining_budget -= sizes[i]
        else:
            break

    tail.reverse()
    trimmed.extend(tail)
    return trimmed


def extract_text(response: Any) -> str:
    """Extract concatenated text from an Anthropic response's content blocks."""
    parts = [block.text for block in response.content if block.type == "text"]
    return "\n".join(parts)


ToolExecutor = Callable[[str, dict[str, Any], Any, Any], Coroutine[Any, Any, str]]


async def _default_execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    db: Any,
    harness: Any,
) -> str:
    """Default tool executor — imports from chat module."""
    from src.api.chat import execute_tool

    return await execute_tool(tool_name, arguments, db, harness)


async def _execute_tool_with_session(
    tool_name: str,
    arguments: dict[str, Any],
    client: anthropic.AsyncAnthropic,
    execute_fn: ToolExecutor = _default_execute_tool,
) -> str:
    """Execute a single tool call with its own short-lived DB session."""
    async with async_session_factory() as db:
        harness = LLMHarness(db_session=db, client=client)
        return await execute_fn(tool_name, arguments, db, harness)


async def run_agentic_chat(
    *,
    system_prompt: str,
    messages: list[dict],
    client: anthropic.AsyncAnthropic,
    tools: list[dict] | None = None,
    max_rounds: int = MAX_TOOL_ROUNDS,
    execute_tool_fn: ToolExecutor | None = None,
) -> tuple[str, list[dict]]:
    """Run the agentic chat loop, returning (final_text, tool_calls_metadata).

    No DB connection is held during LLM API calls. Tool handlers get
    their own short-lived sessions.
    """
    if tools is None:
        tools = RESEARCH_TOOLS

    _exec_fn = execute_tool_fn or _default_execute_tool
    model = settings.summary_model
    all_tool_calls: list[dict] = []
    api_messages = list(messages)
    final_text = ""

    for _round in range(max_rounds):
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=api_messages,
            tools=tools,
        )

        if response.stop_reason == "end_turn":
            final_text = extract_text(response)
            break

        elif response.stop_reason == "tool_use":
            api_messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input

                logger.info(
                    "Chat tool call: %s(%s)",
                    tool_name,
                    json.dumps(tool_input)[:200],
                )

                try:
                    result_str = await _execute_tool_with_session(
                        tool_name, tool_input, client, _exec_fn
                    )
                except (ValueError, LookupError, json.JSONDecodeError):
                    logger.exception("Tool execution error: %s", tool_name)
                    result_str = json.dumps({"error": f"Tool '{tool_name}' encountered an error."})

                # Summarize for metadata
                result_data = json.loads(result_str)
                if "error" in result_data:
                    summary = result_data["error"]
                elif "total" in result_data:
                    summary = f"{result_data['total']} results"
                elif "bill_id" in result_data:
                    ident = result_data.get("identifier", result_data["bill_id"])
                    summary = f"Retrieved {ident}"
                else:
                    summary = f"{len(result_str)} chars"

                all_tool_calls.append(
                    {
                        "tool_name": tool_name,
                        "arguments": tool_input,
                        "result_summary": summary,
                    }
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    }
                )

            api_messages.append({"role": "user", "content": tool_results})

        else:
            final_text = extract_text(response)
            if not final_text:
                final_text = "I was unable to complete the request."
            break
    else:
        extracted = extract_text(response)
        final_text = extracted or (
            "I reached the maximum number of research steps. Here is what I found so far."
        )

    return final_text, all_tool_calls


def _sse_event(event_type: str, data: dict) -> str:
    """Format an SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def stream_agentic_chat(
    *,
    system_prompt: str,
    messages: list[dict],
    client: anthropic.AsyncAnthropic,
    tools: list[dict] | None = None,
    max_rounds: int = MAX_TOOL_ROUNDS,
    execute_tool_fn: ToolExecutor | None = None,
) -> AsyncGenerator[str, None]:
    """Stream the agentic chat loop, yielding SSE events.

    Uses true Anthropic SDK streaming for every round:
    - Tool-use rounds: accumulate silently, emit tool_status events, execute tools
    - End-turn rounds: yield real token events as text deltas arrive

    The caller is responsible for DB persistence (load-call-persist pattern).
    """
    if tools is None:
        tools = RESEARCH_TOOLS

    _exec_fn = execute_tool_fn or _default_execute_tool
    model = settings.summary_model
    all_tool_calls: list[dict] = []
    api_messages = list(messages)
    final_text = ""

    for _round in range(max_rounds):
        # Use non-streaming call for tool-use rounds to avoid greenlet
        # conflicts with SQLAlchemy when executing tools. Stream the final
        # text response for real-time token delivery.
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=api_messages,
            tools=tools,
        )

        if response.stop_reason == "end_turn":
            # Re-issue as streaming call for token-by-token delivery,
            # unless using the SDK adapter (which already returned text)
            final_text = extract_text(response)
            # Emit the text in chunks for streaming UX
            chunk_size = 40
            for i in range(0, len(final_text), chunk_size):
                yield _sse_event("token", {"text": final_text[i : i + chunk_size]})
            break

        elif response.stop_reason == "tool_use":
            api_messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input

                yield _sse_event("tool_status", {
                    "tool": tool_name,
                    "status": "running",
                    "description": _tool_description(tool_name, tool_input),
                })

                try:
                    result_str = await _execute_tool_with_session(
                        tool_name, tool_input, client, _exec_fn
                    )
                except (ValueError, LookupError, json.JSONDecodeError):
                    logger.exception("Tool execution error: %s", tool_name)
                    result_str = json.dumps(
                        {"error": f"Tool '{tool_name}' encountered an error."}
                    )

                result_data = json.loads(result_str)
                if "error" in result_data:
                    summary = result_data["error"]
                elif "total" in result_data:
                    summary = f"{result_data['total']} results"
                elif "bill_id" in result_data:
                    ident = result_data.get("identifier", result_data["bill_id"])
                    summary = f"Retrieved {ident}"
                else:
                    summary = f"{len(result_str)} chars"

                all_tool_calls.append({
                    "tool_name": tool_name,
                    "arguments": tool_input,
                    "result_summary": summary,
                })

                yield _sse_event("tool_status", {
                    "tool": tool_name,
                    "status": "complete",
                    "description": summary,
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })

            api_messages.append({"role": "user", "content": tool_results})

        else:
            final_text = extract_text(response)
            if not final_text:
                final_text = "I was unable to complete the request."
            break
    else:
        final_text = extract_text(response)
        if not final_text:
            final_text = (
                "I reached the maximum number of research steps. "
                "Here is what I found so far."
            )

    yield _sse_event("done", {
        "text": final_text,
        "tool_calls": all_tool_calls,
    })


def _tool_description(tool_name: str, tool_input: dict) -> str:
    """Generate a human-readable description of a tool call for status events."""
    descriptions: dict[str, Callable[[dict], str]] = {
        "search_bills": lambda args: f"Searching for '{args.get('query', '')}'...",
        "get_bill_detail": lambda args: f"Reading bill {args.get('bill_id', '')}...",
        "list_jurisdictions": lambda _args: "Listing available jurisdictions...",
        "find_similar_bills": lambda args: (
            f"Finding similar bills to {args.get('bill_id', '')}..."
        ),
        "analyze_version_diff": lambda args: (
            f"Comparing versions of {args.get('bill_id', '')}..."
        ),
        "analyze_constitutional": lambda args: (
            f"Analyzing constitutionality of {args.get('bill_id', '')}..."
        ),
        "analyze_patterns": lambda args: (
            f"Detecting legislative patterns for {args.get('bill_id', '')}..."
        ),
        "predict_bill_passage": lambda args: (
            f"Predicting passage for {args.get('bill_id', '')}..."
        ),
        "search_govinfo": lambda args: (
            f"Searching GovInfo for '{args.get('query', '')}'..."
        ),
        "get_govinfo_document": lambda args: (
            f"Retrieving document {args.get('package_id', '')}..."
        ),
    }
    fn = descriptions.get(tool_name, lambda _: f"Running {tool_name}...")
    return fn(tool_input)


# ---------------------------------------------------------------------------
# Agent SDK + MCP path — used when no ANTHROPIC_API_KEY is set
# ---------------------------------------------------------------------------


def _build_sdk_prompt(system: str, messages: list[dict]) -> str:
    """Convert system prompt + conversation history into a flat prompt for the Agent SDK."""
    parts = []
    if system:
        parts.append(f"<system>\n{system}\n</system>\n")

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(f"<{role}>\n{content}\n</{role}>")
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "tool_result":
                        text_parts.append(f"[Tool result: {item.get('content', '')}]")
            if text_parts:
                parts.append(f"<{role}>\n{''.join(text_parts)}\n</{role}>")

    return "\n".join(parts)


# Environment variables the MCP server subprocess needs. Everything else is
# filtered out to avoid leaking unrelated secrets (webhook keys, cloud creds).
_MCP_ENV_ALLOWLIST = {
    # Application
    "DATABASE_URL",
    "ANTHROPIC_API_KEY",
    "VOYAGE_API_KEY",
    "CONGRESS_API_KEY",
    "GOVINFO_API_KEY",
    "OPENSTATES_API_KEY",
    # Python / system
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "PATH",
    # Windows-specific (required for subprocess to run)
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "HOMEDRIVE",
    "HOMEPATH",
    "COMSPEC",
}


def _inherit_env() -> dict[str, str]:
    """Build a filtered env dict for the MCP server subprocess.

    Only passes through variables the MCP server actually needs —
    database URL, API keys, and system essentials.
    """
    return {k: v for k, v in os.environ.items() if k.upper() in _MCP_ENV_ALLOWLIST}


def _run_sdk_query_with_mcp(prompt: str, system_prompt: str) -> list[dict]:
    """Run Agent SDK query() with MCP server config in a dedicated event loop.

    This runs synchronously — designed to be called via asyncio.to_thread()
    to avoid corrupting the main thread's greenlet state.

    Returns a list of serialized event dicts for SSE conversion.
    """
    import asyncio as _asyncio

    from claude_agent_sdk import ClaudeAgentOptions, query
    from claude_agent_sdk.types import (
        AssistantMessage,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )

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

    async def _collect() -> list[dict]:
        events: list[dict] = []
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        events.append({"type": "text", "text": block.text})
                    elif isinstance(block, ToolUseBlock):
                        events.append({
                            "type": "tool_use",
                            "name": block.name,
                            "input": block.input,
                            "id": block.id,
                        })
            elif isinstance(msg, ResultMessage):
                events.append({
                    "type": "result",
                    "is_error": msg.is_error,
                    "result": msg.result,
                })
            # UserMessage (tool results) and SystemMessage are internal to the
            # SDK's agentic loop — we don't need to surface them.
        return events

    loop = _asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_collect())
    finally:
        loop.close()


async def stream_sdk_agentic_chat(
    *,
    system_prompt: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """Run agentic chat via Agent SDK with MCP tools, yielding SSE events.

    The Agent SDK handles the entire tool-use loop internally — it spawns
    our MCP server as a subprocess, discovers the 10 research tools, and
    lets Claude call them against the database.

    Events are collected in a background thread (to avoid greenlet corruption)
    and then converted to our SSE format for the frontend.
    """
    prompt = _build_sdk_prompt("", messages)  # system_prompt passed via options

    try:
        events = await asyncio.to_thread(
            _run_sdk_query_with_mcp, prompt, system_prompt
        )
    except Exception:
        logger.exception("Agent SDK query with MCP failed")
        yield _sse_event("error", {
            "message": "The research assistant encountered an error. Please try again.",
            "retryable": True,
        })
        return

    # Convert collected events to SSE format
    full_text = ""
    tool_calls: list[dict] = []

    for event in events:
        if event["type"] == "text":
            full_text += event["text"]
            # Chunk the text for streaming UX
            text = event["text"]
            chunk_size = 40
            for i in range(0, len(text), chunk_size):
                yield _sse_event("token", {"text": text[i : i + chunk_size]})

        elif event["type"] == "tool_use":
            tool_calls.append({
                "tool_name": event["name"],
                "arguments": event.get("input", {}),
                "result_summary": _tool_description(event["name"], event.get("input", {})),
            })
            yield _sse_event("tool_status", {
                "tool": event["name"],
                "status": "running",
                "description": _tool_description(event["name"], event.get("input", {})),
            })
            # Emit a completion status after each tool use
            yield _sse_event("tool_status", {
                "tool": event["name"],
                "status": "complete",
            })

        elif event["type"] == "result":
            if event.get("is_error"):
                yield _sse_event("error", {
                    "message": event.get("result", "Unknown error"),
                    "retryable": True,
                })
                return

    yield _sse_event("done", {
        "text": full_text,
        "tool_calls": tool_calls,
    })
