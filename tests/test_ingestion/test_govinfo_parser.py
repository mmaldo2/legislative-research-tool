"""Tests for GovInfo XML parsing (no network calls)."""

import defusedxml.ElementTree as SafeET

from src.ingestion.normalizer import normalize_bill_status, normalize_identifier


class TestBillStatusXmlParsing:
    """Test parsing of BILLSTATUS XML documents."""

    def test_parse_basic_bill(self, sample_bill_xml):
        root = SafeET.fromstring(sample_bill_xml)
        bill_el = root.find(".//bill")

        assert bill_el is not None
        assert bill_el.findtext("billNumber") == "1234"
        assert bill_el.findtext("billType") == "hr"
        assert bill_el.findtext("title") == "Consumer Data Privacy Act of 2025"

    def test_extract_subjects(self, sample_bill_xml):
        root = SafeET.fromstring(sample_bill_xml)
        subjects = [
            s.text
            for s in root.findall(".//legislativeSubjects/item/name")
            if s.text
        ]
        assert "Right of privacy" in subjects
        assert "Consumer protection" in subjects

    def test_extract_actions(self, sample_bill_xml):
        root = SafeET.fromstring(sample_bill_xml)
        actions = []
        for action_el in root.findall(".//actions/item"):
            action_date = action_el.findtext("actionDate")
            action_text = action_el.findtext("text")
            if action_date and action_text:
                actions.append({"date": action_date, "text": action_text})

        assert len(actions) == 2
        assert actions[0]["text"] == "Introduced in House"
        assert actions[1]["date"] == "2025-02-10"

    def test_determine_status_from_actions(self, sample_bill_xml):
        root = SafeET.fromstring(sample_bill_xml)
        actions = root.findall(".//actions/item")
        latest_text = actions[-1].findtext("text") or ""
        status = normalize_bill_status(latest_text)
        assert status == "in_committee"

    def test_normalize_identifier_from_xml(self, sample_bill_xml):
        root = SafeET.fromstring(sample_bill_xml)
        bill_el = root.find(".//bill")
        bill_type = (bill_el.findtext("billType") or "hr").lower()
        bill_number = bill_el.findtext("billNumber") or ""
        identifier = normalize_identifier(f"{bill_type}{bill_number}")
        assert identifier == "HR1234"
