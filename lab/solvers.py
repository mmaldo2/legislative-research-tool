"""SWAPPABLE solvers used to validate the GRADERS without a live LLM (v1).

  - SqlOracleSolver: returns gold -> graders must PASS (they accept correct answers).
  - WrongBaselineSolver: returns a wrong answer -> graders must FAIL (catch hallucinations).
  - OverRefuseSolver: refuses everything -> answerable items FAIL (catches over-refusal).

The live chat/MCP agent (backend: claude-sdk) is the future drop-in replacement.
"""

from lab.graders import REFUSAL
from lab.harness import Instance
from src.ingestion.vote_parsers import OPTION_BUCKETS


class SqlOracleSolver:
    name = "oracle"

    def solve(self, inst: Instance):
        return inst.gold


class WrongBaselineSolver:
    """Provably wrong per instance: a different valid option for answerable items,
    and a fabricated (non-refusal) answer for refusal items."""

    name = "wrong-baseline"

    def solve(self, inst: Instance):
        if inst.is_refusal:
            return OPTION_BUCKETS[0]  # fabricate instead of refusing -> wrong
        for opt in OPTION_BUCKETS:
            if opt != inst.gold:
                return opt
        return REFUSAL  # unreachable for a valid option gold


class OverRefuseSolver:
    """Refuses every item — proves the exact grader catches over-refusal on answerable items."""

    name = "over-refuse"

    def solve(self, inst: Instance):
        return REFUSAL
