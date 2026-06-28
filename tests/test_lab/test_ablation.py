"""Ablation rate-math — the closed-match trust partition on SYNTHETIC subscores (no live calls).

The partition is the metric's whole point and the thing most likely to be subtly wrong: it must be
exhaustive + mutually exclusive over an answerable item, separate confident-wrong (hallucination)
from over-refusal from format-fail from operational error, and RAISE on a subscore state that
build_verdict cannot produce (so a future None-returning grader can never silently land in the
trust-fatal hallucination bucket).
"""

import pytest

from lab.ablation import (
    _aggregate_by_switcher,
    _delta,
    _partition_by_kind,
    classify,
)
from lab.harness import Instance


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


# --- the switcher/control SPLIT machinery (pass 2), on synthetic data — NO live calls ----------


def _inst(kind=None):
    params = {"x": 1} if kind is None else {"kind": kind, "switcher_name": f"Sen. {kind}"}
    return Instance(
        instance_id="i",
        template_id="t",
        tier="C",
        params=params,
        prompt="?",
        gold={"D"},
        grader="set_match",
        is_refusal=False,
    )


def _cell(model, surface, kind, *, halluc=0.0, correct=0.0, by_switcher=None):
    buckets = ("correct", "hallucination", "over_refusal", "format_fail", "errored")
    rates = dict.fromkeys(buckets, 0.0)
    rates["correct"], rates["hallucination"] = correct, halluc
    return {
        "model": model,
        "surface": surface,
        "kind": kind,
        "rates": rates,
        "by_switcher": by_switcher or {},
    }


class TestPartitionByKind:
    def test_splits_switcher_and_control(self):
        insts = [_inst("switcher"), _inst("control"), _inst("switcher")]
        by_kind = _partition_by_kind(insts)
        assert sorted(by_kind) == ["control", "switcher"]
        assert len(by_kind["switcher"]) == 2 and len(by_kind["control"]) == 1

    def test_no_kind_collapses_to_all(self):
        # vote_lookup (pass 1) has no kind -> a single "all" bucket, so pass 1 is unchanged.
        by_kind = _partition_by_kind([_inst(), _inst()])
        assert list(by_kind) == ["all"] and len(by_kind["all"]) == 2


class TestDelta:
    def test_switcher_delta_isolates_the_moat(self):
        # web hallucinates on switchers (0.6) while ours doesn't (0.0); control ties -> the headline
        # delta is read on the SWITCHER subset, never averaged with the control.
        runs = [
            _cell("haiku", "ours", "switcher", halluc=0.0),
            _cell("haiku", "web", "switcher", halluc=0.6),
            _cell("haiku", "ours", "control", halluc=0.0),
            _cell("haiku", "web", "control", halluc=0.0),
        ]
        assert _delta(runs, "haiku", "switcher", "hallucination") == pytest.approx(0.6)
        assert _delta(runs, "haiku", "control", "hallucination") == pytest.approx(0.0)

    def test_delta_averages_over_repeats(self):
        runs = [
            _cell("s", "ours", "switcher", correct=1.0),
            _cell("s", "web", "switcher", correct=0.4),
            _cell("s", "web", "switcher", correct=0.6),  # 2 web reps -> mean 0.5
        ]
        assert _delta(runs, "s", "switcher", "correct") == pytest.approx(-0.5)

    def test_none_when_an_arm_is_absent(self):
        runs = [_cell("s", "ours", "switcher", halluc=0.0)]  # no web cell
        assert _delta(runs, "s", "switcher", "hallucination") is None


class TestAggregateBySwitcher:
    def test_merges_bucket_counts_across_reps(self):
        cells = [
            _cell("s", "web", "switcher", by_switcher={"Amash": {"hallucination": 1}}),
            _cell(
                "s",
                "web",
                "switcher",
                by_switcher={"Amash": {"hallucination": 1, "correct": 1}, "Sinema": {"correct": 1}},
            ),
        ]
        agg = _aggregate_by_switcher(cells)
        assert agg["Amash"]["hallucination"] == 2 and agg["Amash"]["correct"] == 1
        assert agg["Sinema"]["correct"] == 1
