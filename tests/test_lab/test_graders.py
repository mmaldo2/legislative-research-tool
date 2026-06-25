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
    def test_exact(self):
        assert grade("exact", "nay", "nay")
        assert not grade("exact", "nay", "yea")

    def test_refusal(self):
        assert grade("refusal_correct", REFUSAL, REFUSAL)
        assert not grade("refusal_correct", REFUSAL, "present")
