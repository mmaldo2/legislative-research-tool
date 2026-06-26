"""Option W (Agent SDK backend) — mocked, no live SDK/API call.

The fake `query()` AWAITS the REAL in-process @tool handlers (so observation/submit capture is
exercised, not bypassed), and captures the `ClaudeAgentOptions` so the integrity lockdown,
tool-doc parity, key-pop, and gold-leak guard are all asserted. SYNC def (the solver spins its own
asyncio.Runner).
"""

import json
import os
from unittest.mock import AsyncMock, Mock

from lab import solvers
from lab.harness import Instance


def _defection_inst() -> Instance:
    return Instance(
        instance_id="family1.party_defection:42:e1:R",
        template_id="family1.party_defection",
        tier="C",
        params={"vote_event_id": "e1", "party": "R"},
        prompt="On roll call e1, how many R voted against their party's majority?",
        gold=5,
        grader="exact_int",
        is_refusal=False,
    )


def _fake_exec(tool_name, args, db, harness):
    if tool_name == "submit_answer":
        return json.dumps({"status": "recorded"})
    return json.dumps({"vote_event_id": "e1", "records": [{"person_id": "p1", "party": "R"}]})


class _FakeSession:
    async def __aenter__(self):
        return Mock()

    async def __aexit__(self, *a):
        return False


def test_sdk_backend_drives_tools_maps_and_locks_down(monkeypatch):
    captured: dict = {}
    sdk_tools: dict = {}

    def fake_create_server(name, version="1.0.0", tools=None):
        for t in tools or []:
            sdk_tools[t.name] = t
        return {"server": name}

    async def fake_query(*, prompt, options):
        captured["prompt"] = prompt
        captured["options"] = options
        captured["key_during"] = os.environ.get("ANTHROPIC_API_KEY", "<absent>")
        # drive the REAL @tool handlers -> populate observations + submit_box
        await sdk_tools["get_vote_event"].handler({"vote_event_id": "e1"})
        await sdk_tools["submit_answer"].handler({"count": 5})
        if False:  # an async generator that yields nothing (no messages to iterate)
            yield

    monkeypatch.setattr("claude_agent_sdk.create_sdk_mcp_server", fake_create_server)
    monkeypatch.setattr("claude_agent_sdk.query", fake_query)
    monkeypatch.setattr("lab.solvers.lab_execute_tool", AsyncMock(side_effect=_fake_exec))
    monkeypatch.setattr("src.database.async_session_factory", lambda: _FakeSession())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-be-popped")

    solver = solvers.AgentSolver(backend="agent-sdk")
    inst = _defection_inst()
    ans = solver.solve(inst)
    solver.close()

    # mapping: count -> coerced int
    assert ans == 5
    # subscription-only: key popped DURING the query, restored after
    assert captured["key_during"] == "<absent>"
    assert os.environ.get("ANTHROPIC_API_KEY") == "should-be-popped"
    # capture wiring (real @tools ran): bare-name observations, both tools, submit captured
    traj = solver.trace_extras["trajectory"]
    assert [o["tool"] for o in traj] == ["get_vote_event", "submit_answer"]
    assert solver.history[-1]["retrieved"] is True  # bare name != submit_answer
    # integrity lockdown on the options
    opts = captured["options"]
    assert opts.allowed_tools == ["mcp__lab__get_vote_event", "mcp__lab__submit_answer"]
    assert opts.disallowed_tools == solvers._DISALLOWED_BUILTINS
    assert opts.setting_sources == []
    assert opts.permission_mode == "bypassPermissions"
    assert opts.model == solver.model and opts.system_prompt == solver.system_prompt
    # tool-doc parity: the SDK get_vote_event @tool == the product RESEARCH_TOOLS entry
    from src.llm.tools import RESEARCH_TOOLS

    gve = next(t for t in RESEARCH_TOOLS if t["name"] == "get_vote_event")
    assert sdk_tools["get_vote_event"].description == gve["description"]
    assert sdk_tools["get_vote_event"].input_schema == gve["input_schema"]
    # no gold leak: the agent saw inst.prompt only, never the gold value
    assert captured["prompt"] == inst.prompt
    assert str(inst.gold) not in captured["prompt"]


def test_sdk_backend_policy_records_backend():
    solver = solvers.AgentSolver(backend="agent-sdk")
    assert solver.policy["backend"] == "agent-sdk"
    assert solver.kind == "agent"
