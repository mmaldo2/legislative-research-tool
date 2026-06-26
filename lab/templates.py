"""FROZEN Family 1 templates — gold computed by trusted, engine-portable SQL.

Phase 0 ships Template #1 (vote lookup). Gold is read directly from `vote_records`
(the canonical store), never hand-authored. The #1 trust-floor dichotomy:
  - answerable: a (member, event) pair that EXISTS in vote_records -> gold = the recorded option
  - refusal:    a member with NO vote_records anywhere -> gold = REFUSAL ("not in the data")
We do NOT claim an eligible/ineligible distinction (the schema can't support it).
"""

from types import SimpleNamespace

from lab.generate import pick_one, sample
from lab.graders import REFUSAL
from lab.harness import Instance

TEMPLATE_VOTE_LOOKUP = "family1.vote_lookup"
TEMPLATE_TALLY = "family1.tally"
TEMPLATE_CLOSEST = "family1.closest_by_margin"
CLOSEST_K = 5  # how many "closest" roll calls a closest_by_margin instance asks for


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


def generate_tally(conn, n: int, seed: int, precomputed) -> list[Instance]:
    """Template #2 (tally): yea / nay / margin / result for one roll-call event.

    Group A — gold is read STRAIGHT FROM the canonical stored count columns on `vote_events`
    (`vote_records` are a resolved subset, so counting them could undercount; the official totals
    are authoritative and overcount-immune). The candidate pool excludes events with any NULL
    count or NULL result (a NULL gold would crash the margin and make the oracle fail itself) —
    the Group-A NULL guard, airtight even against an overcount event that also has a NULL bucket.
    `precomputed` is accepted for the frozen run-loop signature but unused here.
    """
    cur = conn.cursor()
    instances: list[Instance] = []

    # --- answerable: events with complete, non-NULL official tallies + result ---
    cur.execute(
        "SELECT id FROM vote_events "
        "WHERE yes_count IS NOT NULL AND no_count IS NOT NULL AND result IS NOT NULL"
    )
    event_ids = [r[0] for r in cur.fetchall()]
    chosen = sample(event_ids, n, seed)
    if chosen:
        cur.execute(
            "SELECT id, yes_count, no_count, result, motion_text "
            f"FROM vote_events WHERE id IN ({_in_clause(len(chosen))})",
            chosen,
        )
        rows = {r[0]: r for r in cur.fetchall()}
        for eid in chosen:
            row = rows.get(eid)
            if row is None:
                continue
            _id, yes_count, no_count, result, motion_text = row
            gold = {
                "yea": yes_count,
                "nay": no_count,
                "margin": yes_count - no_count,
                "result": result,
            }
            instances.append(
                Instance(
                    instance_id=f"{TEMPLATE_TALLY}:{seed}:{eid}",
                    template_id=TEMPLATE_TALLY,
                    tier="C",
                    params={"vote_event_id": eid},
                    prompt=f"On roll call {eid} "
                    f"({(motion_text or 'the recorded motion').strip()}), how many voted yea and "
                    f"how many nay, what was the margin (yea minus nay), and the result?",
                    gold=gold,
                    grader="fields",
                    is_refusal=False,
                )
            )

    # --- refusal: SYNTHETIC nonexistent event ids, proven absent before emit ---
    n_refusal = max(3, n // 4)
    synthetic = [f"NX-EVENT-{seed}-{i:04d}" for i in range(n_refusal)]
    cur.execute(f"SELECT id FROM vote_events WHERE id IN ({_in_clause(len(synthetic))})", synthetic)
    if cur.fetchall():
        raise AssertionError("synthetic refusal event ids unexpectedly exist in vote_events")
    for eid in synthetic:
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_TALLY}:{seed}:refusal:{eid}",
                template_id=TEMPLATE_TALLY,
                tier="C",
                params={"vote_event_id": eid},
                prompt=f"On roll call {eid}, how many voted yea and nay, and what was the result?",
                gold=REFUSAL,
                grader="refusal_correct",
                is_refusal=True,
                refusal_reason="event_not_in_data",
            )
        )
    return instances


