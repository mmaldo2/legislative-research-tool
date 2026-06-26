"""closest_by_margin (Template #8) gold: portable + correct on a DuckDB fixture.

Exercises the three correctness properties of the window ranking:
  - window filter: only the queried (congress, chamber)'s events count (senate excluded);
  - NULL guard:    NULL-count events are unrankable and excluded;
  - tie-determinism: ranking by the total order (margin ASC, id ASC) yields a UNIQUE K-set even
    when margins tie at the boundary (e5 in, e6 out by id) — mirrors generate_closest_by_margin.
"""

import pytest

from lab.templates import CLOSEST_K


def test_closest_by_margin_gold_portable_and_correct():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE sessions (id VARCHAR, identifier VARCHAR)")
    con.execute("CREATE TABLE bills (id VARCHAR, session_id VARCHAR)")
    con.execute(
        "CREATE TABLE vote_events (id VARCHAR, bill_id VARCHAR, chamber VARCHAR, "
        "yes_count INTEGER, no_count INTEGER)"
    )
    con.execute("INSERT INTO sessions VALUES ('s110', '110')")
    con.execute("INSERT INTO bills VALUES ('b1', 's110')")
    # house window: margins 1,2,3,4,5,5,100 + a NULL-count event + one senate event.
    con.execute(
        "INSERT INTO vote_events VALUES "
        "('e1','b1','house',10,9),"  # margin 1
        "('e2','b1','house',10,8),"  # margin 2
        "('e3','b1','house',10,7),"  # margin 3
        "('e4','b1','house',20,16),"  # margin 4
        "('e5','b1','house',5,0),"  # margin 5  <- boundary, kept (smaller id)
        "('e6','b1','house',5,0),"  # margin 5  <- boundary, dropped (larger id)
        "('e7','b1','house',100,0),"  # margin 100
        "('eN','b1','house',NULL,3),"  # NULL count -> unrankable, excluded
        "('sX','b1','senate',1,0)"  # senate -> different window, excluded
    )

    rows = con.execute(
        "SELECT ve.id, ve.yes_count, ve.no_count "
        "FROM vote_events ve "
        "JOIN bills b ON b.id = ve.bill_id "
        "JOIN sessions s ON s.id = b.session_id "
        "WHERE s.identifier = '110' AND ve.chamber = 'house' "
        "AND ve.yes_count IS NOT NULL AND ve.no_count IS NOT NULL"
    ).fetchall()

    ranked = sorted((abs(yes - no), eid) for (eid, yes, no) in rows)
    gold = {eid for (_margin, eid) in ranked[:CLOSEST_K]}

    # e6 dropped by the (margin, id) tiebreak; eN (null) and sX (senate) never in the window.
    assert gold == {"e1", "e2", "e3", "e4", "e5"}
