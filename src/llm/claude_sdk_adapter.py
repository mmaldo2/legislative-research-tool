"""Adapter to use Claude Agent SDK (subscription auth) as the LLM backend.

When ANTHROPIC_API_KEY is not set, this adapter routes LLM calls through
the Claude Agent SDK, which authenticates via the user's Claude subscription
(claude.ai login). This enables local development and demos without API costs.

The Agent SDK returns responses as streaming events. This adapter collects
the full text and returns it in a format compatible with the Anthropic SDK's
Messages API response shape.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class TextBlock:
    type: str
    text: str


@dataclass
class SDKResponse:
    """Mimics anthropic.types.Message shape for harness compatibility."""

    content: list[TextBlock]
    usage: Usage
    stop_reason: str


def _extract_json(text: str) -> str:
    """Extract JSON from a response that may be wrapped in markdown code blocks."""
    # Try raw JSON first
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped

    # Extract from ```json ... ``` blocks
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Last resort — find first { to last }
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]

    return stripped


class ClaudeSDKClient:
    """Drop-in replacement for anthropic.AsyncAnthropic that routes through
    the Claude Agent SDK (subscription-based auth).

    Implements the subset of the Anthropic client interface used by the harness:
    - messages.create(model, max_tokens, system, messages) -> SDKResponse
    - messages.stream(model, max_tokens, system, messages) -> async context manager
    """

    def __init__(self):
        self.messages = _SDKMessages()


class _SDKMessages:
    """Implements the messages.create() and messages.stream() interface."""

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> SDKResponse:
        """Send a message via the Agent SDK and return a complete response."""
        from claude_agent_sdk import query

        prompt = _build_prompt(system, messages)

        full_text = ""
        async for event in query(prompt=prompt):
            if hasattr(event, "content"):
                for block in event.content:
                    if hasattr(block, "text"):
                        full_text += block.text

        # Extract JSON if the response is wrapped in code blocks
        cleaned = _extract_json(full_text)

        return SDKResponse(
            content=[TextBlock(type="text", text=cleaned)],
            usage=Usage(input_tokens=0, output_tokens=len(full_text) // 4),
            stop_reason="end_turn",
        )

    def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ):
        """Return an async context manager that streams events."""
        return _SDKStream(system, messages)


class _SDKStream:
    """Async context manager that streams Agent SDK events,
    mimicking the anthropic client.messages.stream() interface."""

    def __init__(self, system: str, messages: list[dict]):
        self._system = system
        self._messages = messages
        self._full_text = ""
        self._events: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def __aiter__(self):
        from claude_agent_sdk import query

        prompt = _build_prompt(self._system, self._messages)

        async for event in query(prompt=prompt):
            if hasattr(event, "content"):
                for block in event.content:
                    if hasattr(block, "text"):
                        self._full_text += block.text
                        # Emit a content_block_delta-like event
                        yield _DeltaEvent(text=block.text)

    async def get_final_message(self) -> SDKResponse:
        cleaned = _extract_json(self._full_text)
        return SDKResponse(
            content=[TextBlock(type="text", text=cleaned)],
            usage=Usage(input_tokens=0, output_tokens=len(self._full_text) // 4),
            stop_reason="end_turn",
        )


@dataclass
class _Delta:
    text: str


@dataclass
class _DeltaEvent:
    """Mimics anthropic RawContentBlockDelta event."""

    text: str
    type: str = "content_block_delta"

    @property
    def delta(self):
        return _Delta(text=self.text)


def _build_prompt(system: str, messages: list[dict]) -> str:
    """Convert system prompt + messages into a single prompt string
    for the Agent SDK (which takes a flat prompt, not structured messages)."""
    parts = []
    if system:
        parts.append(f"<system>\n{system}\n</system>\n")

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(f"<{role}>\n{content}\n</{role}>")
        elif isinstance(content, list):
            # Handle tool results and multi-part content
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "tool_result":
                        text_parts.append(
                            f"[Tool result: {item.get('content', '')}]"
                        )
            if text_parts:
                parts.append(f"<{role}>\n{''.join(text_parts)}\n</{role}>")

    return "\n".join(parts)
