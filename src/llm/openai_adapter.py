"""OpenAI adapter exposing an Anthropic-like `messages` interface.

This keeps the existing LLMHarness mostly unchanged while allowing the broader
analysis/reporting system to run against OpenAI models.
"""

import json
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class TextBlock:
    type: str
    text: str


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class OpenAIResponse:
    content: list[TextBlock]
    usage: Usage
    stop_reason: str


@dataclass
class _Delta:
    text: str


@dataclass
class _DeltaEvent:
    text: str
    type: str = "content_block_delta"

    @property
    def delta(self):
        return _Delta(text=self.text)


class OpenAICompatClient:
    """Compatibility wrapper for the subset of the Anthropic client we use."""

    def __init__(self, api_key: str):
        self._client = AsyncOpenAI(api_key=api_key)
        self.messages = _OpenAIMessages(self._client)


class _OpenAIMessages:
    def __init__(self, client: AsyncOpenAI):
        self._client = client

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> OpenAIResponse:
        request: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "messages": _to_openai_messages(system, messages),
        }
        if tools:
            request["tools"] = _to_openai_tools(tools)
            request["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**request)
        message = response.choices[0].message
        usage = response.usage

        content_blocks: list[TextBlock | ToolUseBlock] = []
        text = message.content or ""
        if text:
            content_blocks.append(TextBlock(type="text", text=text))

        tool_calls = getattr(message, "tool_calls", None) or []
        for tool_call in tool_calls:
            try:
                tool_input = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                tool_input = {}
            content_blocks.append(
                ToolUseBlock(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    input=tool_input,
                )
            )

        return OpenAIResponse(
            content=content_blocks,
            usage=Usage(
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
            ),
            stop_reason="tool_use" if tool_calls else "end_turn",
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
        return _OpenAIStream(self._client, model, max_tokens, system, messages)


class _OpenAIStream:
    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict],
    ):
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._system = system
        self._messages = messages
        self._final_message: OpenAIResponse | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def __aiter__(self):
        if self._final_message is None:
            self._final_message = await _OpenAIMessages(self._client).create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system,
                messages=self._messages,
            )
        text = self._final_message.content[0].text if self._final_message.content else ""
        if text:
            yield _DeltaEvent(text=text)

    async def get_final_message(self) -> OpenAIResponse:
        if self._final_message is None:
            self._final_message = await _OpenAIMessages(self._client).create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system,
                messages=self._messages,
            )
        return self._final_message


def _to_openai_tools(tools: list[dict]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for tool in tools
    ]


def _to_openai_messages(system: str, messages: list[dict]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                if item_type == "text":
                    text_parts.append(item.get("text", ""))
                elif item_type == "tool_use":
                    tool_calls.append(
                        {
                            "id": item.get("id"),
                            "type": "function",
                            "function": {
                                "name": item.get("name", ""),
                                "arguments": json.dumps(item.get("input", {})),
                            },
                        }
                    )
                elif item_type == "tool_result":
                    if text_parts:
                        out.append({"role": role, "content": "\n".join(text_parts)})
                        text_parts = []
                    out.append(
                        {
                            "role": "tool",
                            "tool_call_id": item.get("tool_use_id", ""),
                            "content": item.get("content", ""),
                        }
                    )
            if tool_calls:
                out.append(
                    {
                        "role": "assistant",
                        "content": "\n".join(text_parts) if text_parts else None,
                        "tool_calls": tool_calls,
                    }
                )
            elif text_parts:
                out.append({"role": role, "content": "\n".join(text_parts)})
            continue

        out.append({"role": role, "content": str(content)})

    return out
