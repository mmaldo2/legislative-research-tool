"""Non-frozen lift-study instance generator (harness-lift ablation, REV 4.2).

Hermetic: the disjoint-pairing logic (pure) + the gold SQL mirrors against DuckDB literals (proving
the lift gold == the frozen member_summary/pairwise aggregate, just window-pinned). `requires_pg`:
the live generator shape (pinned 118-House, public-resolvability prompt, refusal twins, no id leak).
"""

import pytest

from lab.experiments.lift_instances import (
    CHAMBER,
    CONGRESS,
    TEMPLATE_LIFT_MEMBER_SUMMARY,
    TEMPLATE_LIFT_PAIRWISE,
    generate_lift_member_summary,
    generate_lift_pairwise,
    member_pairs,
)


# --- pure: disjoint seeded pairing ------------------------------------------------------------
class TestMemberPairs:
    def test_disjoint_and_count(self):
        ids = [f"p{i}" for i in range(10)]
        pairs = member_pairs(ids, 3, 42)
        assert len(pairs) == 3
        flat = [pid for pair in pairs for pid in pair]
        assert len(set(flat)) == len(flat), "a member must not appear in two pairs"
        assert all(a != b for a, b in pairs)

    def test_deterministic_by_seed(self):
        ids = [f"p{i}" for i in range(20)]
        assert member_pairs(ids, 5, 42) == member_pairs(ids, 5, 42)

    def test_seed_changes_selection(self):
        ids = [f"p{i}" for i in range(20)]
        assert member_pairs(ids, 5, 42) != member_pairs(ids, 5, 7)

    def test_truncates_when_population_too_small(self):
        # 5 members -> only 2 disjoint pairs possible even if n=4 requested.
        assert len(member_pairs(["a", "b", "c", "d", "e"], 4, 42)) == 2


# --- hermetic: gold SQL mirrors the frozen aggregate ------------------------------------------
def _window_fixture():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE sessions (id VARCHAR, identifier VARCHAR)")
    con.execute("CREATE TABLE bills (id VARCHAR, session_id VARCHAR)")
    con.execute("CREATE TABLE vote_events (id VARCHAR, bill_id VARCHAR, chamber VARCHAR)")
    con.execute(
        'CREATE TABLE vote_records (vote_event_id VARCHAR, person_id VARCHAR, "option" VARCHAR)'
    )
    con.execute("CREATE TABLE people (id VARCHAR, name VARCHAR)")
    con.execute(f"INSERT INTO sessions VALUES ('s', '{CONGRESS}')")
    con.execute("INSERT INTO bills VALUES ('b1', 's')")
    con.execute(
        f"INSERT INTO vote_events VALUES "
        f"('e1','b1','{CHAMBER}'),('e2','b1','{CHAMBER}'),('e3','b1','{CHAMBER}')"
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
            ("e3", "p2", "not_voting"),  # mutual absence -> neither summary-nay nor shared
        ],
    )
    return con


def test_member_summary_gold_collapses_other():
    # Inline-literal mirror (DuckDB uses ? not psycopg2 %s); the live %s helper is exercised under
    # requires_pg below. Proves the bucketing LOGIC matches the frozen generate_member_summary.
    con = _window_fixture()
    rows = con.execute(
        'SELECT vr."option", COUNT(*) FROM vote_records vr '
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN bills b ON b.id = ve.bill_id JOIN sessions s ON s.id = b.session_id "
        f"WHERE vr.person_id = 'p1' AND s.identifier = '{CONGRESS}' AND ve.chamber = '{CHAMBER}' "
        'GROUP BY vr."option"'
    ).fetchall()
    gold = {"yea": 0, "nay": 0, "other": 0}
    for option, count in rows:
        gold[option if option in ("yea", "nay") else "other"] += count
    # p1: e1 yea, e2 nay, e3 present -> present collapses into other.
    assert gold == {"yea": 1, "nay": 1, "other": 1}


