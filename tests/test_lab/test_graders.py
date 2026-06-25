"""Grader unit tests (no DB/LLM). The graders are the frozen anti-cheat floor."""

from lab.graders import REFUSAL, grade, grade_exact, grade_refusal_correct


class TestExact:
    def test_match(self):
        assert grade_exact("yea", "yea")

    def test_case_and_whitespace_insensitive(self):
        assert grade_exact("Yea", " yea ")

    def test_mismatch(self):
        assert not grade_exact("yea", "nay")

    def test_over_refusal_on_answerable_fails(self):
        # refusing an answerable item must be graded wrong (over-refusal caught)
        assert not grade_exact("yea", REFUSAL)


class TestRefusalCorrect:
    def test_refused_passes(self):
        assert grade_refusal_correct(REFUSAL, REFUSAL)

    def test_fabricated_answer_fails(self):
        # answering instead of refusing on a "not in the data" item is wrong
        assert not grade_refusal_correct(REFUSAL, "yea")


class TestDispatch:
    """grade() now returns a Verdict composed from the pure primitives above."""

    def test_exact_correct(self):
        v = grade("exact", "nay", "nay", is_refusal=False)
        assert v.passed and v.score == 1.0
        assert v.subscores["decision_correct"] == 1.0
        assert v.subscores["answer_correct"] == 1.0

    def test_exact_wrong_is_attempted_partial(self):
        v = grade("exact", "nay", "yea", is_refusal=False)
        assert not v.passed and v.score == 0.5  # attempted (decision 1) but wrong (answer 0)
        assert "yea" in v.feedback and "nay" in v.feedback

    def test_refusal_correct(self):
        v = grade("refusal_correct", REFUSAL, REFUSAL, is_refusal=True)
        assert v.passed and v.score == 1.0

    def test_refusal_fabricated_hard_floor(self):
        v = grade("refusal_correct", REFUSAL, "present", is_refusal=True)
        assert not v.passed and v.score == 0.0
