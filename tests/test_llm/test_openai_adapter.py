import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.llm.openai_adapter import OpenAICompatClient, _to_openai_messages, _to_openai_tools


class DummyUsage:
    def __init__(self, prompt_tokens=11, completion_tokens=7):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class DummyToolCall:
    def __init__(self, id: str, name: str, arguments: dict):
        self.id = id
        self.function = SimpleNamespace(name=name, arguments=json.dumps(arguments))


@pytest.mark.asyncio
async def test_create_returns_tool_use_blocks_when_openai_requests_tools():
    client = OpenAICompatClient(api_key="test-key")
    create_mock = AsyncMock()
    create_mock.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[DummyToolCall("call_1", "search_bills", {"query": "privacy"})],
                )
            )
        ],
        usage=DummyUsage(),
    )
    client._client.chat.completions.create = create_mock

    response = await client.messages.create(
        model="gpt-test",
        max_tokens=100,
        system="system",
        messages=[{"role": "user", "content": "find privacy bills"}],
        tools=[
            {
                "name": "search_bills",
                "description": "Search bills",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
            }
        ],
    )

    assert response.stop_reason == "tool_use"
    tool_blocks = [block for block in response.content if getattr(block, "type", None) == "tool_use"]
    assert len(tool_blocks) == 1
    assert tool_blocks[0].name == "search_bills"
    assert tool_blocks[0].input == {"query": "privacy"}


def test_to_openai_messages_converts_tool_use_and_tool_result_history():
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me search."},
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "search_bills",
                    "input": {"query": "privacy"},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": '{"total": 1}',
                }
            ],
        },
    ]

    converted = _to_openai_messages("system prompt", messages)
    assert converted[0] == {"role": "system", "content": "system prompt"}
    assert converted[1]["role"] == "assistant"
    assert converted[1]["tool_calls"][0]["id"] == "call_1"
    assert converted[2] == {"role": "tool", "tool_call_id": "call_1", "content": '{"total": 1}'}


def test_to_openai_tools_projects_anthropic_shape_to_openai_functions():
    tools = [
        {
            "name": "search_bills",
            "description": "Search legislation",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        }
    ]

    converted = _to_openai_tools(tools)
    assert converted == [
        {
            "type": "function",
            "function": {
                "name": "search_bills",
                "description": "Search legislation",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        }
    ]
