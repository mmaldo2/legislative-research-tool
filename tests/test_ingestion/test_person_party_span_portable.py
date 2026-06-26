"""Portability smoke test: the half-open as-of-date party resolution runs on DuckDB.

Proves the `start_date <= vote_date < end_date` join (the production resolution 3b will wrap) is
engine-portable, including the boundary-day case — a switch-day vote resolves to exactly the LATER
party, never two. No lab/ coupling; the full lab fixture + drift-manifest entry land in 3b.
"""

import pytest


def test_half_open_party_resolution_portable():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE person_party_spans "
        "(person_id VARCHAR, party VARCHAR, start_date DATE, end_date DATE)"
    )
    con.execute("CREATE TABLE vote_events (id VARCHAR, vote_date DATE)")
    con.execute("CREATE TABLE vote_records (vote_event_id VARCHAR, person_id VARCHAR)")
    # Specter-shaped switcher (half-open, SHARED boundary 2009-04-30) + a single-span member.
    con.execute(
        "INSERT INTO person_party_spans VALUES "
        "('S000709','R',DATE '2005-01-04',DATE '2009-04-30'),"  # [start, 04-30)
        "('S000709','D',DATE '2009-04-30',DATE '2011-01-04'),"  # [04-30, end)
        "('X1','D',DATE '2007-01-04',DATE '2009-01-04')"
    )
    con.execute(
        "INSERT INTO vote_events VALUES "
        "('e_pre',DATE '2009-04-28'),('e_bound',DATE '2009-04-30'),"
        "('e_post',DATE '2010-06-01'),('e_x',DATE '2008-06-01')"
    )
    con.execute(
        "INSERT INTO vote_records VALUES "
        "('e_pre','S000709'),('e_bound','S000709'),('e_post','S000709'),('e_x','X1')"
    )
    rows = con.execute(
        "SELECT vr.vote_event_id, pps.party "
        "FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN person_party_spans pps ON pps.person_id = vr.person_id "
        "AND ve.vote_date >= pps.start_date AND ve.vote_date < pps.end_date "
        "ORDER BY vr.vote_event_id"
    ).fetchall()

    # exactly one row per (voter, event) — the boundary-day vote does NOT double-resolve.
    assert len(rows) == 4
    assert dict(rows) == {"e_bound": "D", "e_post": "D", "e_pre": "R", "e_x": "D"}
