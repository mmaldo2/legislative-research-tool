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


def _member_summary_inst() -> Instance:
    return Instance(
        instance_id="family1.member_summary:42:115:house:p1",
        template_id="family1.member_summary",
        tier="C",
        params={"person_id": "p1", "congress": "115", "chamber": "house"},
        prompt="Across the house roll-call votes of Congress 115, how did X vote (yea/nay/other)?",
        gold={"yea": 10, "nay": 5, "other": 2},
        grader="fields",
        is_refusal=False,
    )


def _fake_exec_window(tool_name, args, db, harness):
    if tool_name == "submit_answer":
        return json.dumps({"status": "recorded"})
    if tool_name == "find_people":
        return json.dumps({"people": [{"person_id": "p1", "name": "X"}], "count": 1})
    return json.dumps({"records": [{"vote_event_id": "e1", "option": "yea"}], "count": 1})


def test_sdk_backend_window_template_provisions_window_tools(monkeypatch):
    """P9 + the @tool factory: a window template gets ONLY its window tools (built via
    _make_sdk_product_tool), allowed_tools is the lockstep whitelist, and the multi-tool trajectory
    is captured."""
    captured: dict = {}
    sdk_tools: dict = {}

    def fake_create_server(name, version="1.0.0", tools=None):
        for t in tools or []:
            sdk_tools[t.name] = t
        return {"server": name}

    async def fake_query(*, prompt, options):
        captured["options"] = options
        # drive the REAL factory-built @tools for the member-summary subset
        await sdk_tools["find_people"].handler({"name": "X", "congress": "115", "chamber": "house"})
        await sdk_tools["get_member_voting_record"].handler(
            {"person_id": "p1", "congress": "115", "chamber": "house"}
        )
        await sdk_tools["submit_answer"].handler({"yea": 10, "nay": 5, "other": 2})
        if False:
            yield

    monkeypatch.setattr("claude_agent_sdk.create_sdk_mcp_server", fake_create_server)
    monkeypatch.setattr("claude_agent_sdk.query", fake_query)
    monkeypatch.setattr("lab.solvers.lab_execute_tool", AsyncMock(side_effect=_fake_exec_window))
    monkeypatch.setattr("src.database.async_session_factory", lambda: _FakeSession())

    solver = solvers.AgentSolver(backend="agent-sdk")
    ans = solver.solve(_member_summary_inst())
    solver.close()

    # the fields shape maps (all-int coercion)
    assert ans == {"yea": 10, "nay": 5, "other": 2}
    # exactly the member subset built (no get_vote_event), submit always present
    assert set(sdk_tools) == {"find_people", "get_member_voting_record", "submit_answer"}
    # P9 lockstep: allowed_tools == the mcp__lab__* whitelist for THIS subset + submit
    assert captured["options"].allowed_tools == [
        "mcp__lab__find_people",
        "mcp__lab__get_member_voting_record",
        "mcp__lab__submit_answer",
    ]
    # multi-tool trajectory captured with bare names, in order
    traj = solver.trace_extras["trajectory"]
    assert [o["tool"] for o in traj] == [
        "find_people",
        "get_member_voting_record",
        "submit_answer",
    ]
    assert solver.history[-1]["retrieved"] is True


def _vote_lookup_inst() -> Instance:
    return Instance(
        instance_id="family1.vote_lookup:42:e1:p1",
        template_id="family1.vote_lookup",
        tier="C",
        params={"person_id": "p1", "vote_event_id": "us-house-115-2017-0009"},
        prompt="How did Rep. X vote on roll call us-house-115-2017-0009 (the motion)?",
        gold="yea",
        grader="exact",
        is_refusal=False,
    )


