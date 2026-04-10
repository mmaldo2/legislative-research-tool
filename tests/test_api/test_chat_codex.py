import asyncio
from unittest.mock import patch

import pytest


class _FakeBridge:
    def __init__(self, cwd):
        self.cwd = cwd

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def run_prompt(self, prompt: str, cwd=None, timeout: float = 60.0):
        return ["hello", " world"], "hello world"


@pytest.mark.asyncio
async def test_run_codex_chat_once_returns_text_and_no_tool_calls():
    from src.api import chat as chat_module

    with patch.object(chat_module, "CodexLocalBridge", _FakeBridge):
        text, tool_calls = await chat_module._run_codex_chat_once("hi")

    assert text == "hello world"
    assert tool_calls == []


@pytest.mark.asyncio
async def test_stream_codex_chat_once_emits_token_and_done_events():
    from src.api import chat as chat_module

    with patch.object(chat_module, "CodexLocalBridge", _FakeBridge):
        events = [event async for event in chat_module._stream_codex_chat_once("hi")]

    assert events[0] == 'event: token\ndata: {"text": "hello"}\n\n'
    assert events[1] == 'event: token\ndata: {"text": " world"}\n\n'
    assert events[2] == 'event: done\ndata: {"text": "hello world", "tool_calls": []}\n\n'
