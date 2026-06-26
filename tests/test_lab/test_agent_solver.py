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
    assert solver.trace_extras["trajectory"]  # tool trajectory captured for the trace


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
