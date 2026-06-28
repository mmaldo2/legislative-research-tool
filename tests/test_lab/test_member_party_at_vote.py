"""family9.member_party_at_vote — the integrity properties that have no analog elsewhere (the
coerce/fold/answer-spec is covered hermetically in test_answer_spec.py):

  - the SHARPENED ("switch-year") arena: every switcher (HARD) instance is a vote whose calendar
    year SPANS the member's switch (the eid leaks the year but NOT the day, so only a year-ambiguous
    vote is a clean moat) AND whose VOTE-TIME party != the member's current party (web's default is
    wrong); every control instance is a self-control (as-of == current, web's default is right);
  - gold is ALWAYS the exact-day as-of party, NEVER people.party (the web's wrong answer);
  - leak-safety: the prompt carries the member name (party-tag STRIPPED) + the eid, never a party.

Pure helpers are hermetic; the generation properties are `requires_pg` (skip when PG unreachable).
plain `def` is fine — no solver loop here.
"""

import pytest

from lab.solvers import SqlOracleSolver, WrongBaselineSolver
from lab.templates import (
    TEMPLATE_PARTY,
    _norm_current_party,
    _stratify,
    _strip_party_tag,
    generate_member_party_at_vote,
)

_PARTY_WORDS = ("democrat", "republican", "independent", "libertarian")


class TestPureHelpers:
    def test_strip_party_tag(self):
        assert _strip_party_tag("Rep. Amash, Justin [R-MI-3]") == "Rep. Amash, Justin"
        assert _strip_party_tag("Sen. Manchin, Joe, III [I-WV]") == "Sen. Manchin, Joe, III"
        assert _strip_party_tag("Sen. Specter, Arlen [D-PA]") == "Sen. Specter, Arlen"
        assert _strip_party_tag("No Tag Here") == "No Tag Here"  # idempotent on an untagged name

    def test_norm_current_party(self):
        assert _norm_current_party("ID") == "I"  # current-only Independent-Democrat code -> I
        for p in ("D", "I", "L", "R"):
            assert _norm_current_party(p) == p  # span vocab is unchanged

    def test_stratify_spreads_across_persons_before_deepening(self):
        # 3 persons, lopsided counts; n=3 must take ONE from each (no single person dominates).
        by_person = {"a": ["a1", "a2", "a3", "a4"], "b": ["b1"], "c": ["c1", "c2"]}
        picks = _stratify(by_person, 3, seed=42)
        assert {p for p, _e in picks} == {"a", "b", "c"}  # one per person first
        assert len(picks) == 3

    def test_stratify_deterministic_and_capped(self):
        by_person = {"a": ["a1", "a2"], "b": ["b1", "b2"]}
        assert _stratify(by_person, 3, 42) == _stratify(by_person, 3, 42)  # deterministic
        assert len(_stratify(by_person, 10, 42)) == 4  # capped at the candidate count
        assert _stratify({}, 5, 42) == []  # no candidates -> empty


def _conn():
    from lab.harness import get_connection

    try:
        return get_connection()
    except Exception as exc:  # noqa: BLE001 — unreachable means skip, not fail
        pytest.skip(f"Postgres unreachable: {exc}")


def _asof_party(cur, pid: str, eid: str) -> str | None:
    """The member's exact-day vote-time party for (person, event) via the same half-open as-of join
    the gold uses — the independent recomputation the test grades the gold against."""
    cur.execute(
        "SELECT MIN(pps.party) FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN person_party_spans pps ON pps.person_id = vr.person_id "
        "AND ve.vote_date >= pps.start_date AND ve.vote_date < pps.end_date "
        "WHERE vr.person_id = %s AND vr.vote_event_id = %s "
        "GROUP BY vr.person_id, vr.vote_event_id HAVING COUNT(DISTINCT pps.party) = 1",
        (pid, eid),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _current_party(cur, pid: str) -> str:
    cur.execute("SELECT party FROM people WHERE id = %s", (pid,))
    return cur.fetchone()[0]


def _year_spans_switch(cur, pid: str, eid: str) -> bool:
    """True iff the person had >1 distinct as-of party among their votes in this vote's calendar
    year (the eid's year is then INSUFFICIENT to resolve the party — the leak-defense grain)."""
    cur.execute(
        "SELECT COUNT(DISTINCT pps.party) FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN person_party_spans pps ON pps.person_id = vr.person_id "
        "AND ve.vote_date >= pps.start_date AND ve.vote_date < pps.end_date "
        "WHERE vr.person_id = %s AND ve.vote_date IS NOT NULL "
        "AND EXTRACT(YEAR FROM ve.vote_date) = ("
        "  SELECT EXTRACT(YEAR FROM vote_date) FROM vote_events WHERE id = %s)",
        (pid, eid),
    )
    return cur.fetchone()[0] > 1


@pytest.mark.requires_pg
def test_switcher_and_control_construction_is_clean():
    from lab.precompute import precompute

    conn = _conn()
    try:
        insts = generate_member_party_at_vote(conn, 8, 42, precompute(conn))
        assert insts, "no member_party_at_vote instances generated"
        switchers = [i for i in insts if i.params["kind"] == "switcher"]
        controls = [i for i in insts if i.params["kind"] == "control"]
        assert switchers and controls, "both kinds must be sampled"
        cur = conn.cursor()
        for i in insts:
            assert i.template_id == TEMPLATE_PARTY and i.grader == "set_match" and not i.is_refusal
            pid, eid = i.params["person_id"], i.params["vote_event_id"]
            gold = list(i.gold)
            assert len(gold) == 1, f"gold must be a singleton party set, got {i.gold!r}"
            asof = _asof_party(cur, pid, eid)
            assert gold[0] == asof, "gold must be the exact-day as-of party (never people.party)"
            current = _norm_current_party(_current_party(cur, pid))
            if i.params["kind"] == "switcher":
                # web's current default is WRONG, AND the year can't rescue it (switch-year)
                assert asof != current, "switcher gold must differ from current party"
                assert _year_spans_switch(cur, pid, eid), "switcher vote must be in a switch-year"
            else:
                assert asof == current, "control gold must equal current party (self-control)"
    finally:
        conn.close()


@pytest.mark.requires_pg
def test_prompts_are_leak_safe():
    from lab.precompute import precompute

    conn = _conn()
    try:
        insts = generate_member_party_at_vote(conn, 8, 42, precompute(conn))
        assert insts
        for i in insts:
            eid = i.params["vote_event_id"]
            assert eid in i.prompt, "prompt must name the eid (the lookup key)"
            assert "[" not in i.prompt, "prompt must not carry the [party-state] tag (current)"
            low = i.prompt.lower()
            for word in _PARTY_WORDS:
                assert word not in low, f"prompt leaks a party word: {word!r}"
    finally:
        conn.close()


@pytest.mark.requires_pg
def test_deterministic_invariants_oracle_and_wrong():
    from lab.graders import grade
    from lab.precompute import precompute

    conn = _conn()
    try:
        insts = generate_member_party_at_vote(conn, 8, 42, precompute(conn))
        assert insts
    finally:
        conn.close()
    oracle, wrong = SqlOracleSolver(), WrongBaselineSolver()
    for i in insts:
        assert grade(i.grader, i.gold, oracle.solve(i), is_refusal=i.is_refusal).passed
        assert not grade(i.grader, i.gold, wrong.solve(i), is_refusal=i.is_refusal).passed
