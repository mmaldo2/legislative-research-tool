"""result_subtype must persist through build_record into the JSONL.

This is the field the lift analysis uses to EXCLUDE non-success (budget/turn-truncated) rollouts
post-hoc; it lived only in memory before, so a truncation was indistinguishable from a wrong answer
in the trace. Hermetic (no DB).
"""

from lab.graders import grade
from lab.harness import Instance
from lab.trace import RunContext, build_record


class _AgentSolver:
    name = "agent"
    kind = "agent"
    policy = {"name": "agent", "surface": "web", "model": "claude-haiku-4-5"}


def _inst():
    return Instance(
        instance_id="t:42:1",
        template_id="family1.vote_lookup",
        tier="C",
        params={},
        prompt="p",
        gold="yea",
        grader="exact",
        is_refusal=False,
    )


def _ctx():
    return RunContext(grading_contract_hash="gch", content_hash="ch", dataset_fingerprint={})


def test_result_subtype_persists_from_extras():
    v = grade("exact", "yea", "yea", is_refusal=False)
    rec = build_record(
        _inst(), _AgentSolver(), "yea", v, _ctx(), seed=42,
        extras={"result_subtype": "error_max_turns"},
    )
    assert rec.result_subtype == "error_max_turns"


def test_result_subtype_defaults_none_for_deterministic_path():
    v = grade("exact", "yea", "yea", is_refusal=False)
    rec = build_record(_inst(), _AgentSolver(), "yea", v, _ctx(), seed=42, extras=None)
    assert rec.result_subtype is None
