"""SWAPPABLE solvers used to validate the GRADERS without a live LLM (v1).

  - SqlOracleSolver: returns gold -> graders must PASS (they accept correct answers).
  - WrongBaselineSolver: returns a wrong answer -> graders must FAIL (catch hallucinations).
  - OverRefuseSolver: refuses everything -> answerable items FAIL (catches over-refusal).

The live chat/MCP agent (backend: claude-sdk) is the future drop-in replacement; it sets
kind="agent" and a richer policy. Each solver exposes `kind` + `policy` so the trace records
what produced a rollout (and synthetic fixture rows can be filtered out of any training set).
"""

from lab.graders import REFUSAL
from lab.harness import Instance
from src.ingestion.vote_parsers import OPTION_BUCKETS


class _DeterministicSolver:
    """Base for the non-LLM validation solvers: a fixed policy + a synthetic-row marker."""

    name: str
    kind = "deterministic"

    @property
    def policy(self) -> dict:
        return {"name": self.name}


class SqlOracleSolver(_DeterministicSolver):
    name = "oracle"

    def solve(self, inst: Instance):
        return inst.gold


class WrongBaselineSolver(_DeterministicSolver):
    """Provably wrong per instance, but always WELL-FORMED (so the wrong-baseline invariant is
    decision_correct==1 & answer_correct==0 & format_valid==1, never a format-fail):
      - refusal item:  fabricate a non-refusal option (didn't refuse -> wrong);
      - dict gold:     perturb the first non-bool int field by +1 (same keys -> shape valid);
      - set gold:      ADD a guaranteed-absent sentinel (never remove -> empty gold stays wrong);
      - bare int gold: +1 (a well-formed wrong int -> attempted-but-wrong, not a format-fail);
      - scalar option: a different valid option.
    """

    name = "wrong-baseline"

    def solve(self, inst: Instance):
        if inst.is_refusal:
            return OPTION_BUCKETS[0]  # fabricate instead of refusing -> wrong
        gold = inst.gold
        if isinstance(gold, dict):
            for key, val in gold.items():
                if isinstance(val, int) and not isinstance(val, bool):
                    return {**gold, key: val + 1}
            raise AssertionError(f"composite gold has no int field to perturb: {gold!r}")
        if isinstance(gold, set | list | tuple):
            return set(gold) | {"NX-wrong"}  # add a provably-absent id
        if isinstance(gold, int) and not isinstance(gold, bool):
            return gold + 1  # bare int (e.g. defection count) -> a different, well-formed int
        for opt in OPTION_BUCKETS:
            if opt != gold:
                return opt
        return REFUSAL  # unreachable for a valid option gold


class OverRefuseSolver(_DeterministicSolver):
    """Refuses every item — proves the exact grader catches over-refusal on answerable items."""

    name = "over-refuse"

    def solve(self, inst: Instance):
        return REFUSAL
