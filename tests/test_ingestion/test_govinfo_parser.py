"""Tests for GovInfo XML parsing (no network calls)."""

from datetime import date

import defusedxml.ElementTree as SafeET

from src.ingestion.govinfo import (
    BILL_TYPES,
    CONGRESS_DATES,
    STATUS_PRECEDENCE,
    _parse_bill_type_number,
)
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
        subjects = [s.text for s in root.findall(".//legislativeSubjects/item/name") if s.text]
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

    def test_extract_introduced_date(self, sample_bill_xml):
        """introducedDate element is extracted from BILLSTATUS XML."""
        root = SafeET.fromstring(sample_bill_xml)
        bill_el = root.find(".//bill")
        intro_str = bill_el.findtext("introducedDate")
        assert intro_str == "2025-01-15"
        assert date.fromisoformat(intro_str) == date(2025, 1, 15)

    def test_extract_sponsors(self, sample_bill_xml):
        """Sponsors are extracted from BILLSTATUS XML."""
        root = SafeET.fromstring(sample_bill_xml)
        bill_el = root.find(".//bill")
        sponsors = bill_el.findall(".//sponsors/item")
        assert len(sponsors) == 1
        assert sponsors[0].findtext("bioguideId") == "S001150"
        assert sponsors[0].findtext("party") == "D"
        assert "Smith" in sponsors[0].findtext("fullName")

    def test_extract_cosponsors(self, sample_bill_xml):
        """Cosponsors are extracted from BILLSTATUS XML."""
        root = SafeET.fromstring(sample_bill_xml)
        bill_el = root.find(".//bill")
        cosponsors = bill_el.findall(".//cosponsors/item")
        assert len(cosponsors) == 1
        assert cosponsors[0].findtext("bioguideId") == "J000295"
        assert cosponsors[0].findtext("party") == "R"


class TestCongressDates:
    """Test congress date lookup and bill type constants."""

    def test_congress_dates_cover_110_to_119(self):
        """CONGRESS_DATES covers all congresses needed for backfill."""
        for congress in range(110, 120):
            assert congress in CONGRESS_DATES, f"Missing dates for Congress {congress}"

    def test_congress_dates_are_valid_iso_dates(self):
        """All congress dates parse as valid ISO dates."""
        for congress, (start, end) in CONGRESS_DATES.items():
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
            assert start_date < end_date, f"Congress {congress}: start >= end"

    def test_congress_dates_are_chronological(self):
        """Congress dates progress chronologically."""
        congresses = sorted(CONGRESS_DATES.keys())
        for i in range(len(congresses) - 1):
            _, end_a = CONGRESS_DATES[congresses[i]]
            start_b, _ = CONGRESS_DATES[congresses[i + 1]]
            assert date.fromisoformat(end_a) <= date.fromisoformat(start_b), (
                f"Congress {congresses[i]} overlaps with {congresses[i + 1]}"
            )

    def test_bill_types_include_all_federal_types(self):
        """BILL_TYPES covers all federal bill types."""
        assert "hr" in BILL_TYPES
        assert "s" in BILL_TYPES
        assert "hjres" in BILL_TYPES
        assert "sjres" in BILL_TYPES
        assert "hres" in BILL_TYPES
        assert "sres" in BILL_TYPES
        assert "hconres" in BILL_TYPES
        assert "sconres" in BILL_TYPES
        assert len(BILL_TYPES) == 8


class TestStatusPrecedence:
    """Test status precedence for action-based status determination."""

    def test_enacted_is_highest(self):
        assert STATUS_PRECEDENCE["enacted"] >= max(STATUS_PRECEDENCE.values())

    def test_introduced_is_lowest(self):
        assert STATUS_PRECEDENCE["introduced"] <= min(STATUS_PRECEDENCE.values())

    def test_passed_lower_before_passed_upper(self):
        assert STATUS_PRECEDENCE["passed_lower"] < STATUS_PRECEDENCE["passed_upper"]

    def test_enrolled_before_enacted(self):
        assert STATUS_PRECEDENCE["enrolled"] < STATUS_PRECEDENCE["enacted"]

    def test_all_canonical_statuses_covered(self):
        """Every status from normalize_bill_status has a precedence."""
        canonical = {
            "introduced", "in_committee", "passed_lower", "passed_upper",
            "enrolled", "enacted", "vetoed", "failed", "withdrawn", "other",
        }
        for status in canonical:
            assert status in STATUS_PRECEDENCE, f"Missing: {status}"

    def test_best_status_from_action_list(self):
        """Simulate scanning actions to find best status."""
        action_texts = [
            "Introduced in House",
            "Referred to the Committee on Energy and Commerce",
            "Passed House by voice vote",
            "Received in the Senate",
        ]
        best = "introduced"
        for text in action_texts:
            s = normalize_bill_status(text)
            if STATUS_PRECEDENCE.get(s, 0) > STATUS_PRECEDENCE.get(best, 0):
                best = s
        assert best == "passed_lower"


class TestParseBillTypeNumber:
    """Test parsing congress_bill_id into type and number."""

    def test_hr_bill(self):
        assert _parse_bill_type_number("hr1234-118") == ("hr", "1234")

    def test_senate_bill(self):
        assert _parse_bill_type_number("s567-117") == ("s", "567")

    def test_joint_resolution(self):
        assert _parse_bill_type_number("hjres42-118") == ("hjres", "42")

    def test_concurrent_resolution(self):
        assert _parse_bill_type_number("sconres10-110") == ("sconres", "10")
