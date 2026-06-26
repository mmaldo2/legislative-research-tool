"""party_majority / party_defection / crossed_party (#5/#6) gold + eligibility, on one fixture.

Proves against hand literals:
  - party_majority = strict majority of yea+nay; tie/zero -> None (excluded, never a guessed side);
  - the defection/crossed eligibility (≥2 AND non-null majority) EXCLUDES a 2-2 tie that breakdown's
    tie-tolerant ≥2-only filter INCLUDES;
  - defection = min(yea,nay); crossed = the minority-side member set; |crossed| == defection;
  - VOTE-TIME attribution via a switcher (a current-party join would flip R 2-1 -> R 1-1 tie);
  - the WrongBaselineSolver bare-int arm (the first standalone exact_int gold).
"""

import pytest

from lab.harness import Instance
from lab.solvers import WrongBaselineSolver
from lab.templates import _eligible_party_sides, _party_majority_side


class TestPartyMajoritySide:
    def test_strict_majority(self):
        assert _party_majority_side(2, 1) == "yea"
        assert _party_majority_side(1, 2) == "nay"

    def test_tie_and_zero_are_null(self):
        assert _party_majority_side(3, 3) is None  # tie -> no majority
        assert _party_majority_side(0, 0) is None  # zero voters -> no majority


class TestEligiblePartySides:
    def test_excludes_ties_and_single_member(self):
        splits = {
            "R": {"yea": 2, "nay": 1},  # majority yea
            "D": {"yea": 2, "nay": 0},  # unanimous -> majority yea (defection 0 / crossed ∅)
            "I": {"yea": 1, "nay": 1},  # tie -> excluded
            "L": {"yea": 2, "nay": 2},  # tie -> excluded (breakdown WOULD include this)
            "X": {"yea": 1, "nay": 0},  # single member -> excluded by >=2
        }
        assert _eligible_party_sides(splits) == {"R": "yea", "D": "yea"}
        # breakdown's tie-tolerant >=2-only filter includes the ties (I, L) that defection excludes.
        breakdown_candidates = {p for p, c in splits.items() if c["yea"] + c["nay"] >= 2}
        assert breakdown_candidates == {"R", "D", "I", "L"}
        assert {"I", "L"} <= breakdown_candidates - set(_eligible_party_sides(splits))


def _fixture():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute(
        'CREATE TABLE vote_records (vote_event_id VARCHAR, person_id VARCHAR, "option" VARCHAR)'
    )
    con.execute("CREATE TABLE vote_events (id VARCHAR, vote_date DATE)")
    con.execute(
        "CREATE TABLE person_party_spans "
        "(id INTEGER, person_id VARCHAR, party VARCHAR, start_date DATE, end_date DATE)"
    )
    con.execute("INSERT INTO vote_events VALUES ('e1', DATE '2008-06-01')")  # pre-switch date
    # p1 is the SWITCHER: R until 2009-04-30, D after. On 2008 it must resolve to R.
    con.execute(
        "INSERT INTO person_party_spans VALUES "
        "(1,'p1','R',DATE '2005-01-01',DATE '2009-04-30'),"
        "(2,'p1','D',DATE '2009-04-30',DATE '2030-01-01'),"
        "(3,'p2','R',DATE '2005-01-01',DATE '2030-01-01'),"
        "(4,'p3','R',DATE '2005-01-01',DATE '2030-01-01'),"
        "(5,'p4','D',DATE '2005-01-01',DATE '2030-01-01'),"
        "(6,'p5','D',DATE '2005-01-01',DATE '2030-01-01'),"
        "(7,'p6','I',DATE '2005-01-01',DATE '2030-01-01'),"
        "(8,'p7','I',DATE '2005-01-01',DATE '2030-01-01'),"
        "(9,'p8','L',DATE '2005-01-01',DATE '2030-01-01'),"
        "(10,'p9','L',DATE '2005-01-01',DATE '2030-01-01'),"
        "(11,'p10','L',DATE '2005-01-01',DATE '2030-01-01'),"
        "(12,'p11','L',DATE '2005-01-01',DATE '2030-01-01')"
    )
    con.executemany(
        "INSERT INTO vote_records VALUES (?, ?, ?)",
        [
            ("e1", "p1", "yea"),
            ("e1", "p2", "yea"),
            ("e1", "p3", "nay"),  # R: 2-1
            ("e1", "p4", "yea"),
            ("e1", "p5", "yea"),  # D: 2-0
            ("e1", "p6", "yea"),
            ("e1", "p7", "nay"),  # I: 1-1 tie
            ("e1", "p8", "yea"),
            ("e1", "p9", "nay"),
            ("e1", "p10", "yea"),
            ("e1", "p11", "nay"),  # L: 2-2
        ],
    )
    return con


def test_defection_and_crossed_gold_vote_time():
    con = _fixture()
    # mirrors generate_crossed_party's ONE per-event query (literal event id).
    rows = con.execute(
        'SELECT pps.party, vr."option", vr.person_id '
        "FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN person_party_spans pps ON pps.person_id = vr.person_id "
        "AND ve.vote_date >= pps.start_date AND ve.vote_date < pps.end_date "
        "WHERE vr.vote_event_id = 'e1' AND vr.\"option\" IN ('yea', 'nay')"
    ).fetchall()
    splits: dict[str, dict[str, int]] = {}
    ids: dict[str, dict[str, list[str]]] = {}
    for party, option, pid in rows:
        splits.setdefault(party, {"yea": 0, "nay": 0})[option] += 1
        ids.setdefault(party, {"yea": [], "nay": []})[option].append(pid)

    # vote-time: p1 (switcher) counts as R on 2008 -> R is 2-1 (NOT a 1-1 tie under latest-party).
    assert splits["R"] == {"yea": 2, "nay": 1}
    eligible = _eligible_party_sides(splits)
    assert eligible == {"R": "yea", "D": "yea"}  # I (1-1) and L (2-2) excluded

    # defection = min(yea,nay); crossed = minority-side set; |crossed| == defection.
    for party in eligible:
        minority = "nay" if eligible[party] == "yea" else "yea"
        crossers = set(ids[party][minority])
        defection = min(splits[party]["yea"], splits[party]["nay"])
        assert len(crossers) == defection
    assert {"nay" if eligible["R"] == "yea" else "yea"} == {"nay"}
    assert set(ids["R"]["nay"]) == {"p3"}  # R crosser = p3
    assert min(splits["R"]["yea"], splits["R"]["nay"]) == 1  # R defection = 1
    assert set(ids["D"]["nay"]) == set()  # D unanimous -> crossed ∅, defection 0


def test_wrong_baseline_bare_int_arm():
    inst = Instance(
        instance_id="x",
        template_id="family1.party_defection",
        tier="C",
        params={},
        prompt="?",
        gold=3,
        grader="exact_int",
        is_refusal=False,
    )
    # bare-int gold must perturb to a different INT (not a non-int option), so it grades as
    # attempted-but-wrong, not malformed.
    assert WrongBaselineSolver().solve(inst) == 4
