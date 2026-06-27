"""Ablation rate-math — the closed-match trust partition on SYNTHETIC subscores (no live calls).

The partition is the metric's whole point and the thing most likely to be subtly wrong: it must be
exhaustive + mutually exclusive over an answerable item, separate confident-wrong (hallucination)
from over-refusal from format-fail from operational error, and RAISE on a subscore state that
build_verdict cannot produce (so a future None-returning grader can never silently land in the
trust-fatal hallucination bucket).
"""

import pytest

from lab.ablation import classify


def _subs(fv, dc, ac):
    return {"format_valid": fv, "decision_correct": dc, "answer_correct": ac, "grounded": None}


def test_correct():
    assert classify(_subs(1.0, 1.0, 1.0), errored=False) == "correct"


def test_hallucination_is_confident_wrong():
    # attempted (dc=1) but wrong (ac=0) — the trust-fatal case, NOT format_fail
    assert classify(_subs(1.0, 1.0, 0.0), errored=False) == "hallucination"


def test_over_refusal():
    # refused an answerable item (dc=0); ac is None on this path — must key on dc, not touch ac
    assert classify(_subs(1.0, 0.0, None), errored=False) == "over_refusal"


def test_format_fail():
    # never-submitted / non-canonical: fv=0 forces the other subscores to None
    assert classify(_subs(0.0, None, None), errored=False) == "format_fail"


def test_errored_takes_precedence():
    # an SDK crash / budget-or-turn truncation is operational, NOT a trust failure — even though the
    # underlying answer format-failed (fv=0), it must bucket as `errored`, not `format_fail`.
    assert classify(_subs(0.0, None, None), errored=True) == "errored"
    assert classify(_subs(1.0, 1.0, 1.0), errored=True) == "errored"


def test_illegal_dc_none_with_fv1_raises():
    # build_verdict guarantees fv1 ⇒ dc present; a None here = a contract drift → loud failure,
    # never a silent mis-bucket.
    with pytest.raises(AssertionError):
        classify(_subs(1.0, None, None), errored=False)


def test_illegal_ac_none_with_dc1_raises():
    # the one the catch-all `else: hallucination` would silently absorb into the trust-fatal bucket.
    with pytest.raises(AssertionError):
        classify(_subs(1.0, 1.0, None), errored=False)


def test_partition_is_exhaustive_and_exclusive():
    # every legal answerable subscore state maps to exactly one bucket; the set covers all 5.
    legal = [
        (_subs(1.0, 1.0, 1.0), "correct"),
        (_subs(1.0, 1.0, 0.0), "hallucination"),
        (_subs(1.0, 0.0, None), "over_refusal"),
        (_subs(0.0, None, None), "format_fail"),
    ]
    seen = {classify(s, errored=False) for s, _ in legal}
    seen.add(classify(_subs(1.0, 1.0, 1.0), errored=True))  # errored
    assert seen == {"correct", "hallucination", "over_refusal", "format_fail", "errored"}
    for s, want in legal:
        assert classify(s, errored=False) == want
