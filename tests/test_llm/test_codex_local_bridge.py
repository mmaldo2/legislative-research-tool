from src.llm.codex_local_bridge import CodexLocalBridge


def test_extracts_thread_id_from_thread_start_response():
    response = {
        "thread": {
            "id": "thread-123",
            "cwd": "C:\\repo",
        },
        "model": "gpt-5.4",
        "modelProvider": "openai",
    }

    thread = CodexLocalBridge._thread_from_response(response)

    assert thread.id == "thread-123"
    assert thread.cwd == "C:\\repo"
    assert thread.model == "gpt-5.4"
    assert thread.model_provider == "openai"


def test_collects_agent_message_deltas_until_thread_returns_idle():
    events = [
        {"method": "thread/status/changed", "params": {"status": {"type": "active"}}},
        {
            "method": "item/agentMessage/delta",
            "params": {"delta": "hello"},
        },
        {
            "method": "item/agentMessage/delta",
            "params": {"delta": " world"},
        },
        {"method": "thread/status/changed", "params": {"status": {"type": "idle"}}},
    ]

    deltas, final_text = CodexLocalBridge._collect_turn_output(events)

    assert deltas == ["hello", " world"]
    assert final_text == "hello world"
