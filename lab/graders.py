"""FROZEN code-graders for Family 1.

Anti-cheat discipline (carried from autoresearch's "do not modify prepare.py"):
never weaken a grader, loosen a tolerance, or simplify gold to inflate a pass rate.
If a task fails because the *task* is wrong, fix the task; if the *solver* is wrong,
fix the solver — never the grader.
"""

from typing import Any

# Sentinel for the required "not in the data" answer (Condorcet hard rule: refusal
# is a valid, graded outcome). Distinct from every canonical vote option.
REFUSAL = "not_in_the_data"


def _norm(value: Any) -> Any:
    """Symmetric normalization applied to BOTH gold and answer."""
    return value.strip().lower() if isinstance(value, str) else value


def grade_exact(gold: Any, answer: Any) -> bool:
    """Scalar/option exact match. An over-refusal (answer == REFUSAL on an
    answerable item) fails here, which is how over-refusal is caught."""
    return _norm(gold) == _norm(answer)


def grade_refusal_correct(gold: Any, answer: Any) -> bool:
    """For refusal instances (gold == REFUSAL): pass iff the solver refused.
    A solver that fabricates any answer instead of refusing fails."""
    return answer == REFUSAL


GRADERS = {
    "exact": grade_exact,
    "refusal_correct": grade_refusal_correct,
}


def grade(grader: str, gold: Any, answer: Any) -> bool:
    return GRADERS[grader](gold, answer)
