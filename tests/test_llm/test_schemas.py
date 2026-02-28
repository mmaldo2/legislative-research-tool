"""Tests for Pydantic analysis schemas."""

from src.schemas.analysis import BillSummaryOutput, TopicClassificationOutput


class TestBillSummaryOutput:
    def test_valid_summary(self):
        summary = BillSummaryOutput(
            plain_english_summary="This bill establishes consumer data privacy rights.",
            key_provisions=[
                "Right to access personal data",
                "Right to delete personal data",
            ],
            affected_populations=["Consumers", "Data controllers"],
            changes_to_existing_law=["Amends unfair trade practices statute"],
            fiscal_implications="Minimal — enforcement via existing AG office",
            effective_date="January 1, 2026",
            confidence=0.92,
        )
        assert summary.confidence == 0.92
        assert len(summary.key_provisions) == 2

    def test_minimal_summary(self):
        summary = BillSummaryOutput(
            plain_english_summary="Simple bill.",
            key_provisions=[],
            affected_populations=[],
            changes_to_existing_law=[],
            confidence=0.5,
        )
        assert summary.fiscal_implications is None
        assert summary.effective_date is None

    def test_serialization_roundtrip(self):
        original = BillSummaryOutput(
            plain_english_summary="Test summary",
            key_provisions=["Provision A"],
            affected_populations=["Group A"],
            changes_to_existing_law=[],
            confidence=0.8,
        )
        data = original.model_dump()
        restored = BillSummaryOutput(**data)
        assert restored == original


class TestTopicClassificationOutput:
    def test_valid_classification(self):
        classification = TopicClassificationOutput(
            primary_topic="Health",
            secondary_topics=["Education", "Labor & Employment"],
            policy_area="Public Health",
            confidence=0.87,
        )
        assert classification.primary_topic == "Health"
        assert len(classification.secondary_topics) == 2
