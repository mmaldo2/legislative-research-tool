"""Frozen-contract tests for lab/scoring.py — the six worked Verdict->score examples,
the subscore-type guard (floats, never bools — the training-data-poisoning bug), the
empty-present guard, and the Verdict invariant."""

import pytest

from lab.scoring import Subscores, Verdict, score_verdict


def _subs(
    decision: float | None,
    answer: float | None,
    grounded: float | None,
    fmt: float,
) -> Subscores:
    return {
        "decision_correct": decision,
        "answer_correct": answer,
        "grounded": grounded,
        "format_valid": fmt,
    }


class TestWorkedExamples:
    """The six frozen rows from the plan (1a). Each is (subscores, is_refusal) -> score."""

    def test_correct_answer(self):
        assert score_verdict(_subs(1.0, 1.0, None, 1.0), is_refusal=False) == 1.0

    def test_wrong_but_attempted(self):
        # attempted (decision 1) but wrong (answer 0) -> partial credit 0.5, not a pass
        assert score_verdict(_subs(1.0, 0.0, None, 1.0), is_refusal=False) == 0.5

    def test_over_refusal(self):
        # answerable item, but refused -> decision 0, answer N/A -> 0.0
        assert score_verdict(_subs(0.0, None, None, 1.0), is_refusal=False) == 0.0

    def test_correct_refusal(self):
        # the "not in the data" case answered correctly -> 1.0
        assert score_verdict(_subs(1.0, None, None, 1.0), is_refusal=True) == 1.0

    def test_fabrication_hard_floor(self):
        # refusal item, but it fabricated an answer -> cardinal sin -> 0.0
        assert score_verdict(_subs(0.0, None, None, 1.0), is_refusal=True) == 0.0

    def test_malformed_output_gate(self):
        # format gate fires before anything else
        assert score_verdict(_subs(None, None, None, 0.0), is_refusal=False) == 0.0


class TestScoreType:
    def test_score_is_float(self):
        score = score_verdict(_subs(1.0, 1.0, None, 1.0), is_refusal=False)
        assert isinstance(score, float)

    def test_subscores_are_float_or_none_never_bool(self):
        # The training-data-poisoning guard: reward fields must be float|None, never bool.
        # (bool is a subclass of int, NOT of float, so isinstance(v, float) already rejects it;
        # we assert explicitly to document the contract.)
        for case in [_subs(1.0, 1.0, None, 1.0), _subs(0.0, None, None, 1.0)]:
            for key, value in case.items():
                assert value is None or (
                    isinstance(value, float) and not isinstance(value, bool)
                ), f"{key}={value!r} ({type(value).__name__}) is not float|None"


class TestEmptyPresentGuard:
    def test_all_non_gate_subscores_none_raises(self):
        # format_valid==1.0 but every other subscore None should be impossible; guarded loudly.
        with pytest.raises(AssertionError):
            score_verdict(_subs(None, None, None, 1.0), is_refusal=False)


class TestVerdictInvariant:
    def test_valid_pass(self):
        Verdict(passed=True, score=1.0, feedback="ok", subscores=_subs(1.0, 1.0, None, 1.0))

    def test_valid_fail(self):
        Verdict(passed=False, score=0.5, feedback="wrong", subscores=_subs(1.0, 0.0, None, 1.0))

    def test_passed_must_match_perfect_score(self):
        with pytest.raises(AssertionError):
            Verdict(passed=True, score=0.5, feedback="x", subscores=_subs(1.0, 0.0, None, 1.0))

    def test_score_out_of_range_rejected(self):
        with pytest.raises(AssertionError):
            Verdict(passed=False, score=1.5, feedback="x", subscores=_subs(1.0, 1.0, None, 1.0))
