"""Composite (dict) + set grader unit tests — the Phase-2 additive contract extension.

The existing scalar primitives (test_graders.py) are unchanged and must still pass; these cover
the new `exact_int` / `fields` / `set_match` modes and the SHAPE-ONLY format gate.
"""

from lab.graders import (
    _match_field,
    grade,
    grade_exact_int,
    grade_fields,
    grade_set_match,
)


class TestExactInt:
    def test_match(self):
        assert grade_exact_int(5, 5)

    def test_mismatch(self):
        assert not grade_exact_int(5, 6)

    def test_bool_excluded(self):
        # True == 1 / False == 0 in Python; a bool must NEVER satisfy an int field.
        assert not grade_exact_int(1, True)
        assert not grade_exact_int(0, False)

    def test_non_int_answer(self):
        assert not grade_exact_int(5, "5")

    def test_negative_margin(self):
        assert grade_exact_int(-8, -8)


class TestMatchField:
    def test_int(self):
        assert _match_field(3, 3)
        assert not _match_field(3, 4)

    def test_str_case_and_whitespace_normalized(self):
        assert _match_field("Passed", " passed ")

    def test_none_arm(self):
        assert _match_field(None, None)
        assert not _match_field(None, "x")

    def test_bool_field_identity(self):
        assert _match_field(True, True)
        assert not _match_field(True, 1)  # bool field must not match an int


class TestFields:
    def test_all_match(self):
        assert grade_fields({"yea": 2, "nay": 1}, {"yea": 2, "nay": 1})

    def test_one_field_wrong(self):
        assert not grade_fields({"yea": 2, "nay": 1}, {"yea": 2, "nay": 9})

    def test_key_mismatch_either_direction(self):
        assert not grade_fields({"yea": 2, "nay": 1}, {"yea": 2})
        assert not grade_fields({"yea": 2}, {"yea": 2, "extra": 0})

    def test_empty_gold_is_never_a_vacuous_pass(self):
        assert not grade_fields({}, {})

    def test_non_dict_answer(self):
        assert not grade_fields({"yea": 2}, "yea")

    def test_mixed_int_str_fields(self):
        gold = {"yea": 218, "nay": 210, "margin": 8, "result": "Passed"}
        assert grade_fields(gold, dict(gold))
        assert not grade_fields(gold, {**gold, "result": "Failed"})


class TestSetMatch:
    def test_equal_order_independent(self):
        assert grade_set_match({"p1", "p2"}, ["p2", "p1"])

    def test_unequal(self):
        assert not grade_set_match({"p1"}, {"p1", "p2"})

    def test_empty_sets_equal(self):
        assert grade_set_match(set(), [])

    def test_case_normalized(self):
        assert grade_set_match({"P1"}, {"p1"})

    def test_typeerror_safe(self):
        assert not grade_set_match({"p1"}, 5)  # non-iterable answer -> False, not a crash


class TestShapeOnlyGate:
    """The live-agent-facing semantic: a wrong-KEYED dict is attempted-but-wrong (0.5), NOT
    malformed (0.0). The format gate validates shape only; grade_fields owns key correctness."""

    def test_wrong_keyed_dict_is_attempted_partial(self):
        v = grade("fields", {"yea": 2, "nay": 1}, {"yea": 2}, is_refusal=False)
        assert v.subscores["format_valid"] == 1.0  # dict shape is valid...
        assert v.subscores["decision_correct"] == 1.0  # ...it attempted (didn't refuse)...
        assert v.subscores["answer_correct"] == 0.0  # ...but the keys are wrong -> wrong
        assert v.score == 0.5 and not v.passed

    def test_correct_composite_passes(self):
        gold = {"yea": 2, "nay": 1}
        v = grade("fields", gold, dict(gold), is_refusal=False)
        assert v.passed and v.score == 1.0

    def test_non_dict_answer_is_malformed(self):
        v = grade("fields", {"yea": 2}, "yea", is_refusal=False)
        assert v.subscores["format_valid"] == 0.0
        assert v.subscores["decision_correct"] is None
        assert v.score == 0.0 and not v.passed

    def test_set_match_correct_passes(self):
        v = grade("set_match", {"p1", "p2"}, ["p1", "p2"], is_refusal=False)
        assert v.passed and v.score == 1.0

    def test_set_match_wrong_is_attempted_partial(self):
        v = grade("set_match", {"p1", "p2"}, ["p1", "p2", "NX-wrong"], is_refusal=False)
        assert v.subscores["decision_correct"] == 1.0
        assert v.subscores["answer_correct"] == 0.0
        assert v.score == 0.5 and not v.passed
