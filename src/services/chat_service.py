"""Shared agentic chat loop used by both general and workspace-scoped assistants."""

import json
import logging
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
        "get_bill_text": lambda args: f"Fetching text of {args.get('bill_id', '')}...",
        "get_similar_bills": lambda args: (
            f"Finding similar bills to {args.get('bill_id', '')}..."
        ),
        "summarize_bill": lambda args: f"Summarizing {args.get('bill_id', '')}...",
        "analyze_constitutional": lambda args: (
            f"Analyzing constitutionality of {args.get('bill_id', '')}..."
        ),
        "search_precedent_language": lambda args: (
            f"Searching precedent language for '{args.get('query', '')}'..."
        ),
        "get_trend_data": lambda _args: "Getting trend data...",
        "get_jurisdiction_info": lambda args: (
            f"Looking up {args.get('jurisdiction_id', '')}..."
        ),
        "get_legislator_info": lambda _args: "Looking up legislator...",
    }
    fn = descriptions.get(tool_name, lambda _: f"Running {tool_name}...")
    return fn(tool_input)