def test_sdk_web_surface_websearch_only_locks_out_lab_and_folds_vocab(monkeypatch):
    """Tool-surface ablation, WEB arm: WebSearch + fetch_url + run_python + submit (no lab DATA
    @tool, no WebFetch/Bash builtin); the
    built-in WebSearch call + its result are captured from the stream; web's faithful vocabulary
    ('Aye') folds to the canonical option."""
    from claude_agent_sdk.types import (
        AssistantMessage,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )

    captured: dict = {}
    sdk_tools: dict = {}

    def fake_create_server(name, version="1.0.0", tools=None):
        for t in tools or []:
            sdk_tools[t.name] = t
        return {"server": name}

    async def fake_query(*, prompt, options):
        captured["options"] = options
        # a built-in WebSearch call + its result arrive on the stream (NOT via an @tool side-effect)
        web_call = ToolUseBlock(id="tu1", name="WebSearch", input={"query": "Rep X roll call 9"})
        yield AssistantMessage(content=[web_call], model="claude-haiku-4-5")
        yield UserMessage(
            content=[ToolResultBlock(tool_use_id="tu1", content="Rep X voted Aye.", is_error=False)]
        )
        # the model answers in Congress.gov's faithful vocabulary; the fold must canonicalize it
        await sdk_tools["submit_answer"].handler({"answer": "Aye"})

    monkeypatch.setattr("claude_agent_sdk.create_sdk_mcp_server", fake_create_server)
    monkeypatch.setattr("claude_agent_sdk.query", fake_query)
    monkeypatch.setattr("lab.solvers.lab_execute_tool", AsyncMock(side_effect=_fake_exec))

    solver = solvers.AgentSolver(backend="agent-sdk", surface="web")
    ans = solver.solve(_vote_lookup_inst())
    solver.close()

    # vocab fold: web's "Aye" -> canonical "yea"
    assert ans == "yea"
    # web @tools = the guarded fetch_url + run_python + submit (NO get_vote_event / lab DATA tool)
    assert set(sdk_tools) == {"fetch_url", "run_python", "submit_answer"}
    opts = captured["options"]
    # web allowed = WebSearch + guarded fetch_url + run_python + submit (NO built-in WebFetch)
    assert opts.allowed_tools == [
        "WebSearch",
        "mcp__lab__fetch_url",
        "mcp__lab__run_python",
        "mcp__lab__submit_answer",
    ]
    assert "WebFetch" not in opts.allowed_tools
    # disallowed: WebSearch removed (so web works); WebFetch + the rest STAY blocked
    assert "WebSearch" not in opts.disallowed_tools
    assert "WebFetch" in opts.disallowed_tools
    assert "Bash" in opts.disallowed_tools
    # the global was NOT mutated (ours cells after this must still block WebSearch)
    assert "WebSearch" in solvers._DISALLOWED_BUILTINS
    # the built-in WebSearch was captured from the stream WITH its result, not double-counted;
    # submit self-captured once
    traj = solver.trace_extras["trajectory"]
    assert [o["tool"] for o in traj] == ["WebSearch", "submit_answer"]
    web_obs = traj[0]
    assert web_obs["arguments"] == {"query": "Rep X roll call 9"}
    assert web_obs["result"] == "Rep X voted Aye."  # ToolResultBlock matched by id
    assert solver.history[-1]["retrieved"] is True  # a non-submit tool ran
    assert solver.policy["surface"] == "web"


def test_sdk_ours_surface_keeps_web_disallowed(monkeypatch):
    """The ours arm must PROVABLY block web — WebSearch + WebFetch stay in disallowed_tools."""
    captured: dict = {}
    sdk_tools: dict = {}

    def fake_create_server(name, version="1.0.0", tools=None):
        for t in tools or []:
            sdk_tools[t.name] = t
        return {"server": name}

    async def fake_query(*, prompt, options):
        captured["options"] = options
        await sdk_tools["get_vote_event"].handler({"vote_event_id": "e1"})
        await sdk_tools["submit_answer"].handler({"answer": "yea"})
        if False:
            yield

    monkeypatch.setattr("claude_agent_sdk.create_sdk_mcp_server", fake_create_server)
    monkeypatch.setattr("claude_agent_sdk.query", fake_query)
    monkeypatch.setattr("lab.solvers.lab_execute_tool", AsyncMock(side_effect=_fake_exec))
    monkeypatch.setattr("src.database.async_session_factory", lambda: _FakeSession())

    solver = solvers.AgentSolver(backend="agent-sdk", surface="ours")
    solver.solve(_vote_lookup_inst())
    solver.close()

    opts = captured["options"]
    assert "WebSearch" in opts.disallowed_tools and "WebFetch" in opts.disallowed_tools
    assert opts.allowed_tools == ["mcp__lab__get_vote_event", "mcp__lab__submit_answer"]
    assert solver.policy["surface"] == "ours"
