"""FROZEN code-graders for Family 1.

Anti-cheat discipline (carried from autoresearch's "do not modify prepare.py"):
never weaken a grader, loosen a tolerance, or simplify gold to inflate a pass rate.
If a task fails because the *task* is wrong, fix the task; if the *solver* is wrong,
fix the solver — never the grader.

The pure primitives (grade_exact, grade_refusal_correct) stay pure 0/1 predicates so they
cannot be "weakened" by presentation concerns. `build_verdict` composes them into a Verdict
(see lab/scoring.py), FLOAT-coercing every subscore — a boolean would poison the training
corpus and infer a BOOLEAN column on the DuckDB read-side.
"""

from typing import Any

from lab.scoring import Subscores, Verdict, score_verdict
from src.ingestion.vote_parsers import OPTION_BUCKETS

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


def _is_canonical(answer: Any) -> bool:
    """format_valid gate: a well-formed answer is the refusal sentinel or a canonical option."""
    return answer == REFUSAL or _norm(answer) in OPTION_BUCKETS


def build_verdict(grader: str, gold: Any, answer: Any, *, is_refusal: bool) -> Verdict:
    """Compose the pure primitives into a Verdict with FLOAT subscores + a grader-authored
    feedback string (the GEPA reflection fuel)."""
    if not _is_canonical(answer):
        subs: Subscores = {
            "decision_correct": None,
            "answer_correct": None,
            "grounded": None,
            "format_valid": 0.0,
        }
        score = score_verdict(subs, is_refusal=is_refusal)
        feedback = f"{grader}: answer={answer!r} is not a canonical token (option or refusal)"
        return Verdict(passed=(score == 1.0), score=score, feedback=feedback, subscores=subs)

    if is_refusal:
        decision = 1.0 if answer == REFUSAL else 0.0  # refusing is correct; fabricating is not
        answer_correct = None
    else:
        decision = 0.0 if answer == REFUSAL else 1.0  # refusing an answerable item = over-refusal
        answer_correct = float(GRADERS[grader](gold, answer)) if decision == 1.0 else None

    subs = {
        "decision_correct": decision,
        "answer_correct": answer_correct,
        "grounded": None,  # reserved for the agent slice + v2 groundedness grader
        "format_valid": 1.0,
    }
    score = score_verdict(subs, is_refusal=is_refusal)
    feedback = (
        f"{grader}: answer={answer!r} gold={gold!r} -> {'pass' if score == 1.0 else 'fail'} "
        f"(decision_correct={decision}, answer_correct={answer_correct})"
    )
    return Verdict(passed=(score == 1.0), score=score, feedback=feedback, subscores=subs)


def grade(grader: str, gold: Any, answer: Any, *, is_refusal: bool) -> Verdict:
    return build_verdict(grader, gold, answer, is_refusal=is_refusal)
