"""Family 10 cite_record_id — the two integrity-critical properties that have no analog in the
existing suite (the coerce/answer-spec is auto-covered by the TEMPLATE_REGISTRY loop):

  - gold UNIQUENESS: each answerable gold is a singleton = the member's REAL vote on a bill with
    exactly one roll-call (so the citation is unambiguous);
  - no-link AIRTIGHTNESS: each no-link twin's X truly has 0 votes on bill Y, is structurally
    disjoint (0 votes in Y's congress), is a real active voter — a false no-link corrupts the eval.

`requires_pg` (skips when Postgres is unreachable). plain `def` is fine — no solver loop here.
"""

import pytest

from lab.graders import REFUSAL
from lab.templates import TEMPLATE_CITE, generate_cite_record_id


def _conn():
    from lab.harness import get_connection

    try:
        return get_connection()
    except Exception as exc:  # noqa: BLE001 — unreachable means skip, not fail
        pytest.skip(f"Postgres unreachable: {exc}")


@pytest.mark.requires_pg
def test_answerable_gold_is_unique_real_and_leak_free():
    from lab.precompute import precompute

    conn = _conn()
    try:
        insts = generate_cite_record_id(conn, 10, 42, precompute(conn))
        answerable = [i for i in insts if not i.is_refusal]
        assert answerable, "no answerable cite instances generated"
        cur = conn.cursor()
        for i in answerable:
            assert i.template_id == TEMPLATE_CITE and i.grader == "set_match"
            gold = list(i.gold)
            assert len(gold) == 1, f"gold must be a singleton id set, got {i.gold!r}"
            eid, pid, bid = gold[0], i.params["person_id"], i.params["bill_id"]
            # the bill has EXACTLY ONE roll-call, and the gold event IS that roll-call
            cur.execute("SELECT COUNT(*) FROM vote_events WHERE bill_id = %s", (bid,))
            assert cur.fetchone()[0] == 1, "answerable bill must have exactly one roll-call"
            cur.execute("SELECT bill_id FROM vote_events WHERE id = %s", (eid,))
            assert cur.fetchone()[0] == bid, "gold event must belong to the prompted bill"
            # the member ACTUALLY voted on it (gold is a real record, not synthesized)
            cur.execute(
                "SELECT COUNT(*) FROM vote_records WHERE person_id = %s AND vote_event_id = %s",
                (pid, eid),
            )
            assert cur.fetchone()[0] == 1, "gold must be the member's real recorded vote"
            # leak-safe: the prompt names the member + bill but NEVER the answer id
            assert eid not in i.prompt, "prompt must not leak the gold vote_event_id"
    finally:
        conn.close()


@pytest.mark.requires_pg
def test_no_link_twins_are_airtight():
    from lab.precompute import precompute

    conn = _conn()
    try:
        insts = generate_cite_record_id(conn, 10, 42, precompute(conn))
        no_link = [i for i in insts if i.refusal_reason == "member_did_not_vote_on_bill"]
        assert no_link, "no no-link twins generated (the centerpiece must be sampled)"
        cur = conn.cursor()
        for i in no_link:
            assert i.gold == REFUSAL and i.grader == "refusal_correct" and i.is_refusal
            pid, bid = i.params["person_id"], i.params["bill_id"]
            # X has ZERO records on any of Y's roll-calls (the explicit no-link)
            cur.execute("SELECT id FROM vote_events WHERE bill_id = %s", (bid,))
            y_rcs = [r[0] for r in cur.fetchall()]
            assert y_rcs, "no-link bill must have roll-calls"
            placeholders = ",".join(["%s"] * len(y_rcs))
            cur.execute(
                f"SELECT COUNT(*) FROM vote_records WHERE person_id = %s "
                f"AND vote_event_id IN ({placeholders})",
                (pid, *y_rcs),
            )
            assert cur.fetchone()[0] == 0, "X must have no recorded vote on Y"
            # structurally disjoint: X never voted in Y's congress at all
            cur.execute(
                "SELECT s.identifier FROM bills b JOIN sessions s ON s.id = b.session_id "
                "WHERE b.id = %s",
                (bid,),
            )
            congress_y = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM vote_records vr "
                "JOIN vote_events ve ON ve.id = vr.vote_event_id "
                "JOIN bills b ON b.id = ve.bill_id "
                "JOIN sessions s ON s.id = b.session_id "
                "WHERE vr.person_id = %s AND s.identifier = %s",
                (pid, congress_y),
            )
            assert cur.fetchone()[0] == 0, "X must be structurally disjoint from Y's congress"
            # X is a REAL active voter (not a phantom / nonexistent member)
            cur.execute("SELECT COUNT(*) FROM vote_records WHERE person_id = %s", (pid,))
            assert cur.fetchone()[0] > 0, "no-link X must be a real active voter"
    finally:
        conn.close()
