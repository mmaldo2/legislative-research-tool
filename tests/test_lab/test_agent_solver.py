"""A3b AgentSolver answer-mapping tests.

SYNC defs on purpose: `asyncio_mode = "auto"` runs `async def` tests inside a live loop, and the
solver's own `asyncio.Runner` would then raise. `run_agentic_chat` is mocked and the client is
injected (`Mock()`), so NO live API call is made and no auth is needed.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

from lab.graders import REFUSAL, grade
from lab.harness import Instance
from lab.solvers import NO_ANSWER, AgentSolver

_RAC = "src.services.chat_service.run_agentic_chat"


def _inst(prompt="How did Adam Smith vote on roll call e1?", *, refusal=False) -> Instance:
    if refusal:
        return Instance(
            instance_id="family1.vote_lookup:42:refusal:e1:NX-1",
            template_id="family1.vote_lookup",
            tier="C",
            params={"person_id": "NX-1", "vote_event_id": "e1"},
            prompt=prompt,
            gold=REFUSAL,
            grader="refusal_correct",
            is_refusal=True,
            refusal_reason="person_not_in_data",
        )
    return Instance(
        instance_id="family1.vote_lookup:42:e1:p1",
        template_id="family1.vote_lookup",
        tier="C",
        params={"person_id": "p1", "vote_event_id": "e1"},
        prompt=prompt,
        gold="yea",
        grader="exact",
        is_refusal=False,
    )


def _run(tool_calls, final_text="done", inst=None):
    inst = inst or _inst()
    solver = AgentSolver(client=Mock())
    with patch(_RAC, new=AsyncMock(return_value=(final_text, tool_calls))) as mock_rac:
        answer = solver.solve(inst)
    solver.close()
    return answer, solver, mock_rac


def test_maps_option_passthrough():
    ans, solver, _ = _run(
        [{"tool_name": "submit_answer", "arguments": {"answer": "yea"}}], final_text="X voted yea."
    )
    assert ans == "yea"
    assert solver.trace_extras["raw"] == "X voted yea."
    assert solver.trace_extras["latency_ms"] >= 0
    # trajectory is the observation list (empty here — the mock short-circuits the tool loop)
    assert isinstance(solver.trace_extras["trajectory"], list)


def test_maps_refusal_flag_authoritative():
    ans, *_ = _run([{"tool_name": "submit_answer", "arguments": {"refused": True}}])
    assert ans == REFUSAL


def test_never_submitted_is_fallback():
    ans, *_ = _run([{"tool_name": "get_vote_event", "arguments": {"vote_event_id": "e1"}}])
    assert ans == NO_ANSWER


def test_inconsistent_both_is_fallback():
    ans, *_ = _run(
        [{"tool_name": "submit_answer", "arguments": {"answer": "yea", "refused": True}}]
    )
    assert ans == NO_ANSWER


def test_no_submit_on_refusal_instance_earns_no_credit():
    """A non-finishing agent must FAIL a refusal instance — never free refusal credit."""
    inst = _inst(refusal=True)
    ans, *_ = _run([], inst=inst)
    assert ans == NO_ANSWER
    verdict = grade(inst.grader, inst.gold, ans, is_refusal=inst.is_refusal)
    assert not verdict.passed


def test_prompt_only_no_gold_leak_and_constrained_tools():
    """The agent sees inst.prompt ONLY — never inst.params (gold person_id) or inst.gold."""
    inst = _inst()
    solver = AgentSolver(client=Mock())
    with patch(_RAC, new=AsyncMock(return_value=("done", []))) as mock_rac:
        solver.solve(inst)
    solver.close()
    kwargs = mock_rac.await_args.kwargs
    sent = json.dumps(kwargs["messages"])
    assert inst.params["person_id"] not in sent
    assert inst.gold not in sent
    assert {t["name"] for t in kwargs["tools"]} == {"get_vote_event", "submit_answer"}
    assert kwargs["model"] == "claude-sonnet-4-6"


def test_api_error_is_recorded_not_raised():
    """A live API/network failure FAILS the instance (NO_ANSWER) and is recorded — never crashes."""
    solver = AgentSolver(client=Mock())
    with patch(_RAC, new=AsyncMock(side_effect=RuntimeError("429 boom"))):
        ans = solver.solve(_inst())  # must NOT raise
    solver.close()
    assert ans == NO_ANSWER
    assert "429 boom" in solver.trace_extras["raw"]


def test_observations_captured_in_trajectory():
    """The trajectory records full tool OBSERVATIONS (results), not just char-count summaries."""

    async def fake_rac(*, execute_tool_fn, **kwargs):
        await execute_tool_fn("submit_answer", {"answer": "yea"}, None, None)
        return ("done", [{"tool_name": "submit_answer", "arguments": {"answer": "yea"}}])

    solver = AgentSolver(client=Mock())
    with patch(_RAC, new=fake_rac):
        ans = solver.solve(_inst())
    solver.close()
    assert ans == "yea"
    traj = solver.trace_extras["trajectory"]
    assert traj and traj[0]["tool"] == "submit_answer" and "result" in traj[0]


def test_error_message_redacts_oauth_token():
    """A secret that surfaces in a third-party error string must NOT reach the persisted trace."""
    leak = "auth failed: sk-ant-oat01-SUPERSECRETVALUE blah"
    solver = AgentSolver(client=Mock())
    with patch(_RAC, new=AsyncMock(side_effect=RuntimeError(leak))):
        solver.solve(_inst())
    solver.close()
    raw = solver.trace_extras["raw"]
    assert "sk-ant-oat01-SUPERSECRETVALUE" not in raw
    assert "<redacted>" in raw


def test_runner_reused_across_instances():
    """The persistent Runner must be reused across N instances (regression guard: a revert to
    asyncio.run() per call leaves _runner=None and would fail here)."""

    async def fake_rac(**kwargs):
        return ("done", [{"tool_name": "submit_answer", "arguments": {"answer": "yea"}}])

    solver = AgentSolver(client=Mock())
    with patch(_RAC, new=fake_rac):
        assert solver.solve(_inst()) == "yea"
        first = solver._runner
        assert solver.solve(_inst()) == "yea"  # 2nd instance on the SAME runner must not raise
        assert solver._runner is first and first is not None
    assert len(solver.history) == 2  # the diagnostic trail records both
    solver.close()
