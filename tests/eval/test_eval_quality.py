"""Evaluation suite for AI analysis quality using golden set data.

Tests LLM output quality against annotated golden set cases.
Run with: pytest tests/eval/ -v --run-eval
Skip by default in CI — requires ANTHROPIC_API_KEY and is slow/expensive.
"""

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from src.config import settings

logger = logging.getLogger(__name__)

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"

# Skip entire module unless --run-eval flag is provided
pytestmark = pytest.mark.skipif(
    "not config.getoption('--run-eval', default=False)",
)


def load_golden_set() -> list[dict[str, Any]]:
    """Load golden set test cases from JSON."""
    with open(GOLDEN_SET_PATH) as f:
        data = json.load(f)
    return data["test_cases"]


def get_cases_by_category(category: str) -> list[dict[str, Any]]:
    """Filter golden set cases by category."""
    return [c for c in load_golden_set() if c["category"] == category]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def harness():
    """Create a real LLMHarness for evaluation (no DB session)."""
    if not settings.anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    from src.llm.harness import LLMHarness

    return LLMHarness(db_session=None)


# ---------------------------------------------------------------------------
# Summarization quality tests
# ---------------------------------------------------------------------------


class TestSummarizationQuality:
    """Evaluate bill summarization against golden set expectations."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        get_cases_by_category("summarization"),
        ids=lambda c: c["id"],
    )
    async def test_summary_mentions_key_terms(self, harness, case):
        """Summary output must mention all required terms."""
        inp = case["input"]
        expected = case["expected"]

        output = await harness.summarize(
            bill_id=f"eval-{case['id']}",
            bill_text=inp["bill_text"],
            identifier=inp["identifier"],
            jurisdiction=inp["jurisdiction"],
            title=inp["title"],
        )

        summary_text = output.plain_english_summary.lower()
        missing = [term for term in expected["must_mention"] if term.lower() not in summary_text]
        assert not missing, (
            f"Summary missing required terms: {missing}\n"
            f"Summary: {output.plain_english_summary[:500]}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        get_cases_by_category("summarization"),
        ids=lambda c: c["id"],
    )
    async def test_summary_avoids_hallucination(self, harness, case):
        """Summary must not mention terms that aren't in the bill."""
        inp = case["input"]
        expected = case["expected"]

        output = await harness.summarize(
            bill_id=f"eval-{case['id']}",
            bill_text=inp["bill_text"],
            identifier=inp["identifier"],
            jurisdiction=inp["jurisdiction"],
            title=inp["title"],
        )

        summary_text = output.plain_english_summary.lower()
        hallucinated = [
            term for term in expected.get("must_not_mention", []) if term.lower() in summary_text
        ]
        assert not hallucinated, (
            f"Summary contains hallucinated terms: {hallucinated}\n"
            f"Summary: {output.plain_english_summary[:500]}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        get_cases_by_category("summarization"),
        ids=lambda c: c["id"],
    )
    async def test_summary_has_sufficient_provisions(self, harness, case):
        """Summary must identify a minimum number of key provisions."""
        inp = case["input"]
        expected = case["expected"]

        output = await harness.summarize(
            bill_id=f"eval-{case['id']}",
            bill_text=inp["bill_text"],
            identifier=inp["identifier"],
            jurisdiction=inp["jurisdiction"],
            title=inp["title"],
        )

        min_provisions = expected.get("key_provisions_min_count", 1)
        assert len(output.key_provisions) >= min_provisions, (
            f"Expected at least {min_provisions} key provisions, "
            f"got {len(output.key_provisions)}: {output.key_provisions}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        get_cases_by_category("summarization"),
        ids=lambda c: c["id"],
    )
    async def test_summary_identifies_affected_populations(self, harness, case):
        """Summary must identify affected populations."""
        inp = case["input"]
        expected = case["expected"]

        output = await harness.summarize(
            bill_id=f"eval-{case['id']}",
            bill_text=inp["bill_text"],
            identifier=inp["identifier"],
            jurisdiction=inp["jurisdiction"],
            title=inp["title"],
        )

        min_pops = expected.get("affected_populations_min_count", 1)
        assert len(output.affected_populations) >= min_pops, (
            f"Expected at least {min_pops} affected populations, "
            f"got {len(output.affected_populations)}: {output.affected_populations}"
        )


# ---------------------------------------------------------------------------
# Classification quality tests
# ---------------------------------------------------------------------------


