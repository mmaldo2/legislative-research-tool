"""member_summary (#6) + pairwise_agreement (#7) gold + the all-or-nothing window gate.

DuckDB fixtures prove engine portability + absolute correctness against hand literals:
  - member_summary: {yea, nay, other} with present+not_voting collapsed into `other`;
  - pairwise: shared_events + agreements restricted to events where BOTH cast yea/nay
    (a mutual present/not_voting is neither shared nor an agreement);
  - _fully_complete_windows: a window with even ONE non-complete event is excluded (all-or-nothing).
"""

import pytest

from lab.precompute import Precomputed
from lab.templates import _fully_complete_windows


def _window_fixture():
    """One congress (110), two chambers, with vote_records for two members in the house window."""
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE sessions (id VARCHAR, identifier VARCHAR)")
    con.execute("CREATE TABLE bills (id VARCHAR, session_id VARCHAR)")
    con.execute("CREATE TABLE vote_events (id VARCHAR, bill_id VARCHAR, chamber VARCHAR)")
    con.execute(
        'CREATE TABLE vote_records (vote_event_id VARCHAR, person_id VARCHAR, "option" VARCHAR)'
    )
    con.execute("CREATE TABLE people (id VARCHAR, name VARCHAR)")
    con.execute("INSERT INTO sessions VALUES ('s110', '110')")
    con.execute("INSERT INTO bills VALUES ('b1', 's110')")
    con.execute(
        "INSERT INTO vote_events VALUES ('e1','b1','house'),('e2','b1','house'),('e3','b1','house')"
    )
    con.execute("INSERT INTO people VALUES ('p1','Rep. A'),('p2','Rep. B')")
    con.executemany(
        "INSERT INTO vote_records VALUES (?, ?, ?)",
        [
            ("e1", "p1", "yea"),
            ("e1", "p2", "yea"),  # both yea -> shared + agree
            ("e2", "p1", "nay"),
            ("e2", "p2", "yea"),  # both yea/nay -> shared, disagree
            ("e3", "p1", "present"),
            ("e3", "p2", "not_voting"),  # mutual absence -> not counted
        ],
    )
    return con


def test_member_summary_gold_yea_nay_other():
    con = _window_fixture()
    rows = con.execute(
        'SELECT vr."option", COUNT(*) '
        "FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN bills b ON b.id = ve.bill_id "
        "JOIN sessions s ON s.id = b.session_id "
        "WHERE vr.person_id = 'p1' AND s.identifier = '110' AND ve.chamber = 'house' "
        'GROUP BY vr."option"'
    ).fetchall()
    gold = {"yea": 0, "nay": 0, "other": 0}
    for option, count in rows:
        key = option if option in ("yea", "nay") else "other"
        gold[key] += count
    # p1: e1 yea, e2 nay, e3 present -> present collapses into other
    assert gold == {"yea": 1, "nay": 1, "other": 1}


def test_pairwise_gold_yea_nay_filtered():
    con = _window_fixture()
    rows = con.execute(
        'SELECT ra."option", rb."option" '
        "FROM vote_records ra "
        "JOIN vote_records rb ON ra.vote_event_id = rb.vote_event_id "
        "JOIN vote_events ve ON ve.id = ra.vote_event_id "
        "JOIN bills b ON b.id = ve.bill_id "
        "JOIN sessions s ON s.id = b.session_id "
        "WHERE ra.person_id = 'p1' AND rb.person_id = 'p2' "
        "AND s.identifier = '110' AND ve.chamber = 'house' "
        "AND ra.\"option\" IN ('yea', 'nay') AND rb.\"option\" IN ('yea', 'nay')"
    ).fetchall()
    shared = len(rows)
    agreements = sum(1 for a, b in rows if a == b)
    # e1 (yea/yea agree), e2 (nay/yea disagree); e3 (present/not_voting) excluded by the filter
    assert {"agreements": agreements, "shared_events": shared} == {
        "agreements": 1,
        "shared_events": 2,
    }


def test_fully_complete_windows_all_or_nothing():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE sessions (id VARCHAR, identifier VARCHAR)")
    con.execute("CREATE TABLE bills (id VARCHAR, session_id VARCHAR)")
    con.execute("CREATE TABLE vote_events (id VARCHAR, bill_id VARCHAR, chamber VARCHAR)")
    con.execute("INSERT INTO sessions VALUES ('s110', '110')")
    con.execute("INSERT INTO bills VALUES ('b1', 's110')")
    con.execute(
        "INSERT INTO vote_events VALUES "
        "('e1','b1','house'),('e2','b1','house'),"  # house: both complete -> window kept
        "('e3','b1','senate'),('e4','b1','senate')"  # senate: e4 not complete -> window dropped
    )
    pre = Precomputed(
        completed_congresses=frozenset({"110"}),
        complete_events=frozenset({"e1", "e2", "e3"}),  # e4 missing -> senate incomplete
    )
    assert _fully_complete_windows(con, pre) == [("110", "house")]
