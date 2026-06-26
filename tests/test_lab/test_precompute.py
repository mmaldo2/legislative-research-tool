"""Hermetic precompute tests on a controlled DuckDB fixture (Layer 3 truth: the gold/eligibility
SQL runs on DuckDB and is asserted against HAND-AUTHORED literals — proving both engine
portability and absolute correctness on a known input).
"""

import pytest

from lab.precompute import Precomputed, _party_majority, precompute


def _fixture():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE vote_events (id VARCHAR, yes_count INT, no_count INT, other_count INT)"
    )
    con.execute('CREATE TABLE vote_records (vote_event_id VARCHAR, "option" VARCHAR)')
    con.execute("CREATE TABLE sessions (identifier VARCHAR, end_date DATE)")
    con.execute(
        "INSERT INTO vote_events VALUES "
        "('e_ok', 2, 1, 1),"  # resolved exactly matches stored -> kept
        "('e_under', 5, 5, 5),"  # resolved < stored (records are a subset) -> kept
        "('e_over', 1, 0, 0),"  # resolved yea=3 > stored 1 -> overcount
        "('e_null', NULL, 1, 1),"  # yes_count NULL -> missing_official_count
        "('e_over_and_null', NULL, 0, 0)"  # nay=2 > 0 (overcount) AND yes NULL -> overcount wins
    )
    records = (
        [("e_ok", "yea")] * 2
        + [("e_ok", "nay")]
        + [("e_ok", "present")]
        + [("e_under", "yea")]
        + [("e_over", "yea")] * 3
        + [("e_null", "nay")]
        + [("e_over_and_null", "nay")] * 2
    )  # total = 11
    con.executemany("INSERT INTO vote_records VALUES (?, ?)", records)
    con.execute("INSERT INTO sessions VALUES ('118', DATE '2025-01-03'), ('119', NULL)")
    return con


class TestOvercountClassification:
    def test_boundaries(self):
        pre = precompute(_fixture())
        # e_ok (==) and e_under (<) are NOT excluded; the explicit NULL arm + overcount-wins hold.
        assert pre.excluded_events == {
            "e_over": "overcount",
            "e_null": "missing_official_count",
            "e_over_and_null": "overcount",
        }


class TestCompleteEvents:
    def test_exact_reconciliation_and_strict_superset(self):
        pre = precompute(_fixture())
        # e_ok reconciles EXACTLY (yea2/nay1/other1 == stored 2/1/1) -> complete.
        assert pre.complete_events == frozenset({"e_ok"})
        # e_under is undercount (resolved 1/0/0 < stored 5/5/5): in NEITHER complete_events NOR
        # excluded_events — the strict-superset distinction ("not excluded" != "complete").
        assert "e_under" not in pre.complete_events
        assert "e_under" not in pre.excluded_events


class TestCompletedCongresses:
    def test_only_ended_sessions(self):
        pre = precompute(_fixture())
        assert pre.completed_congresses == frozenset({"118"})  # 119 has NULL end_date


class TestTotalVoteRecords:
    def test_derived_from_aggregate(self):
        pre = precompute(_fixture())
        assert pre.total_vote_records == 11


class TestPartyMajorityReserved:
    def test_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            _party_majority(None)


class TestEmptyDB:
    def test_empty_returns_empty_precomputed(self):
        duckdb = pytest.importorskip("duckdb")
        con = duckdb.connect()
        con.execute(
            "CREATE TABLE vote_events (id VARCHAR, yes_count INT, no_count INT, other_count INT)"
        )
        con.execute('CREATE TABLE vote_records (vote_event_id VARCHAR, "option" VARCHAR)')
        con.execute("CREATE TABLE sessions (identifier VARCHAR, end_date DATE)")
        pre = precompute(con)
        assert pre == Precomputed()