class TestClassificationQuality:
    """Evaluate topic classification against golden set expectations."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        get_cases_by_category("classification"),
        ids=lambda c: c["id"],
    )
    async def test_primary_topic_accuracy(self, harness, case):
        """Primary topic must be one of the expected values."""
        inp = case["input"]
        expected = case["expected"]

        output = await harness.classify(
            bill_id=f"eval-{case['id']}",
            identifier=inp["identifier"],
            title=inp["title"],
            summary=inp["summary"],
        )

        valid_topics = [t.lower() for t in expected["primary_topic_must_be_one_of"]]
        actual = output.primary_topic.lower()
        assert any(valid in actual or actual in valid for valid in valid_topics), (
            f"Primary topic '{output.primary_topic}' not in expected: "
            f"{expected['primary_topic_must_be_one_of']}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        get_cases_by_category("classification"),
        ids=lambda c: c["id"],
    )
    async def test_secondary_topics_relevance(self, harness, case):
        """At least one secondary topic must match expected topics."""
        inp = case["input"]
        expected = case["expected"]

        output = await harness.classify(
            bill_id=f"eval-{case['id']}",
            identifier=inp["identifier"],
            title=inp["title"],
            summary=inp["summary"],
        )

        expected_secondaries = [t.lower() for t in expected["must_include_secondary_topic_from"]]
        actual_secondaries = [t.lower() for t in output.secondary_topics]

        # Check if any expected topic appears in or contains any actual topic
        found = any(
            any(exp in act or act in exp for act in actual_secondaries)
            for exp in expected_secondaries
        )
        assert found, (
            f"No expected secondary topic found.\n"
            f"Expected one of: {expected['must_include_secondary_topic_from']}\n"
            f"Got: {output.secondary_topics}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        get_cases_by_category("classification"),
        ids=lambda c: c["id"],
    )
    async def test_classification_confidence(self, harness, case):
        """Classification confidence must meet minimum threshold."""
        inp = case["input"]
        expected = case["expected"]

        output = await harness.classify(
            bill_id=f"eval-{case['id']}",
            identifier=inp["identifier"],
            title=inp["title"],
            summary=inp["summary"],
        )

        min_conf = expected.get("confidence_min", 0.5)
        assert output.confidence >= min_conf, (
            f"Confidence {output.confidence} below minimum {min_conf}"
        )


# ---------------------------------------------------------------------------
# Constitutional analysis quality tests
# ---------------------------------------------------------------------------


class TestConstitutionalAnalysisQuality:
    """Evaluate constitutional analysis against golden set expectations."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        get_cases_by_category("constitutional_analysis"),
        ids=lambda c: c["id"],
    )
    async def test_identifies_expected_concerns(self, harness, case):
        """Analysis must identify the expected constitutional concerns."""
        inp = case["input"]
        expected = case["expected"]

        output = await harness.constitutional_analysis(
            bill_id=f"eval-{case['id']}",
            bill_text=inp["bill_text"],
            identifier=inp["identifier"],
            jurisdiction=inp["jurisdiction"],
            title=inp["title"],
        )

        # Collect all concern text for matching
        concern_texts = " ".join(f"{c.clause} {c.description}" for c in output.concerns).lower()

        # Also check preemption issues
        preemption_texts = " ".join(
            f"{p}" if isinstance(p, str) else str(p) for p in output.preemption_issues
        ).lower()

        all_text = f"{concern_texts} {preemption_texts} {output.summary.lower()}"

        for expected_concern in expected["must_identify_concerns_about"]:
            assert expected_concern.lower() in all_text, (
                f"Missing expected concern: '{expected_concern}'\n"
                f"Found concerns: {[c.clause for c in output.concerns]}\n"
                f"Preemption issues: {output.preemption_issues}"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        get_cases_by_category("constitutional_analysis"),
        ids=lambda c: c["id"],
    )
    async def test_minimum_concerns_count(self, harness, case):
        """Analysis must identify at least the minimum number of concerns."""
        inp = case["input"]
        expected = case["expected"]

        output = await harness.constitutional_analysis(
            bill_id=f"eval-{case['id']}",
            bill_text=inp["bill_text"],
            identifier=inp["identifier"],
            jurisdiction=inp["jurisdiction"],
            title=inp["title"],
        )

        min_count = expected.get("min_concerns_count", 1)
        total = len(output.concerns) + len(output.preemption_issues)
        assert total >= min_count, (
            f"Expected at least {min_count} concerns, got {total} "
            f"({len(output.concerns)} concerns + {len(output.preemption_issues)} preemption)"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        get_cases_by_category("constitutional_analysis"),
        ids=lambda c: c["id"],
    )
    async def test_overall_risk_level(self, harness, case):
        """Overall risk assessment must be one of expected levels."""
        inp = case["input"]
        expected = case["expected"]

        output = await harness.constitutional_analysis(
            bill_id=f"eval-{case['id']}",
            bill_text=inp["bill_text"],
            identifier=inp["identifier"],
            jurisdiction=inp["jurisdiction"],
            title=inp["title"],
        )

        valid_levels = [level.lower() for level in expected["overall_risk_must_be_one_of"]]
        actual = output.overall_risk_level.lower()
        assert actual in valid_levels, (
            f"Risk level '{output.overall_risk_level}' not in expected: "
            f"{expected['overall_risk_must_be_one_of']}"
        )


# ---------------------------------------------------------------------------
# Structural quality tests (run without API)
# ---------------------------------------------------------------------------


class TestGoldenSetIntegrity:
    """Validate the golden set data itself."""

    def test_golden_set_loads(self):
        cases = load_golden_set()
        assert len(cases) > 0, "Golden set is empty"

    def test_all_cases_have_required_fields(self):
        for case in load_golden_set():
            assert "id" in case, f"Case missing 'id': {case}"
            assert "category" in case, f"Case {case.get('id')} missing 'category'"
            assert "input" in case, f"Case {case['id']} missing 'input'"
            assert "expected" in case, f"Case {case['id']} missing 'expected'"

    def test_unique_ids(self):
        cases = load_golden_set()
        ids = [c["id"] for c in cases]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"

    def test_all_categories_represented(self):
        cases = load_golden_set()
        categories = {c["category"] for c in cases}
        expected_categories = {
            "summarization",
            "classification",
            "constitutional_analysis",
            "prediction",
        }
        assert expected_categories.issubset(categories), (
            f"Missing categories: {expected_categories - categories}"
        )

    def test_summarization_cases_have_bill_text(self):
        for case in get_cases_by_category("summarization"):
            assert "bill_text" in case["input"], f"Case {case['id']} missing bill_text"
            assert len(case["input"]["bill_text"]) > 100, f"Case {case['id']} bill_text too short"

    def test_classification_cases_have_summary(self):
        for case in get_cases_by_category("classification"):
            assert "summary" in case["input"], f"Case {case['id']} missing summary"

    def test_constitutional_cases_have_bill_text(self):
        for case in get_cases_by_category("constitutional_analysis"):
            assert "bill_text" in case["input"], f"Case {case['id']} missing bill_text"
