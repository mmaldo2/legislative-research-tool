"""Tests for analysis API schemas and request validation."""

from src.schemas.analysis import (
    BillComparisonOutput,
    BillSummaryOutput,
    ClassifyRequest,
    SummarizeRequest,
    TopicClassificationOutput,
)


class TestSummarizeRequest:
    def test_valid_request(self):
        req = SummarizeRequest(bill_id="abc123")
        assert req.bill_id == "abc123"


class TestClassifyRequest:
    def test_valid_request(self):
        req = ClassifyRequest(bill_id="abc123")
        assert req.bill_id == "abc123"


class TestAnalysisOutputSchemas:
    def test_summary_output_roundtrip(self):
        output = BillSummaryOutput(
            plain_english_summary="Test summary for a data privacy bill.",
            key_provisions=["Right to access", "Right to delete"],
            affected_populations=["Consumers", "Businesses"],
            changes_to_existing_law=["Amends Section 5 of FTC Act"],
            fiscal_implications="$10M estimated enforcement cost",
            effective_date="2026-01-01",
            confidence=0.95,
        )
        data = output.model_dump()
        restored = BillSummaryOutput(**data)
        assert restored.confidence == 0.95
        assert len(restored.key_provisions) == 2

    def test_classification_output(self):
        output = TopicClassificationOutput(
            primary_topic="Technology & Communications",
            secondary_topics=["Consumer Protection", "Privacy"],
            policy_area="Data Privacy",
            confidence=0.88,
        )
        assert output.primary_topic == "Technology & Communications"

    def test_comparison_output(self):
        output = BillComparisonOutput(
            similarities=["Both address data privacy"],
            differences=["Scope differs — federal vs state"],
            key_changes=["Added enforcement mechanism"],
            overall_assessment="Substantially similar with key enforcement differences",
            similarity_score=0.78,
        )
        assert output.similarity_score == 0.78
        assert len(output.differences) == 1
