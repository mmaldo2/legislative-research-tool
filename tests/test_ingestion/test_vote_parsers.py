"""Tests for roll-call vote parsing/normalization (pure functions, no network/DB)."""

from datetime import date

import pytest

from src.ingestion.normalizer import generate_bill_id, normalize_identifier
from src.ingestion.vote_parsers import (
    build_lis_bioguide_map,
    build_member_map,
    house_vote_event_id,
    house_years_for_congress,
    is_bill_ref,
    normalize_vote_option,
    normalize_vote_ref,
    parse_house_action_date,
    parse_house_index,
    parse_house_roll_xml,
    parse_senate_date,
    parse_senate_vote_numbers,
    parse_senate_vote_xml,
    reconcile,
    senate_vote_event_id,
)

SAMPLE_HOUSE_ROLL = """<?xml version="1.0" encoding="UTF-8"?>
<rollcall-vote>
<vote-metadata>
<congress>118</congress>
<session>2nd</session>
<chamber>U.S. House of Representatives</chamber>
<rollcall-num>517</rollcall-num>
<legis-num>H R 10545</legis-num>
<vote-question>On Motion to Suspend the Rules and Pass</vote-question>
<vote-type>2/3 YEA-AND-NAY</vote-type>
<vote-result>Passed</vote-result>
<action-date>20-Dec-2024</action-date>
<vote-totals>
<totals-by-vote>
<total-stub>Totals</total-stub>
<yea-total>2</yea-total>
<nay-total>1</nay-total>
<present-total>0</present-total>
<not-voting-total>1</not-voting-total>
</totals-by-vote>
</vote-totals>
</vote-metadata>
<vote-data>
<recorded-vote>
<legislator name-id="A000001">Alpha</legislator><vote>Yea</vote>
</recorded-vote>
<recorded-vote>
<legislator name-id="B000002">Bravo</legislator><vote>Yea</vote>
</recorded-vote>
<recorded-vote>
<legislator name-id="C000003">Charlie</legislator><vote>Nay</vote>
</recorded-vote>
<recorded-vote>
<legislator name-id="D000004">Delta</legislator><vote>Not Voting</vote>
</recorded-vote>
</vote-data>
</rollcall-vote>"""

SAMPLE_QUORUM_ROLL = SAMPLE_HOUSE_ROLL.replace(
    "<legis-num>H R 10545</legis-num>", "<legis-num>QUORUM</legis-num>"
)


class TestNormalizeVoteRef:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("H R 1234", "HR1234"),
            ("H.R. 1234", "HR1234"),
            ("HR 1234", "HR1234"),
            ("S. 5", "S5"),
            ("S 567", "S567"),
            ("H RES 5", "HRES5"),
            ("H J RES 1", "HJRES1"),
            ("H CON RES 3", "HCONRES3"),
            ("S CON RES 7", "SCONRES7"),
        ],
    )
    def test_strips_all_whitespace_and_dots(self, raw, expected):
        assert normalize_vote_ref(raw) == expected

    def test_c1_byte_equal_to_stored_bill_id(self):
        """The dataset-killing bug guard: the spaced vote ref must resolve to the
        SAME bills.id as the stored (no-space) identifier path."""
        from_vote = generate_bill_id("us", "us-118", normalize_vote_ref("H R 10545"))
        stored = generate_bill_id("us", "us-118", normalize_identifier("hr10545"))
        assert from_vote == stored
        # ...and reusing normalize_identifier on the RAW spaced ref would NOT match.
        wrong = generate_bill_id("us", "us-118", normalize_identifier("H R 10545"))
        assert wrong != stored


class TestIsBillRef:
    @pytest.mark.parametrize(
        "ref", ["H R 1234", "S 5", "H RES 5", "H J RES 1", "H CON RES 3", "S CON RES 7"]
    )
    def test_bill_refs(self, ref):
        assert is_bill_ref(ref) is True

    @pytest.mark.parametrize("ref", ["QUORUM", "JOURNAL", "MOTION", "", None])
    def test_sentinels_and_empty(self, ref):
        assert is_bill_ref(ref) is False


class TestNormalizeVoteOption:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Yea", "yea"),
            ("Aye", "yea"),
            ("Yes", "yea"),
            ("Nay", "nay"),
            ("No", "nay"),
            ("Present", "present"),
            ("Not Voting", "not_voting"),
        ],
    )
    def test_known(self, raw, expected):
        assert normalize_vote_option(raw) == expected

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            normalize_vote_option("Maybe")


class TestHouseHelpers:
    def test_years_for_congress(self):
        assert house_years_for_congress(118) == [2023, 2024]
        assert house_years_for_congress(110) == [2007, 2008]

    def test_event_id_padding(self):
        assert house_vote_event_id(118, 2024, 517) == "us-house-118-2024-0517"
        assert house_vote_event_id(118, 2024, 7) == "us-house-118-2024-0007"

    def test_parse_action_date(self):
        assert parse_house_action_date("20-Dec-2024") == date(2024, 12, 20)
        assert parse_house_action_date("not-a-date") is None
        assert parse_house_action_date(None) is None

    def test_parse_index(self):
        html = "foo rollnumber=12 bar rollnumber=517 baz rollnumber=3"
        assert parse_house_index(html) == 517
        assert parse_house_index("no rolls here") == 0


