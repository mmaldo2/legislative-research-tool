"""Tests for the vote-time-party parsing in CongressLegislatorsIngester (no network/DB).

The correctness core is the pure `_terms_to_spans` (half-open span construction + boundary
semantics + collect-don't-coerce). The live backfill + golden assertion is validated in 3a.3.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ingestion.congress_legislators import (
    CongressLegislatorsIngester,
    PartySpan,
    UnknownPartyError,
    _assert_disjoint,
    _terms_to_spans,
)


def _resolve(spans: list[PartySpan], d: date) -> list[str]:
    """As-of-date resolution (half-open) — what the lab join does in 3b."""
    return [s.party for s in spans if s.start_date <= d < s.end_date]


# Real Specter shape: a single term split by party_affiliations on a SHARED boundary day.
SPECTER = {
    "id": {"bioguide": "S000709"},
    "name": {"official_full": "Arlen Specter"},
    "terms": [
        {
            "type": "sen",
            "start": "2005-01-04",
            "end": "2011-01-03",
            "state": "PA",
            "party": "Republican",
            "party_affiliations": [
                {"start": "2005-01-04", "end": "2009-04-30", "party": "Republican"},
                {"start": "2009-04-30", "end": "2011-01-03", "party": "Democrat"},
            ],
        }
    ],
}


class TestTermsToSpans:
    def test_plain_term_single_half_open_span(self):
        leg = {
            "id": {"bioguide": "X000001"},
            "terms": [
                {"type": "rep", "start": "2007-01-04", "end": "2009-01-03", "party": "Democrat"}
            ],
        }
        anomalies = []
        spans = _terms_to_spans(leg, anomalies)
        assert spans == [PartySpan("D", date(2007, 1, 4), date(2009, 1, 4))]  # end = incl_end + 1
        assert anomalies == []
        assert all(isinstance(s.start_date, date) and isinstance(s.end_date, date) for s in spans)

    def test_specter_shared_boundary_disjoint_and_point_in_time(self):
        anomalies = []
        spans = _terms_to_spans(SPECTER, anomalies)
        assert spans == [
            PartySpan("R", date(2005, 1, 4), date(2009, 4, 30)),  # end == next start (shared)
            PartySpan("D", date(2009, 4, 30), date(2011, 1, 4)),  # last -> incl_end + 1
        ]
        # boundary day belongs to the LATER (Democrat) span; pre-switch is Republican.
        assert _resolve(spans, date(2009, 4, 28)) == ["R"]
        assert _resolve(spans, date(2009, 4, 29)) == ["R"]
        assert _resolve(spans, date(2009, 4, 30)) == ["D"]
        assert _resolve(spans, date(2010, 6, 1)) == ["D"]
        _assert_disjoint("S000709", spans)  # no overlap anywhere

    def test_service_gap_left_uncovered(self):
        leg = {
            "id": {"bioguide": "X000002"},
            "terms": [
                {"type": "rep", "start": "2007-01-04", "end": "2009-01-03", "party": "Democrat"},
                {"type": "rep", "start": "2013-01-03", "end": "2015-01-03", "party": "Democrat"},
            ],
        }
        spans = _terms_to_spans(leg, [])
        # first span ends at incl_end + 1 (NOT extended across the gap to the next term's start)
        assert spans[0].end_date == date(2009, 1, 4)
        assert _resolve(spans, date(2011, 1, 1)) == []  # in the gap -> unresolvable (correct)

    def test_libertarian_maps_to_l_code(self):
        leg = {
            "id": {"bioguide": "A000367"},
            "terms": [
                {"type": "rep", "start": "2019-01-03", "end": "2021-01-03", "party": "Libertarian"}
            ],
        }
        spans = _terms_to_spans(leg, [])
        assert [s.party for s in spans] == ["L"]

    def test_unknown_party_collected_not_coerced(self):
        leg = {
            "id": {"bioguide": "X000003"},
            "terms": [{"type": "rep", "start": "1850-01-01", "end": "1852-01-01", "party": "Whig"}],
        }
        anomalies = []
        spans = _terms_to_spans(leg, anomalies)
        assert spans == []  # the unrecognized span is dropped, NOT mapped to some default
        assert anomalies == [("X000003", "Whig")]

    def test_missing_dates_collected(self):
        leg = {
            "id": {"bioguide": "X000004"},
            "terms": [{"type": "rep", "start": "2007-01-04", "end": None, "party": "Democrat"}],
        }
        anomalies = []
        assert _terms_to_spans(leg, anomalies) == []
        assert anomalies and anomalies[0][0] == "X000004"


class TestAssertDisjoint:
    def test_overlap_raises(self):
        with pytest.raises(ValueError, match="overlapping"):
            _assert_disjoint(
                "X",
                [
                    PartySpan("R", date(2009, 1, 1), date(2009, 6, 2)),
                    PartySpan("D", date(2009, 6, 1), date(2010, 1, 1)),
                ],
            )

    def test_duplicate_start_raises(self):
        with pytest.raises(ValueError, match="share start_date"):
            _assert_disjoint(
                "X",
                [
                    PartySpan("R", date(2009, 1, 1), date(2009, 6, 1)),
                    PartySpan("D", date(2009, 1, 1), date(2010, 1, 1)),
                ],
            )

    def test_disjoint_ok(self):
        _assert_disjoint("X", _terms_to_spans(SPECTER, []))  # no raise


class TestSurfaceDontCoerce:
    @pytest.mark.asyncio
    async def test_unknown_party_fails_the_run(self):
        """An unnormalizable party must FAIL the backfill (surface), never silently coerce."""
        session = AsyncMock()
        session.add = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = ["X000003"]  # the Whig is a tracked voter
        session.execute = AsyncMock(return_value=result)

        ing = CongressLegislatorsIngester(session)
        ing._fetch_yaml = AsyncMock(
            side_effect=[
                [
                    {
                        "id": {"bioguide": "X000003"},
                        "terms": [
                            {
                                "type": "rep",
                                "start": "1850-01-01",
                                "end": "1852-01-01",
                                "party": "Whig",
                            }
                        ],
                    }
                ],
                [],  # historical
            ]
        )
        with pytest.raises(UnknownPartyError, match="Whig"):
            await ing.ingest_term_history()
