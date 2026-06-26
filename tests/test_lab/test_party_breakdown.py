"""party_breakdown (#4) gold + the party-eligibility gate, on one DuckDB fixture.

Proves, against hand literals:
  - vote-time attribution: a SWITCHER (R before 2009-04-30, D after) is counted by their party
    AS OF the event date, NOT their latest party — a naive "current party" join would miscount;
  - the eligibility gate `_party_eligible_events` excludes an event with a voter mapping to NO span
    (omission) AND an event with a voter mapping to TWO spans (overlap double-count) — `COUNT <> 1`.
"""

import pytest

from lab.precompute import Precomputed
from lab.templates import _party_eligible_events


def _fixture():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE sessions (id VARCHAR, identifier VARCHAR, end_date DATE)")
    con.execute("CREATE TABLE bills (id VARCHAR, session_id VARCHAR)")
    con.execute(
        "CREATE TABLE vote_events "
        "(id VARCHAR, bill_id VARCHAR, vote_date DATE, motion_text VARCHAR)"
    )
    con.execute(
        'CREATE TABLE vote_records (vote_event_id VARCHAR, person_id VARCHAR, "option" VARCHAR)'
    )
    con.execute(
        "CREATE TABLE person_party_spans "
        "(id INTEGER, person_id VARCHAR, party VARCHAR, start_date DATE, end_date DATE)"
    )
    con.execute("INSERT INTO sessions VALUES ('s118', '118', DATE '2025-01-03')")  # completed
    con.execute("INSERT INTO bills VALUES ('b1', 's118')")
    con.execute(
        "INSERT INTO vote_events VALUES "
        "('e_pre','b1',DATE '2008-06-01','Pre-switch vote'),"  # before p1's switch
        "('e_ok','b1',DATE '2020-06-01','Clean vote'),"
        "('e_unres','b1',DATE '2020-06-01','Has an unresolvable voter'),"
        "('e_overlap','b1',DATE '2020-06-01','Has an overlap voter')"
    )
    # half-open spans. p1 is the SWITCHER: R until 2009-04-30, D after (latest = D).
    con.execute(
        "INSERT INTO person_party_spans VALUES "
        "(1,'p1','R',DATE '2005-01-01',DATE '2009-04-30'),"
        "(2,'p1','D',DATE '2009-04-30',DATE '2030-01-01'),"
        "(3,'p2','D',DATE '2005-01-01',DATE '2030-01-01'),"
        "(4,'p3','R',DATE '2005-01-01',DATE '2030-01-01'),"
        "(5,'p4','D',DATE '2005-01-01',DATE '2006-01-01'),"  # does NOT cover 2020 -> omission
        "(6,'p5','D',DATE '2005-01-01',DATE '2025-01-01'),"  # covers 2020
        "(7,'p5','R',DATE '2019-01-01',DATE '2030-01-01')"  # ALSO covers 2020 -> overlap
    )
    con.executemany(
        "INSERT INTO vote_records VALUES (?, ?, ?)",
        [
            ("e_pre", "p1", "yea"),
            ("e_pre", "p3", "yea"),
            ("e_pre", "p2", "nay"),
            ("e_ok", "p1", "yea"),
            ("e_ok", "p2", "yea"),
            ("e_ok", "p3", "nay"),
            ("e_unres", "p1", "yea"),
            ("e_unres", "p2", "yea"),
            ("e_unres", "p4", "nay"),
            ("e_overlap", "p1", "yea"),
            ("e_overlap", "p2", "yea"),
            ("e_overlap", "p5", "nay"),
        ],
    )
    return con


def test_party_breakdown_gold_uses_vote_time_party():
    con = _fixture()
    # mirrors generate_party_breakdown's per-event gold query exactly (literal event id).
    rows = con.execute(
        'SELECT pps.party, vr."option", COUNT(*) '
        "FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN person_party_spans pps ON pps.person_id = vr.person_id "
        "AND ve.vote_date >= pps.start_date AND ve.vote_date < pps.end_date "
        "WHERE vr.vote_event_id = 'e_pre' AND vr.\"option\" IN ('yea', 'nay') "
        'GROUP BY pps.party, vr."option"'
    ).fetchall()
    by_party: dict[str, dict[str, int]] = {}
    for party, option, count in rows:
        by_party.setdefault(party, {"yea": 0, "nay": 0})[option] += count
    # On 2008-06-01, p1 is REPUBLICAN (pre-switch). A naive latest-party join puts p1 in D
    # (R={yea:1}); vote-time attribution gives R={yea:2} (p1 + p3).
    assert by_party["R"] == {"yea": 2, "nay": 0}
    assert by_party["D"] == {"yea": 0, "nay": 1}  # p2 only


def test_party_eligible_gate_excludes_omission_and_overlap():
    con = _fixture()
    pre = Precomputed(
        complete_events=frozenset({"e_pre", "e_ok", "e_unres", "e_overlap"}),
    )
    eligible = _party_eligible_events(con, pre)
    # e_unres dropped (p4 -> 0 spans), e_overlap dropped (p5 -> 2 spans); clean events kept.
    assert eligible == frozenset({"e_pre", "e_ok"})
