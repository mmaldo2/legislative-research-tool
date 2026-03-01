"""Tests for Pydantic analysis schemas."""

import pytest
from pydantic import ValidationError

from src.schemas.analysis import (
    BillSummaryOutput,
    ConstitutionalAnalysisOutput,
    ConstitutionalConcern,
    PatternBillInfo,
    PatternDetectRequest,
    PatternDetectionOutput,
    TopicClassificationOutput,
    VersionDiffChange,
    VersionDiffOutput,
)


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


class TestVersionDiffChange:
    def test_valid_change(self):
        change = VersionDiffChange(
            section="Section 3(a)",
            change_type="modified",
            significance="major",
            before="Original text of the provision.",
            after="Amended text of the provision.",
            description="Broadens enforcement scope.",
        )
        assert change.change_type == "modified"
        assert change.significance == "major"
        assert change.before is not None

    def test_minimal_change(self):
        change = VersionDiffChange(
            section="Section 1",
            change_type="added",
            significance="minor",
            description="New definitions section.",
        )
        assert change.before is None
        assert change.after is None

    def test_invalid_change_type_rejected(self):
        with pytest.raises(ValidationError):
            VersionDiffChange(
                section="Section 1",
                change_type="replaced",
                significance="minor",
                description="Invalid change type.",
            )

    def test_invalid_significance_rejected(self):
        with pytest.raises(ValidationError):
            VersionDiffChange(
                section="Section 1",
                change_type="added",
                significance="critical",
                description="Invalid significance.",
            )

    def test_serialization_roundtrip(self):
        original = VersionDiffChange(
            section="Section 5",
            change_type="removed",
            significance="moderate",
            before="Deleted provision text.",
            description="Removed sunset clause.",
        )
        data = original.model_dump()
        restored = VersionDiffChange(**data)
        assert restored == original


class TestVersionDiffOutput:
    def test_valid_output(self):
        output = VersionDiffOutput(
            version_a_name="Introduced",
            version_b_name="Enrolled",
            changes=[
                VersionDiffChange(
                    section="Section 2",
                    change_type="modified",
                    significance="major",
                    description="Changed threshold from $500 to $1000.",
                )
            ],
            summary_of_changes="Bill was narrowed in scope.",
            direction_of_change="narrowed scope",
            amendments_incorporated=["Floor Amendment 1"],
            confidence=0.85,
        )
        assert len(output.changes) == 1
        assert output.confidence == 0.85

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            VersionDiffOutput(
                version_a_name="A",
                version_b_name="B",
                changes=[],
                summary_of_changes="No changes.",
                direction_of_change="none",
                amendments_incorporated=[],
                confidence=1.5,
            )
        with pytest.raises(ValidationError):
            VersionDiffOutput(
                version_a_name="A",
                version_b_name="B",
                changes=[],
                summary_of_changes="No changes.",
                direction_of_change="none",
                amendments_incorporated=[],
                confidence=-0.1,
            )

    def test_serialization_roundtrip(self):
        original = VersionDiffOutput(
            version_a_name="Draft",
            version_b_name="Final",
            changes=[],
            summary_of_changes="Minimal changes.",
            direction_of_change="unchanged",
            amendments_incorporated=[],
            confidence=0.7,
        )
        data = original.model_dump()
        restored = VersionDiffOutput(**data)
        assert restored == original


