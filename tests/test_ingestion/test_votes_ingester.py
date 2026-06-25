"""Tests for the VotesIngester (mocked HTTP + DB session, no network)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.normalizer import generate_bill_id
from src.ingestion.vote_parsers import normalize_vote_ref
from src.ingestion.votes import VotesIngester

SAMPLE_HOUSE_ROLL = """<?xml version="1.0" encoding="UTF-8"?>
<rollcall-vote>
<vote-metadata>
<congress>118</congress>
<session>2nd</session>
<rollcall-num>517</rollcall-num>
<legis-num>H R 10545</legis-num>
<vote-question>On Motion to Suspend the Rules and Pass</vote-question>
<vote-type>2/3 YEA-AND-NAY</vote-type>
<vote-result>Passed</vote-result>
<action-date>20-Dec-2024</action-date>
<vote-totals>
<totals-by-vote>
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

BILL_ID = generate_bill_id("us", "us-118", normalize_vote_ref("H R 10545"))
MEMBER_MAP = {
    "A000001": "A000001",
    "B000002": "B000002",
    "C000003": "C000003",
    "D000004": "D000004",
}


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    # begin_nested() returns an async context manager
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=None)
    cm.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=cm)
    return session


@pytest.fixture
def ingester(mock_session):
    ing = VotesIngester(mock_session, congress=118, chamber="house")
    ing._bill_ids = frozenset({BILL_ID})
    ing._member_map = dict(MEMBER_MAP)
    return ing


def test_source_name(ingester):
    assert ingester.source_name == "votes"


def test_init_defaults():
    ing = VotesIngester(AsyncMock())
    assert ing.congress == 119
    assert ing.chamber == "house"


class TestResolveMember:
    def test_resolves_known(self, ingester):
        assert ingester._resolve_member("A000001") == "A000001"

    def test_absent_returns_none(self, ingester):
        assert ingester._resolve_member("Z999999") is None

    def test_collision_returns_none(self, ingester):
        ingester._member_map.pop("C000003")  # simulate excluded (collision) member
        assert ingester._resolve_member("C000003") is None


class TestProcessHouseRoll:
    @pytest.mark.asyncio
    async def test_happy_path_upserts_event_and_records(self, ingester, mock_session):
        await ingester._process_house_roll(2024, 517, SAMPLE_HOUSE_ROLL, "us-118")
        assert ingester.metrics["events_created"] == 1
        assert ingester.metrics["records_created"] == 4  # all 4 members resolved
        assert ingester.metrics["members_resolved"] == 4
        # event upsert + records upsert both executed inside the savepoint
        assert mock_session.execute.call_count == 2
        assert mock_session.begin_nested.called

    @pytest.mark.asyncio
    async def test_out_of_scope_sentinel_skipped(self, ingester, mock_session):
        await ingester._process_house_roll(2024, 1, SAMPLE_QUORUM_ROLL, "us-118")
        assert ingester.metrics["skipped_out_of_scope"] == 1
        assert ingester.metrics["events_created"] == 0
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_unresolved_bill_skipped(self, ingester, mock_session):
        ingester._bill_ids = frozenset()  # bill not in DB
        await ingester._process_house_roll(2024, 517, SAMPLE_HOUSE_ROLL, "us-118")
        assert ingester.metrics["skipped_unresolved_bill"] == 1
        assert ingester.metrics["events_created"] == 0
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_dropped_member_still_reconciles(self, ingester, mock_session):
        """Dropping an unresolved member keeps the event (official counts authoritative)
        because reconcile buckets the drop by its parsed option."""
        ingester._member_map.pop("D000004")  # the 'Not Voting' member becomes unresolved
        await ingester._process_house_roll(2024, 517, SAMPLE_HOUSE_ROLL, "us-118")
        assert ingester.metrics["events_created"] == 1
        assert ingester.metrics["records_created"] == 3
        assert ingester.metrics["members_dropped"] == 1
        assert "D000004" in ingester._unresolved_bios


SAMPLE_SENATE_VOTE = """<?xml version="1.0" encoding="UTF-8"?>
<roll_call_vote>
<congress>118</congress>
<session>2</session>
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


class TestSenate:
    def test_resolve_senate_member(self, ingester):
        ingester._lis2bio = {"S354": "B001230"}
        ingester._member_map = {"B001230": "B001230"}
        assert ingester._resolve_senate_member("S354") == "B001230"
        assert ingester._resolve_senate_member("S999") is None  # lis not in crosswalk
        ingester._lis2bio["S001"] = "B999999"  # bioguide not in people
        assert ingester._resolve_senate_member("S001") is None

    @pytest.mark.asyncio
    async def test_process_senate_vote_happy_path(self, ingester, mock_session):
        ingester._lis2bio = {
            "S354": "B001230",
            "S001": "B000001",
            "S002": "B000002",
            "S003": "B000003",
        }
        ingester._member_map = {b: b for b in ["B001230", "B000001", "B000002", "B000003"]}
        ingester._bill_ids = frozenset({BILL_ID})  # H.R. 10545 resolves to the same bill id
        await ingester._process_senate_vote(2, 339, SAMPLE_SENATE_VOTE, "us-118")
        assert ingester.metrics["events_created"] == 1
        assert ingester.metrics["records_created"] == 4
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_process_senate_nomination_skipped(self, ingester, mock_session):
        nom = SAMPLE_SENATE_VOTE.replace(
            "<document_name>H.R. 10545</document_name>", "<document_name>PN1020</document_name>"
        )
        await ingester._process_senate_vote(2, 1, nom, "us-118")
        assert ingester.metrics["skipped_out_of_scope"] == 1
        assert ingester.metrics["events_created"] == 0
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_senate_menu_retries_on_throttle(self, ingester):
        """A throttled (non-200) menu response must be retried, not silently dropped."""
        menu = (
            "<vote_summary><votes>"
            "<vote><vote_number>00339</vote_number></vote>"
            "<vote><vote_number>00338</vote_number></vote>"
            "</votes></vote_summary>"
        )
        throttled = MagicMock(status_code=503)
        ok = MagicMock(status_code=200)
        ok.text = menu
        with (
            patch.object(ingester.client, "get", new_callable=AsyncMock) as mock_get,
            patch("src.ingestion.votes.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_get.side_effect = [throttled, ok]
            nums = await ingester._senate_vote_numbers(2)
        assert nums == [338, 339]
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_close(ingester):
    ingester.client.aclose = AsyncMock()
    await ingester.close()
    ingester.client.aclose.assert_called_once()
