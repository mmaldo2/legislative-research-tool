"""FROZEN Family 1 templates — gold computed by trusted, engine-portable SQL.

Phase 0 ships Template #1 (vote lookup). Gold is read directly from `vote_records`
(the canonical store), never hand-authored. The #1 trust-floor dichotomy:
  - answerable: a (member, event) pair that EXISTS in vote_records -> gold = the recorded option
  - refusal:    a member with NO vote_records anywhere -> gold = REFUSAL ("not in the data")
We do NOT claim an eligible/ineligible distinction (the schema can't support it).
"""

from lab.generate import pick_one, sample
from lab.graders import REFUSAL
from lab.harness import Instance

TEMPLATE_VOTE_LOOKUP = "family1.vote_lookup"


def _in_clause(n: int) -> str:
    """Portable IN-list placeholders (avoids Postgres-only `= ANY(array)`)."""
    return ",".join(["%s"] * n)


def generate(conn, n: int, seed: int, precomputed) -> list[Instance]:
    """Generate ~n answerable + a proportional refusal set for Template #1.

    `precomputed` is accepted for the frozen run-loop signature but unused here: a single
    member's recorded option is unambiguous even on an overcounted event, so vote_lookup
    consults neither the overcount nor the completed-congress sets.
    """
    cur = conn.cursor()
    instances: list[Instance] = []

    # --- answerable: sample events, then one deterministic voter per event ---
    cur.execute("SELECT id FROM vote_events")
    event_ids = [r[0] for r in cur.fetchall()]
    chosen = sample(event_ids, n, seed)
    if chosen:
        cur.execute(
            f"SELECT vr.vote_event_id, vr.person_id, vr.option, p.name, ve.motion_text "
            f"FROM vote_records vr "
            f"JOIN people p ON p.id = vr.person_id "
            f"JOIN vote_events ve ON ve.id = vr.vote_event_id "
            f"WHERE vr.vote_event_id IN ({_in_clause(len(chosen))})",
            chosen,
        )
        by_event: dict[str, list[tuple[str, str, str]]] = {}
        motion: dict[str, str | None] = {}
        for eid, pid, option, name, motion_text in cur.fetchall():
            by_event.setdefault(eid, []).append((pid, option, name))
            motion[eid] = motion_text
        for eid in chosen:
            rows = by_event.get(eid)
            if not rows:
                continue
            pid = pick_one([r[0] for r in rows], seed)
            option, name = next((o, nm) for p, o, nm in rows if p == pid)
            instances.append(
                Instance(
                    instance_id=f"{TEMPLATE_VOTE_LOOKUP}:{seed}:{eid}:{pid}",
                    template_id=TEMPLATE_VOTE_LOOKUP,
                    tier="C",
                    params={"person_id": pid, "vote_event_id": eid},
                    prompt=f"How did {name} vote on roll call {eid} "
                    f"({(motion.get(eid) or 'the recorded motion').strip()})?",
                    gold=option,
                    grader="exact",
                    is_refusal=False,
                )
            )

    # --- refusal: SYNTHETIC nonexistent members (provably absent) paired with a real event.
    # Unambiguous (a real non-voting member could be a duplicate-row of someone who did vote);
    # absence is the only valid basis for refusal gold, so we prove it before emitting.
    n_refusal = max(3, n // 4)
    synthetic = [f"NX-{seed}-{i:04d}" for i in range(n_refusal)]
    cur.execute(f"SELECT id FROM people WHERE id IN ({_in_clause(len(synthetic))})", synthetic)
    if cur.fetchall():
        raise AssertionError("synthetic refusal ids unexpectedly exist in people")
    if chosen:
        for i, pid in enumerate(synthetic):
            eid = chosen[i % len(chosen)]
            instances.append(
                Instance(
                    instance_id=f"{TEMPLATE_VOTE_LOOKUP}:{seed}:refusal:{eid}:{pid}",
                    template_id=TEMPLATE_VOTE_LOOKUP,
                    tier="C",
                    params={"person_id": pid, "vote_event_id": eid},
                    prompt=f"How did the member with id '{pid}' vote on roll call {eid}?",
                    gold=REFUSAL,
                    grader="refusal_correct",
                    is_refusal=True,
                    refusal_reason="person_not_in_data",
                )
            )
    return instances