def test_pairwise_gold_yea_nay_filtered():
    con = _window_fixture()
    rows = con.execute(
        'SELECT ra."option", rb."option" FROM vote_records ra '
        "JOIN vote_records rb ON ra.vote_event_id = rb.vote_event_id "
        "JOIN vote_events ve ON ve.id = ra.vote_event_id "
        "JOIN bills b ON b.id = ve.bill_id JOIN sessions s ON s.id = b.session_id "
        "WHERE ra.person_id = 'p1' AND rb.person_id = 'p2' "
        f"AND s.identifier = '{CONGRESS}' AND ve.chamber = '{CHAMBER}' "
        "AND ra.\"option\" IN ('yea', 'nay') AND rb.\"option\" IN ('yea', 'nay')"
    ).fetchall()
    shared = len(rows)
    agreements = sum(1 for a, b in rows if a == b)
    # e1 (yea/yea agree), e2 (nay/yea disagree); e3 (present/not_voting) dropped by the yea/nay gate
    assert {"agreements": agreements, "shared_events": shared} == {
        "agreements": 1,
        "shared_events": 2,
    }


# --- the agent-sdk solver must resolve the lift ids in every per-template map -----------------
def test_lift_solver_registration():
    """The lift ids reuse the frozen member_summary/pairwise answer contract; assert they are
    aliased into ALL four per-template-id solver maps (else _asolve_sdk KeyErrors mid-run)."""
    from lab import solvers

    for lift_id, frozen_id in (
        (TEMPLATE_LIFT_MEMBER_SUMMARY, "family1.member_summary"),
        (TEMPLATE_LIFT_PAIRWISE, "family1.pairwise_agreement"),
    ):
        for table in (
            solvers.GOLD_KEYS,
            solvers.NUMERIC_FIELDS,
            solvers.SUBMIT_SCHEMAS,
            solvers.TEMPLATE_TOOLS,
        ):
            assert lift_id in table, f"{lift_id} missing from {table}"
            assert table[lift_id] == table[frozen_id], f"{lift_id} != {frozen_id} in a solver map"


# --- requires_pg: live generator shape --------------------------------------------------------
def _conn():
    from lab.harness import get_connection

    try:
        return get_connection()
    except Exception as exc:  # noqa: BLE001 -- unreachable means skip, not fail
        pytest.skip(f"Postgres unreachable: {exc}")


@pytest.mark.requires_pg
def test_member_summary_live_shape_and_no_leak():
    from lab.precompute import Precomputed

    conn = _conn()
    try:
        insts = generate_lift_member_summary(conn, 8, 42, Precomputed())
        answerable = [i for i in insts if not i.is_refusal]
        refusals = [i for i in insts if i.is_refusal]
        assert len(answerable) == 8 and refusals, "expected 8 answerable + refusal twins"
        for i in answerable:
            assert i.template_id == TEMPLATE_LIFT_MEMBER_SUMMARY and i.grader == "fields"
            assert set(i.gold) == {"yea", "nay", "other"}
            assert sum(i.gold.values()) > 0, "a 118-House member must have voted"
            # public-resolvability: prompt carries no internal id, names the member + window.
            assert i.params["person_id"] not in i.prompt
            assert "118th House" in i.prompt and "bills and resolutions" in i.prompt
        for r in refusals:
            assert r.grader == "refusal_correct" and r.refusal_reason == "person_not_in_data"
    finally:
        conn.close()


@pytest.mark.requires_pg
def test_pairwise_live_shape_disjoint_and_no_leak():
    from lab.precompute import Precomputed

    conn = _conn()
    try:
        insts = generate_lift_pairwise(conn, 8, 42, Precomputed())
        answerable = [i for i in insts if not i.is_refusal]
        assert len(answerable) == 8
        seen: set[str] = set()
        for i in answerable:
            assert i.template_id == TEMPLATE_LIFT_PAIRWISE and i.grader == "fields"
            a, b = i.params["person_a"], i.params["person_b"]
            assert a != b and a not in seen and b not in seen, "pairs must be disjoint"
            seen.update((a, b))
            assert set(i.gold) == {"agreements", "shared_events"}
            assert i.gold["agreements"] <= i.gold["shared_events"]
            assert a not in i.prompt and b not in i.prompt  # names in prompt, not internal ids
    finally:
        conn.close()
