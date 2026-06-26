"""Behavioral truth layer: run the vote_lookup gold JOIN on a controlled DuckDB fixture and
assert the recorded option (the gold) against hand-authored literals. Proves the JOIN is
engine-portable AND correct on a known input (PG and DuckDB could otherwise agree on a wrong
answer). The query mirrors lab/templates.generate's answerable JOIN exactly (incl. `vr.option`)."""

import pytest


def test_vote_lookup_join_portable_and_correct():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE vote_events (id VARCHAR, motion_text VARCHAR)")
    con.execute(
        'CREATE TABLE vote_records (vote_event_id VARCHAR, person_id VARCHAR, "option" VARCHAR)'
    )
    con.execute("CREATE TABLE people (id VARCHAR, name VARCHAR)")
    con.execute("INSERT INTO vote_events VALUES ('e1', 'On Passage of the Bill')")
    con.execute("INSERT INTO people VALUES ('p1', 'Rep. A'), ('p2', 'Rep. B')")
    con.execute("INSERT INTO vote_records VALUES ('e1','p1','yea'), ('e1','p2','nay')")

    # Mirrors templates.generate's answerable JOIN (paramstyle-neutral: literal event id).
    rows = con.execute(
        "SELECT vr.vote_event_id, vr.person_id, vr.option, p.name, ve.motion_text "
        "FROM vote_records vr "
        "JOIN people p ON p.id = vr.person_id "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "WHERE vr.vote_event_id = 'e1'"
    ).fetchall()

    gold_by_person = {person_id: option for (_eid, person_id, option, _name, _motion) in rows}
    assert gold_by_person == {"p1": "yea", "p2": "nay"}
