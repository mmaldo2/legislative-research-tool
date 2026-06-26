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


def grade_exact_int(gold: Any, answer: Any) -> bool:
    """Exact integer match for counts/margins. NO tolerance. `bool` is explicitly excluded
    (True == 1 in Python — a bool answer must never satisfy an int field)."""
    return isinstance(answer, int) and not isinstance(answer, bool) and gold == answer


def _match_field(gold: Any, answer: Any) -> bool:
    """Per-field primitive for composite (dict) answers. Dispatches on the GOLD value's type
    (gold is trusted SQL output): int->exact_int, str->exact (case-normalized), bool->identity
    (defensive; no bool fields today), else plain normalized equality (covers None/other)."""
    if isinstance(gold, bool):
        return gold is answer
    if isinstance(gold, int):
        return grade_exact_int(gold, answer)
    if isinstance(gold, str):
        return grade_exact(gold, answer)
    return _norm(gold) == _norm(answer)


def grade_fields(gold: Any, answer: Any) -> bool:
    """Composite answer: field-wise AND. Keys must match exactly; every field must match its
    per-type primitive. Empty gold is rejected (an empty {} must never grade as a vacuous pass)."""
    if not isinstance(answer, dict) or not isinstance(gold, dict) or not gold:
        return False
    if answer.keys() != gold.keys():
        return False
    return all(_match_field(gold[k], answer[k]) for k in gold)


def grade_set_match(gold: Any, answer: Any) -> bool:
    """Order-independent set equality (e.g. a set of person_ids or event_ids). Symmetric
    normalization on both sides; TypeError-safe (unhashable answer -> fail, not crash)."""
    try:
        return set(map(_norm, gold)) == set(map(_norm, answer))
    except TypeError:
        return False


GRADERS = {
    "exact": grade_exact,
    "refusal_correct": grade_refusal_correct,
    "exact_int": grade_exact_int,
    "fields": grade_fields,
    "set_match": grade_set_match,
}


def _is_canonical(answer: Any) -> bool:
    """format_valid gate for SCALAR option graders: the refusal sentinel or a canonical option."""
    return answer == REFUSAL or _norm(answer) in OPTION_BUCKETS


def _format_valid(grader: str, answer: Any) -> bool:
    """SHAPE-ONLY format gate. Validates the *shape* of the answer, NOT whether it matches gold
    (key-set / element correctness is the grader's job — folding it in here would mis-score a
    wrong-keyed dict as 'malformed' (0.0) instead of 'attempted-but-wrong' (0.5), collapsing the
    over-refusal vs wrong-answer distinction the subscores exist for). REFUSAL is well-formed for
    every grader. The scalar exact/refusal_correct path is unchanged (still via _is_canonical)."""
    if answer == REFUSAL:
        return True
    if grader in ("exact", "refusal_correct"):
        return _is_canonical(answer)
    if grader == "exact_int":
        return isinstance(answer, int) and not isinstance(answer, bool)
    if grader == "fields":
        return isinstance(answer, dict)
    if grader == "set_match":
        return isinstance(answer, set | list | tuple)
    return False


def build_verdict(grader: str, gold: Any, answer: Any, *, is_refusal: bool) -> Verdict:
    """Compose the pure primitives into a Verdict with FLOAT subscores + a grader-authored
    feedback string (the GEPA reflection fuel)."""
    if not _format_valid(grader, answer):
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