class TestConstitutionalConcern:
    def test_valid_concern(self):
        concern = ConstitutionalConcern(
            provision="First Amendment",
            severity="high",
            bill_section="Section 4(b)",
            description="May restrict protected speech.",
            relevant_precedents=["Brandenburg v. Ohio", "Tinker v. Des Moines"],
        )
        assert concern.severity == "high"
        assert len(concern.relevant_precedents) == 2

    def test_minimal_concern(self):
        concern = ConstitutionalConcern(
            provision="Commerce Clause",
            severity="low",
            bill_section="Section 1",
            description="Minor interstate commerce question.",
            relevant_precedents=[],
        )
        assert concern.relevant_precedents == []

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValidationError):
            ConstitutionalConcern(
                provision="14th Amendment",
                severity="critical",
                bill_section="Section 2",
                description="Invalid severity.",
                relevant_precedents=[],
            )

    def test_serialization_roundtrip(self):
        original = ConstitutionalConcern(
            provision="4th Amendment",
            severity="moderate",
            bill_section="Section 7",
            description="Search and seizure concerns.",
            relevant_precedents=["Katz v. United States"],
        )
        data = original.model_dump()
        restored = ConstitutionalConcern(**data)
        assert restored == original


class TestConstitutionalAnalysisOutput:
    def test_valid_output(self):
        output = ConstitutionalAnalysisOutput(
            concerns=[
                ConstitutionalConcern(
                    provision="Due Process",
                    severity="moderate",
                    bill_section="Section 3",
                    description="Procedural due process question.",
                    relevant_precedents=["Mathews v. Eldridge"],
                )
            ],
            preemption_issues=["May conflict with federal ADA requirements"],
            has_severability_clause=True,
            overall_risk_level="moderate",
            summary="Bill raises moderate constitutional questions.",
            confidence=0.78,
        )
        assert output.overall_risk_level == "moderate"
        assert output.has_severability_clause is True

    def test_all_risk_levels(self):
        for level in ("high", "moderate", "low", "minimal", "unknown"):
            output = ConstitutionalAnalysisOutput(
                concerns=[],
                preemption_issues=[],
                has_severability_clause=False,
                overall_risk_level=level,
                summary="Test.",
                confidence=0.5,
            )
            assert output.overall_risk_level == level

    def test_invalid_risk_level_rejected(self):
        with pytest.raises(ValidationError):
            ConstitutionalAnalysisOutput(
                concerns=[],
                preemption_issues=[],
                has_severability_clause=False,
                overall_risk_level="extreme",
                summary="Invalid risk.",
                confidence=0.5,
            )

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            ConstitutionalAnalysisOutput(
                concerns=[],
                preemption_issues=[],
                has_severability_clause=False,
                overall_risk_level="low",
                summary="Out of bounds.",
                confidence=2.0,
            )

    def test_serialization_roundtrip(self):
        original = ConstitutionalAnalysisOutput(
            concerns=[],
            preemption_issues=["Federal preemption concern"],
            has_severability_clause=True,
            overall_risk_level="low",
            summary="Low risk overall.",
            confidence=0.9,
        )
        data = original.model_dump()
        restored = ConstitutionalAnalysisOutput(**data)
        assert restored == original


class TestPatternBillInfo:
    def test_valid_bill_info(self):
        info = PatternBillInfo(
            bill_id="ocd-bill/abc-123",
            identifier="HB 1234",
            jurisdiction_id="ocd-jurisdiction/country:us/state:tx",
            title="Texas Consumer Privacy Act",
            variations=["Higher penalties", "Broader exemptions"],
        )
        assert info.identifier == "HB 1234"
        assert len(info.variations) == 2

    def test_empty_variations(self):
        info = PatternBillInfo(
            bill_id="ocd-bill/xyz",
            identifier="SB 5",
            jurisdiction_id="ocd-jurisdiction/country:us/state:ca",
            title="California Version",
            variations=[],
        )
        assert info.variations == []

    def test_serialization_roundtrip(self):
        original = PatternBillInfo(
            bill_id="ocd-bill/test",
            identifier="AB 100",
            jurisdiction_id="ocd-jurisdiction/country:us/state:ny",
            title="Test Bill",
            variations=["Variation A"],
        )
        data = original.model_dump()
        restored = PatternBillInfo(**data)
        assert restored == original