def generate_closest_by_margin(conn, n: int, seed: int, precomputed) -> list[Instance]:
    """Template #8 (closest by margin): the K roll calls in a {congress, chamber} window with
    the smallest |yea - nay|.

    Group A — margins come from the canonical stored count columns (overcount-immune); NULL-count
    events are excluded (an unrankable NULL margin). The window is a single COMPLETED congress
    (point-in-time gate via `precomputed.completed_congresses` — the ongoing congress is excluded)
    scoped to one chamber. Gold is tie-DETERMINISTIC: events are ranked by the total order
    (margin ASC, id ASC), so the K-set is unique even when margins tie at the boundary; the prompt
    states the tie-break so the question is fully determinate. `grader = "set_match"` (the answer
    is *which* K, order-independent). Verified: every real window has >= ~123 rankable events, so K
    is always satisfiable; the `< K` arm (return all rankable) is defensive only.
    """
    cur = conn.cursor()
    instances: list[Instance] = []
    completed = precomputed.completed_congresses

    # candidate windows: (congress, chamber) with >=1 rankable event, gated to completed congresses.
    cur.execute(
        "SELECT DISTINCT s.identifier, ve.chamber "
        "FROM vote_events ve "
        "JOIN bills b ON b.id = ve.bill_id "
        "JOIN sessions s ON s.id = b.session_id "
        "WHERE ve.yes_count IS NOT NULL AND ve.no_count IS NOT NULL"
    )
    windows = {f"{c}:{ch}": (c, ch) for (c, ch) in cur.fetchall() if c in completed}
    for wid in sample(list(windows), n, seed):
        congress, chamber = windows[wid]
        cur.execute(
            "SELECT ve.id, ve.yes_count, ve.no_count "
            "FROM vote_events ve "
            "JOIN bills b ON b.id = ve.bill_id "
            "JOIN sessions s ON s.id = b.session_id "
            "WHERE s.identifier = %s AND ve.chamber = %s "
            "AND ve.yes_count IS NOT NULL AND ve.no_count IS NOT NULL",
            (congress, chamber),
        )
        # total order (margin ASC, id ASC) -> unique gold set even on ties.
        ranked = sorted((abs(yes - no), eid) for (eid, yes, no) in cur.fetchall())
        gold = {eid for (_margin, eid) in ranked[:CLOSEST_K]}
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_CLOSEST}:{seed}:{congress}:{chamber}",
                template_id=TEMPLATE_CLOSEST,
                tier="C",
                params={"congress": congress, "chamber": chamber, "k": CLOSEST_K},
                prompt=f"Among the {chamber} roll-call votes of Congress {congress}, which "
                f"{CLOSEST_K} had the smallest margin (closest |yea minus nay|), breaking ties "
                f"by roll-call id? List the roll-call ids.",
                gold=gold,
                grader="set_match",
                is_refusal=False,
            )
        )

    # --- refusal: nonexistent congress, proven absent against sessions ---
    n_refusal = max(3, n // 4)
    synthetic = [f"NX-CONGRESS-{seed}-{i:04d}" for i in range(n_refusal)]
    cur.execute(
        f"SELECT identifier FROM sessions WHERE identifier IN ({_in_clause(len(synthetic))})",
        synthetic,
    )
    if cur.fetchall():
        raise AssertionError("synthetic refusal congress ids unexpectedly exist in sessions")
    for i, cid in enumerate(synthetic):
        chamber = "house" if i % 2 == 0 else "senate"
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_CLOSEST}:{seed}:refusal:{cid}:{chamber}",
                template_id=TEMPLATE_CLOSEST,
                tier="C",
                params={"congress": cid, "chamber": chamber, "k": CLOSEST_K},
                prompt=f"Among the {chamber} roll-call votes of Congress {cid}, which "
                f"{CLOSEST_K} had the smallest margin? List the roll-call ids.",
                gold=REFUSAL,
                grader="refusal_correct",
                is_refusal=True,
                refusal_reason="congress_not_in_data",
            )
        )
    return instances


# Template registry — each entry exposes `.generate(conn, n, seed, precomputed)` for the harness.
TEMPLATE_REGISTRY = {
    "vote_lookup": SimpleNamespace(name="vote_lookup", generate=generate),
    "tally": SimpleNamespace(name="tally", generate=generate_tally),
    "closest_by_margin": SimpleNamespace(
        name="closest_by_margin", generate=generate_closest_by_margin
    ),
}
