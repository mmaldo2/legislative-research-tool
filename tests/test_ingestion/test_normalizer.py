"""Tests for the normalization utilities."""

from src.ingestion.normalizer import (
    content_hash,
    generate_bill_id,
    generate_text_id,
    normalize_bill_status,
    normalize_identifier,
    word_count,
)


class TestNormalizeBillStatus:
    def test_introduced(self):
        assert normalize_bill_status("Introduced in House") == "introduced"

    def test_passed_house(self):
        assert normalize_bill_status("Passed House") == "passed_lower"

    def test_passed_senate(self):
        assert normalize_bill_status("Passed Senate") == "passed_upper"

    def test_enacted(self):
        assert normalize_bill_status("Became Law") == "enacted"
        assert normalize_bill_status("Signed by the Governor") == "enacted"

    def test_vetoed(self):
        assert normalize_bill_status("Vetoed by Governor") == "vetoed"

    def test_failed(self):
        assert normalize_bill_status("Failed in Committee") == "failed"

    def test_unknown_returns_other(self):
        assert normalize_bill_status("Some weird status") == "other"

    def test_case_insensitive(self):
        assert normalize_bill_status("INTRODUCED IN HOUSE") == "introduced"

    def test_referred_to_committee(self):
        assert normalize_bill_status("Referred to Committee") == "in_committee"


class TestNormalizeIdentifier:
    def test_hr_bill(self):
        assert normalize_identifier("H.R. 1234") == "HR 1234"

    def test_senate_bill(self):
        assert normalize_identifier("S. 567") == "S 567"

    def test_already_clean(self):
        assert normalize_identifier("HB 1234") == "HB 1234"

    def test_extra_whitespace(self):
        assert normalize_identifier("H.R.  1234") == "HR 1234"


class TestGenerateIds:
    def test_bill_id_deterministic(self):
        id1 = generate_bill_id("us", "us-119", "HR 1234")
        id2 = generate_bill_id("us", "us-119", "HR 1234")
        assert id1 == id2

    def test_bill_id_differs_by_jurisdiction(self):
        id1 = generate_bill_id("us", "us-119", "HR 1234")
        id2 = generate_bill_id("us-ca", "us-ca-2025", "HR 1234")
        assert id1 != id2

    def test_text_id_deterministic(self):
        id1 = generate_text_id("bill-123", "Introduced")
        id2 = generate_text_id("bill-123", "Introduced")
        assert id1 == id2

    def test_text_id_differs_by_version(self):
        id1 = generate_text_id("bill-123", "Introduced")
        id2 = generate_text_id("bill-123", "Engrossed")
        assert id1 != id2


class TestContentHash:
    def test_deterministic(self):
        h1 = content_hash("some text")
        h2 = content_hash("some text")
        assert h1 == h2

    def test_different_content(self):
        h1 = content_hash("text a")
        h2 = content_hash("text b")
        assert h1 != h2


class TestWordCount:
    def test_normal_text(self):
        assert word_count("one two three four five") == 5

    def test_none(self):
        assert word_count(None) is None

    def test_empty(self):
        assert word_count("") is None