class TestPatternDetectionOutput:
    def test_valid_output(self):
        output = PatternDetectionOutput(
            pattern_type="adapted",
            common_framework="Model Consumer Privacy Act",
            source_organization="NCSL",
            bills_analyzed=[
                PatternBillInfo(
                    bill_id="ocd-bill/1",
                    identifier="HB 100",
                    jurisdiction_id="ocd-jurisdiction/country:us/state:co",
                    title="Colorado Privacy Act",
                    variations=["Opt-out mechanism differs"],
                )
            ],
            shared_provisions=["Right to delete", "Data controller obligations"],
            key_variations=["Enforcement mechanisms differ"],
            model_legislation_confidence=0.82,
            summary="Bills share a common framework adapted per state.",
            confidence=0.88,
        )
        assert output.pattern_type == "adapted"
        assert output.source_organization == "NCSL"
        assert output.model_legislation_confidence == 0.82

    def test_all_pattern_types(self):
        for ptype in ("identical", "adapted", "inspired", "coincidental", "unknown"):
            output = PatternDetectionOutput(
                pattern_type=ptype,
                common_framework="Test",
                bills_analyzed=[],
                shared_provisions=[],
                key_variations=[],
                model_legislation_confidence=0.5,
                summary="Test.",
                confidence=0.5,
            )
            assert output.pattern_type == ptype

    def test_invalid_pattern_type_rejected(self):
        with pytest.raises(ValidationError):
            PatternDetectionOutput(
                pattern_type="derivative",
                common_framework="Test",
                bills_analyzed=[],
                shared_provisions=[],
                key_variations=[],
                model_legislation_confidence=0.5,
                summary="Invalid pattern type.",
                confidence=0.5,
            )

    def test_both_confidence_bounds(self):
        with pytest.raises(ValidationError):
            PatternDetectionOutput(
                pattern_type="unknown",
                common_framework="Test",
                bills_analyzed=[],
                shared_provisions=[],
                key_variations=[],
                model_legislation_confidence=1.5,
                summary="Out of bounds.",
                confidence=0.5,
            )
        with pytest.raises(ValidationError):
            PatternDetectionOutput(
                pattern_type="unknown",
                common_framework="Test",
                bills_analyzed=[],
                shared_provisions=[],
                key_variations=[],
                model_legislation_confidence=0.5,
                summary="Out of bounds.",
                confidence=-0.1,
            )

    def test_optional_source_organization(self):
        output = PatternDetectionOutput(
            pattern_type="coincidental",
            common_framework="None identified",
            bills_analyzed=[],
            shared_provisions=[],
            key_variations=[],
            model_legislation_confidence=0.1,
            summary="No clear source.",
            confidence=0.6,
        )
        assert output.source_organization is None

    def test_serialization_roundtrip(self):
        original = PatternDetectionOutput(
            pattern_type="inspired",
            common_framework="Uniform Law",
            source_organization="ALEC",
            bills_analyzed=[],
            shared_provisions=["Shared A"],
            key_variations=["Var A"],
            model_legislation_confidence=0.7,
            summary="Inspired by model legislation.",
            confidence=0.75,
        )
        data = original.model_dump()
        restored = PatternDetectionOutput(**data)
        assert restored == original


class TestPatternDetectRequest:
    def test_default_top_k(self):
        req = PatternDetectRequest(bill_id="ocd-bill/test")
        assert req.top_k == 5

    def test_custom_top_k(self):
        req = PatternDetectRequest(bill_id="ocd-bill/test", top_k=10)
        assert req.top_k == 10

    def test_top_k_lower_bound(self):
        with pytest.raises(ValidationError):
            PatternDetectRequest(bill_id="ocd-bill/test", top_k=0)

    def test_top_k_upper_bound(self):
        with pytest.raises(ValidationError):
            PatternDetectRequest(bill_id="ocd-bill/test", top_k=21)

    def test_top_k_boundary_values(self):
        req_min = PatternDetectRequest(bill_id="ocd-bill/test", top_k=1)
        assert req_min.top_k == 1
        req_max = PatternDetectRequest(bill_id="ocd-bill/test", top_k=20)
        assert req_max.top_k == 20