class TestParseHouseRollXml:
    def test_parses_metadata_and_casts(self):
        v = parse_house_roll_xml(SAMPLE_HOUSE_ROLL)
        assert v is not None
        assert v.congress == 118
        assert v.rollcall_num == 517
        assert v.legis_num == "H R 10545"
        assert v.vote_result == "Passed"
        assert v.vote_date == date(2024, 12, 20)
        assert v.official == {"yea": 2, "nay": 1, "present": 0, "not_voting": 1}
        assert len(v.casts) == 4
        assert ("A000001", "Yea") in v.casts

    def test_unparseable_returns_none(self):
        assert parse_house_roll_xml("<not-valid") is None


class TestBuildMemberMap:
    def test_canonical_tiebreak_and_collision(self):
        rows = [
            ("A000001", "A000001"),  # canonical
            ("hashA", "A000001"),  # duplicate hash row for same member
            ("hashB", "B000002"),  # lone hash row
            ("hash1", "X000009"),  # collision: two non-canonical rows, no id==bioguide
            ("hash2", "X000009"),
        ]
        mapping, collisions = build_member_map(rows)
        assert mapping["A000001"] == "A000001"  # prefers canonical
        assert mapping["B000002"] == "hashB"  # lone row
        assert "X000009" in collisions  # ambiguous -> excluded
        assert "X000009" not in mapping


class TestReconcile:
    def test_exact(self):
        official = {"yea": 2, "nay": 1, "present": 0, "not_voting": 1}
        computed = {"yea": 2, "nay": 1, "not_voting": 1}
        assert reconcile(computed, {}, official) is True

    def test_with_dropped_members(self):
        official = {"yea": 2, "nay": 1, "present": 0, "not_voting": 1}
        computed = {"yea": 1, "nay": 1, "not_voting": 1}
        dropped = {"yea": 1}
        assert reconcile(computed, dropped, official) is True

    def test_mismatch(self):
        official = {"yea": 2, "nay": 1, "present": 0, "not_voting": 1}
        computed = {"yea": 1, "nay": 1, "not_voting": 1}
        assert reconcile(computed, {}, official) is False


SAMPLE_SENATE_VOTE = """<?xml version="1.0" encoding="UTF-8"?>
<roll_call_vote>
<congress>118</congress>
<session>2</session>
<congress_year>2024</congress_year>
<vote_number>339</vote_number>
<vote_date>December 21, 2024,  09:00 AM</vote_date>
<question>On Passage of the Bill</question>
<vote_result>Bill Passed</vote_result>
<document>
<document_type>H.R.</document_type>
<document_number>10545</document_number>
<document_name>H.R. 10545</document_name>
</document>
<count>
<yeas>2</yeas>
<nays>1</nays>
<present/>
<absent>1</absent>
</count>
<members>
<member><lis_member_id>S354</lis_member_id><vote_cast>Yea</vote_cast></member>
<member><lis_member_id>S001</lis_member_id><vote_cast>Yea</vote_cast></member>
<member><lis_member_id>S002</lis_member_id><vote_cast>Nay</vote_cast></member>
<member><lis_member_id>S003</lis_member_id><vote_cast>Not Voting</vote_cast></member>
</members>
</roll_call_vote>"""

SAMPLE_SENATE_MENU = """<?xml version="1.0" encoding="UTF-8"?>
<vote_summary>
<congress>118</congress>
<session>2</session>
<votes>
<vote><vote_number>00339</vote_number><issue>H.R. 10545</issue></vote>
<vote><vote_number>00338</vote_number><issue>H.R. 82</issue></vote>
</votes>
</vote_summary>"""


class TestSenateHelpers:
    def test_event_id_padding(self):
        assert senate_vote_event_id(118, 2, 339) == "us-senate-118-2-00339"

    def test_parse_date(self):
        assert parse_senate_date("December 21, 2024,  09:00 AM") == date(2024, 12, 21)
        assert parse_senate_date("January 8, 2024,  05:27 PM") == date(2024, 1, 8)
        assert parse_senate_date("garbage") is None
        assert parse_senate_date(None) is None

    def test_vote_numbers(self):
        assert parse_senate_vote_numbers(SAMPLE_SENATE_MENU) == [338, 339]

    def test_build_lis_bioguide_map(self):
        legs = [
            {"id": {"lis": "S354", "bioguide": "B001230"}},
            {"id": {"bioguide": "X000001"}},  # no lis -> excluded
            {"id": {"lis": "S999"}},  # no bioguide -> excluded
        ]
        assert build_lis_bioguide_map(legs) == {"S354": "B001230"}


class TestParseSenateVoteXml:
    def test_parses_bill_vote(self):
        v = parse_senate_vote_xml(SAMPLE_SENATE_VOTE)
        assert v is not None
        assert v.chamber == "senate"
        assert v.congress == 118
        assert v.session == "2"
        assert v.rollcall_num == 339
        assert v.legis_num == "H.R. 10545"
        assert is_bill_ref(v.legis_num) is True
        assert v.vote_date == date(2024, 12, 21)
        assert v.official == {"yea": 2, "nay": 1, "present": 0, "not_voting": 1}
        assert ("S354", "Yea") in v.casts
        assert len(v.casts) == 4

    def test_nomination_is_not_bill_ref(self):
        nom = SAMPLE_SENATE_VOTE.replace(
            "<document_name>H.R. 10545</document_name>", "<document_name>PN1020</document_name>"
        )
        v = parse_senate_vote_xml(nom)
        assert is_bill_ref(v.legis_num) is False
