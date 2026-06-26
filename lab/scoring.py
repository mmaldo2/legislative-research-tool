"""FROZEN scoring contract: the Verdict shape + score formula the whole flywheel keys on.

A grade is no longer a bool. A `Verdict` carries a scalar `score` (the RL/GEPA reward),
a `passed` gate (fully-correct only), grader-authored `feedback` (GEPA reflection fuel),
and decomposed `subscores`. This shape is frozen because live-agent rollouts are
perishable point-in-time artifacts — we cannot re-run them, so the record that holds them
must be right the first time.

Subscores are FLOATS (or None), never bools: they serialize into the training corpus, and
a boolean would both poison the reward arithmetic and infer a BOOLEAN column on the
DuckDB read-side. `build_verdict()` (see lab/graders.py, sub-phase 1b) is responsible for
float-coercing the pure 0/1 grader primitives before they land here.

Subscores (each float in [0,1], or None=N/A):
  - format_valid     GATE. 1.0 iff the answer is a canonical token (option or REFUSAL).
                     0.0 => every other subscore is None and score is 0.0 (garbage in).
  - decision_correct Every instance. Answerable: 1.0 if it attempted (answer != REFUSAL),
                     else 0.0 (over-refusal). Refusal: 1.0 if it refused, else 0.0 (fabrication).
  - answer_correct   Answerable AND attempted: the grader float (exact -> {0.0, 1.0}). Else None.
  - grounded         None for all of v1 (reserved for the agent slice + v2 groundedness).
                     Activating it is a trace_schema_version bump that re-baselines invariants;
                     v1 score/passed are NOT comparable across that boundary.
"""

from dataclasses import dataclass
from statistics import mean
from typing import TypedDict


class Subscores(TypedDict):
    decision_correct: float | None
    answer_correct: float | None
    grounded: float | None
    format_valid: float  # gate; always present (0.0 or 1.0)


@dataclass(frozen=True)
class Verdict:
    passed: bool
    score: float  # [0, 1]
    feedback: str  # grader-authored NL "why" (GEPA reflection fuel)
    subscores: Subscores

    def __post_init__(self) -> None:
        assert 0.0 <= self.score <= 1.0, f"score out of range: {self.score}"
        # `passed` is fully-correct only — partial credit (e.g. wrong-but-attempted) is not a pass.
        assert self.passed == (self.score == 1.0), f"passed={self.passed} but score={self.score}"


def score_verdict(s: Subscores, *, is_refusal: bool) -> float:
    """The FROZEN score formula. Equal weights over present (non-null) non-gate subscores,
    with two hard gates. `is_refusal` is a property of the instance, not a subscore, so it is
    a required keyword argument (it cannot be derived from `s` alone)."""
    if s["format_valid"] == 0.0:
        return 0.0  # gate: unparseable output is a total failure
    if is_refusal and s["decision_correct"] == 0.0:
        return 0.0  # fabrication on a refusal item is the cardinal sin — hard floor
    present = [v for k, v in s.items() if k != "format_valid" and v is not None]
    assert present, "format_valid==1.0 must imply decision_correct is present"
    return float(mean(present))
