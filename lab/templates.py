"""FROZEN Family 1 templates — gold computed by trusted, engine-portable SQL.

Phase 0 ships Template #1 (vote lookup). Gold is read directly from `vote_records`
(the canonical store), never hand-authored. The #1 trust-floor dichotomy:
  - answerable: a (member, event) pair that EXISTS in vote_records -> gold = the recorded option
  - refusal:    a member with NO vote_records anywhere -> gold = REFUSAL ("not in the data")
We do NOT claim an eligible/ineligible distinction (the schema can't support it).
"""

from collections import defaultdict
from types import SimpleNamespace
from typing import Literal

from lab.generate import pick_one, sample
from lab.graders import REFUSAL
from lab.harness import Instance

TEMPLATE_VOTE_LOOKUP = "family1.vote_lookup"
TEMPLATE_TALLY = "family1.tally"
TEMPLATE_CLOSEST = "family1.closest_by_margin"
TEMPLATE_MEMBER_SUMMARY = "family1.member_summary"
TEMPLATE_PAIRWISE = "family1.pairwise_agreement"
TEMPLATE_PARTY_BREAKDOWN = "family1.party_breakdown"
TEMPLATE_PARTY_DEFECTION = "family1.party_defection"
TEMPLATE_CROSSED_PARTY = "family1.crossed_party"
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


def _fully_complete_windows(conn, precomputed) -> list[tuple[str, str]]:
    """(congress, chamber) windows where EVERY event reconciles exactly (all-or-nothing) AND the
    congress is completed (point-in-time). ALL-OR-NOTHING is the honest framing: filtering
    incomplete events *inside* a window would silently change the per-member / pairwise denominator
    (a partial tally presented as the member's full-congress record = fabrication-by-omission).
    Returns a sorted list for deterministic sampling. (Currently every completed window is fully
    complete — the only undercount is the ongoing congress, already gated out — but this stays a
    real guard: a future re-ingest that leaves one unmatched voter drops that whole window.)"""
    cur = conn.cursor()
    cur.execute(
        "SELECT ve.id, s.identifier, ve.chamber "
        "FROM vote_events ve "
        "JOIN bills b ON b.id = ve.bill_id "
        "JOIN sessions s ON s.id = b.session_id"
    )
    total: dict[tuple[str, str], int] = defaultdict(int)
    incomplete: dict[tuple[str, str], int] = defaultdict(int)
    for eid, congress, chamber in cur.fetchall():
        if congress not in precomputed.completed_congresses:
            continue
        win = (congress, chamber)
        total[win] += 1
        if eid not in precomputed.complete_events:
            incomplete[win] += 1
    return sorted(w for w, t in total.items() if incomplete[w] == 0)


def generate_member_summary(conn, n: int, seed: int, precomputed) -> list[Instance]:
    """Template #6 (per-member summary): a member's option counts across a {congress, chamber}.

    Group B — `GROUP BY` over the member's records, so it samples only FULLY-COMPLETE windows
    (every event reconciled -> every member's record present). Reported as `{yea, nay, other}`:
    `other` = present + not_voting, which reconciles against the stored `other_count` bucket; the
    present/not_voting split is deliberately NOT reported (it rests on ingest classification the
    gate cannot re-verify). Uses ix_vote_records_person_id.
    """
    cur = conn.cursor()
    instances: list[Instance] = []
    windows = _fully_complete_windows(conn, precomputed)
    win_ids = {f"{c}:{ch}": (c, ch) for (c, ch) in windows}

    for wid in sample(list(win_ids), n, seed):
        congress, chamber = win_ids[wid]
        cur.execute(
            "SELECT DISTINCT vr.person_id "
            "FROM vote_records vr "
            "JOIN vote_events ve ON ve.id = vr.vote_event_id "
            "JOIN bills b ON b.id = ve.bill_id "
            "JOIN sessions s ON s.id = b.session_id "
            "WHERE s.identifier = %s AND ve.chamber = %s",
            (congress, chamber),
        )
        member_ids = [r[0] for r in cur.fetchall()]
        if not member_ids:
            continue
        pid = pick_one(member_ids, seed)
        cur.execute("SELECT name FROM people WHERE id = %s", (pid,))
        row = cur.fetchone()
        name = row[0] if row else pid
        cur.execute(
            'SELECT vr."option", COUNT(*) '
            "FROM vote_records vr "
            "JOIN vote_events ve ON ve.id = vr.vote_event_id "
            "JOIN bills b ON b.id = ve.bill_id "
            "JOIN sessions s ON s.id = b.session_id "
            "WHERE vr.person_id = %s AND s.identifier = %s AND ve.chamber = %s "
            'GROUP BY vr."option"',
            (pid, congress, chamber),
        )
        gold = {"yea": 0, "nay": 0, "other": 0}
        for option, count in cur.fetchall():
            key = option if option in ("yea", "nay") else "other"
            gold[key] += count
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_MEMBER_SUMMARY}:{seed}:{congress}:{chamber}:{pid}",
                template_id=TEMPLATE_MEMBER_SUMMARY,
                tier="C",
                params={"person_id": pid, "congress": congress, "chamber": chamber},
                prompt=f"Across the {chamber} roll-call votes of Congress {congress}, how many did "
                f"{name} vote yea, how many nay, and how many other (present or not voting)?",
                gold=gold,
                grader="fields",
                is_refusal=False,
            )
        )

    # --- refusal: synthetic nonexistent member over a real fully-complete window ---
    n_refusal = max(3, n // 4)
    synthetic = [f"NX-{seed}-{i:04d}" for i in range(n_refusal)]
    cur.execute(f"SELECT id FROM people WHERE id IN ({_in_clause(len(synthetic))})", synthetic)
    if cur.fetchall():
        raise AssertionError("synthetic refusal ids unexpectedly exist in people")
    for i, pid in enumerate(synthetic):
        if not windows:
            break
        congress, chamber = windows[i % len(windows)]
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_MEMBER_SUMMARY}:{seed}:refusal:{congress}:{chamber}:{pid}",
                template_id=TEMPLATE_MEMBER_SUMMARY,
                tier="C",
                params={"person_id": pid, "congress": congress, "chamber": chamber},
                prompt=f"Across the {chamber} roll-call votes of Congress {congress}, how did the "
                f"member with id '{pid}' vote (yea / nay / other)?",
                gold=REFUSAL,
                grader="refusal_correct",
                is_refusal=True,
                refusal_reason="person_not_in_data",
            )
        )
    return instances


def generate_pairwise_agreement(conn, n: int, seed: int, precomputed) -> list[Instance]:
    """Template #7 (pairwise agreement): on shared yea/nay roll calls in a {congress, chamber},
    how often two members voted the same way.

    Group B — fully-complete windows only (so "shared" is not undercounted). Both the shared and
    the agreement counts are restricted to events where BOTH members cast a yea/nay vote (a mutual
    present/not_voting is neither "both voted" nor an "agreement"). Two sargable person_id index
    scans joined on vote_event_id (the (vote_event_id, person_id) uniqueness makes it one row per
    shared event -> no double counting).
    """
    cur = conn.cursor()
    instances: list[Instance] = []
    windows = _fully_complete_windows(conn, precomputed)
    win_ids = {f"{c}:{ch}": (c, ch) for (c, ch) in windows}

    for wid in sample(list(win_ids), n, seed):
        congress, chamber = win_ids[wid]
        cur.execute(
            "SELECT DISTINCT vr.person_id "
            "FROM vote_records vr "
            "JOIN vote_events ve ON ve.id = vr.vote_event_id "
            "JOIN bills b ON b.id = ve.bill_id "
            "JOIN sessions s ON s.id = b.session_id "
            "WHERE s.identifier = %s AND ve.chamber = %s",
            (congress, chamber),
        )
        member_ids = [r[0] for r in cur.fetchall()]
        if len(member_ids) < 2:
            continue
        person_a, person_b = sample(member_ids, 2, seed)  # two smallest-hash members
        cur.execute("SELECT id, name FROM people WHERE id IN (%s, %s)", (person_a, person_b))
        names = {r[0]: r[1] for r in cur.fetchall()}
        cur.execute(
            'SELECT ra."option", rb."option" '
            "FROM vote_records ra "
            "JOIN vote_records rb ON ra.vote_event_id = rb.vote_event_id "
            "JOIN vote_events ve ON ve.id = ra.vote_event_id "
            "JOIN bills b ON b.id = ve.bill_id "
            "JOIN sessions s ON s.id = b.session_id "
            "WHERE ra.person_id = %s AND rb.person_id = %s "
            "AND s.identifier = %s AND ve.chamber = %s "
            "AND ra.\"option\" IN ('yea', 'nay') AND rb.\"option\" IN ('yea', 'nay')",
            (person_a, person_b, congress, chamber),
        )
        shared, agreements = 0, 0
        for a_opt, b_opt in cur.fetchall():
            shared += 1
            if a_opt == b_opt:
                agreements += 1
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_PAIRWISE}:{seed}:{congress}:{chamber}:{person_a}:{person_b}",
                template_id=TEMPLATE_PAIRWISE,
                tier="C",
                params={
                    "person_a": person_a,
                    "person_b": person_b,
                    "congress": congress,
                    "chamber": chamber,
                },
                prompt=f"Across the {chamber} roll-call votes of Congress {congress}, on how many "
                f"did both {names.get(person_a, person_a)} and "
                f"{names.get(person_b, person_b)} vote yea or nay (shared_events), and on how many "
                f"of those did they vote the same way (agreements)?",
                gold={"agreements": agreements, "shared_events": shared},
                grader="fields",
                is_refusal=False,
            )
        )

    # --- refusal: a synthetic nonexistent member paired with a real one over a real window ---
    n_refusal = max(3, n // 4)
    synthetic = [f"NX-{seed}-{i:04d}" for i in range(n_refusal)]
    cur.execute(f"SELECT id FROM people WHERE id IN ({_in_clause(len(synthetic))})", synthetic)
    if cur.fetchall():
        raise AssertionError("synthetic refusal ids unexpectedly exist in people")
    for i, pid in enumerate(synthetic):
        if not windows:
            break
        congress, chamber = windows[i % len(windows)]
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_PAIRWISE}:{seed}:refusal:{congress}:{chamber}:{pid}",
                template_id=TEMPLATE_PAIRWISE,
                tier="C",
                params={
                    "person_a": pid,
                    "person_b": None,
                    "congress": congress,
                    "chamber": chamber,
                },
                prompt=f"Across the {chamber} roll-call votes of Congress {congress}, on how many "
                f"did the member with id '{pid}' and any other member vote the same way?",
                gold=REFUSAL,
                grader="refusal_correct",
                is_refusal=True,
                refusal_reason="person_not_in_data",
            )
        )
    return instances


def _party_eligible_events(conn, precomputed) -> frozenset[str]:
    """Events a `party_breakdown` (and 3c's defection/crossed) may use — the reusable 3-gate
    intersection, computed ONCE per run:
      (1) COMPLETED-congress dated events (point-in-time gate, EXPLICIT — not incidental);
      (2) ∩ `precomputed.complete_events` (records reconcile to the official counts);
      (3) − events where ANY voter maps to ≠1 party span as-of `vote_date`. `COUNT(span) <> 1`
          catches BOTH 0 (omission) and >1 (overlap double-count), so this does NOT rely on the
          span construction staying overlap-free (person_party_spans is a maintained gold table).
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT ve.id "
        "FROM vote_events ve "
        "JOIN bills b ON b.id = ve.bill_id "
        "JOIN sessions s ON s.id = b.session_id "
        "WHERE ve.vote_date IS NOT NULL AND s.end_date IS NOT NULL"
    )
    completed_dated = {r[0] for r in cur.fetchall()}
    cur.execute(
        "SELECT vr.vote_event_id "
        "FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "LEFT JOIN person_party_spans pps ON pps.person_id = vr.person_id "
        "AND ve.vote_date >= pps.start_date AND ve.vote_date < pps.end_date "
        "WHERE ve.vote_date IS NOT NULL "
        "GROUP BY vr.vote_event_id, vr.person_id HAVING COUNT(pps.id) <> 1"
    )
    not_exactly_one = {r[0] for r in cur.fetchall()}
    return frozenset((completed_dated & precomputed.complete_events) - not_exactly_one)


def _party_majority_side(yea: int, nay: int) -> Literal["yea", "nay"] | None:
    """The blessed `party_majority` definition (RESOLVED registry entry): the side a STRICT majority
    of the party's yea+nay voters took. Denominator = yea+nay voters (absences/present excluded). A
    tie or zero voters -> None (no majority -> the (party, event) is excluded; never a guess).
    """
    if yea > nay:
        return "yea"
    if nay > yea:
        return "nay"
    return None


def _event_party_splits(conn, eid: str) -> dict[str, dict[str, int]]:
    """{party: {"yea": n, "nay": m}} for one event, by VOTE-TIME party (the half-open as-of join),
    yea/nay only, 0-filled. Shared by party_breakdown + party_defection."""
    cur = conn.cursor()
    cur.execute(
        'SELECT pps.party, vr."option", COUNT(*) '
        "FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN person_party_spans pps ON pps.person_id = vr.person_id "
        "AND ve.vote_date >= pps.start_date AND ve.vote_date < pps.end_date "
        "WHERE vr.vote_event_id = %s AND vr.\"option\" IN ('yea', 'nay') "
        'GROUP BY pps.party, vr."option"',
        (eid,),
    )
    splits: dict[str, dict[str, int]] = {}
    for party, option, count in cur.fetchall():
        splits.setdefault(party, {"yea": 0, "nay": 0})[option] += count
    return splits


def _eligible_party_sides(
    splits: dict[str, dict[str, int]],
) -> dict[str, Literal["yea", "nay"]]:
    """The SINGLE home of the defection/crossed eligibility predicate: parties with >=2 yea/nay
    voters AND a non-null (strict) majority -> {party: majority_side}. A tie is excluded (null
    majority); a 1-member party is excluded by >=2. (party_breakdown deliberately does NOT use this
    — its counts-only breakdown tolerates ties; it keeps its own >=2-only filter.)"""
    out: dict[str, Literal["yea", "nay"]] = {}
    for party, c in splits.items():
        if c["yea"] + c["nay"] < 2:
            continue
        side = _party_majority_side(c["yea"], c["nay"])
        if side is not None:
            out[party] = side
    return out


def generate_party_breakdown(conn, n: int, seed: int, precomputed) -> list[Instance]:
    """Template #4 (party breakdown): a single party's yea/nay split on one roll call, using
    VOTE-TIME party (the half-open as-of join on person_party_spans — NEVER people.party, which is
    current-only and post-dates switchers).

    Counts-only, single-party-per-instance. Samples only `_party_eligible_events` (complete ∩
    exactly-one-span ∩ completed-congress) and a party with **≥2** yea/nay voters on the event (a
    breakdown needs ≥2 to be a real split; excludes trivial single-member items that duplicate
    vote_lookup — party-agnostic, no D/R allowlist; tie-tolerant since it's counts-only). Gold =
    `{yea, nay}`, 0-filled (both keys always present so grade_fields never key-mismatches).
    """
    cur = conn.cursor()
    instances: list[Instance] = []
    chosen = sample(sorted(_party_eligible_events(conn, precomputed)), n, seed)

    motions: dict[str, str | None] = {}
    if chosen:
        cur.execute(
            f"SELECT id, motion_text FROM vote_events WHERE id IN ({_in_clause(len(chosen))})",
            chosen,
        )
        motions = {r[0]: r[1] for r in cur.fetchall()}

    for eid in chosen:
        by_party = _event_party_splits(conn, eid)
        # a "breakdown" needs >=2 yea/nay voters; excludes the trivial single-member case (tie OK).
        candidates = sorted(p for p, c in by_party.items() if c["yea"] + c["nay"] >= 2)
        if not candidates:
            continue
        party = pick_one(candidates, seed)
        motion = (motions.get(eid) or "the recorded motion").strip()
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_PARTY_BREAKDOWN}:{seed}:{eid}:{party}",
                template_id=TEMPLATE_PARTY_BREAKDOWN,
                tier="C",
                params={"vote_event_id": eid, "party": party},
                prompt=f"On roll call {eid} ({motion}), how many members of the {party} party "
                f"voted yea and how many voted nay?",
                gold=by_party[party],
                grader="fields",
                is_refusal=False,
            )
        )

    # --- refusal: synthetic nonexistent event id, proven absent before emit ---
    n_refusal = max(3, n // 4)
    synthetic = [f"NX-EVENT-{seed}-{i:04d}" for i in range(n_refusal)]
    cur.execute(f"SELECT id FROM vote_events WHERE id IN ({_in_clause(len(synthetic))})", synthetic)
    if cur.fetchall():
        raise AssertionError("synthetic refusal event ids unexpectedly exist in vote_events")
    for eid in synthetic:
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_PARTY_BREAKDOWN}:{seed}:refusal:{eid}",
                template_id=TEMPLATE_PARTY_BREAKDOWN,
                tier="C",
                params={"vote_event_id": eid, "party": "D"},  # placeholder party for shape parity
                prompt=f"On roll call {eid}, how many members of the D party voted yea and how "
                f"many voted nay?",
                gold=REFUSAL,
                grader="refusal_correct",
                is_refusal=True,
                refusal_reason="event_not_in_data",
            )
        )
    return instances


def generate_party_defection(conn, n: int, seed: int, precomputed) -> list[Instance]:
    """Template #5 (party defection): how many {party} members voted AGAINST their party's majority.
    gold = min(yea, nay) (the minority/against-majority count), a bare int. Vote-time party; samples
    an eligible (event, party) with a NON-NULL majority and >=2 yea/nay voters (a tied party has no
    majority -> excluded, never a guessed side)."""
    cur = conn.cursor()
    instances: list[Instance] = []
    chosen = sample(sorted(_party_eligible_events(conn, precomputed)), n, seed)

    motions: dict[str, str | None] = {}
    if chosen:
        cur.execute(
            f"SELECT id, motion_text FROM vote_events WHERE id IN ({_in_clause(len(chosen))})",
            chosen,
        )
        motions = {r[0]: r[1] for r in cur.fetchall()}

    for eid in chosen:
        splits = _event_party_splits(conn, eid)
        eligible = _eligible_party_sides(splits)  # {party: majority_side}; non-null majority, >=2
        if not eligible:
            continue
        party = pick_one(sorted(eligible), seed)
        c = splits[party]
        defectors = min(c["yea"], c["nay"])  # the non-majority (minority) side count
        motion = (motions.get(eid) or "the recorded motion").strip()
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_PARTY_DEFECTION}:{seed}:{eid}:{party}",
                template_id=TEMPLATE_PARTY_DEFECTION,
                tier="C",
                params={"vote_event_id": eid, "party": party},
                prompt=f"On roll call {eid} ({motion}), how many members of the {party} party "
                f"voted against their party's majority?",
                gold=defectors,
                grader="exact_int",
                is_refusal=False,
            )
        )

    instances.extend(_party_event_refusals(cur, TEMPLATE_PARTY_DEFECTION, n, seed))
    return instances


def generate_crossed_party(conn, n: int, seed: int, precomputed) -> list[Instance]:
    """Template #6 (crossed party): WHICH {party} members crossed party lines (voted against their
    party's majority). gold = the SET of person_ids on the minority side (∅ if unanimous). ONE
    per-event (party, option, person_id) query -> counts + ids from the SAME rows, so
    len(gold) == min(yea, nay) holds by construction (asserted)."""
    cur = conn.cursor()
    instances: list[Instance] = []
    chosen = sample(sorted(_party_eligible_events(conn, precomputed)), n, seed)

    motions: dict[str, str | None] = {}
    if chosen:
        cur.execute(
            f"SELECT id, motion_text FROM vote_events WHERE id IN ({_in_clause(len(chosen))})",
            chosen,
        )
        motions = {r[0]: r[1] for r in cur.fetchall()}

    for eid in chosen:
        cur.execute(
            'SELECT pps.party, vr."option", vr.person_id '
            "FROM vote_records vr "
            "JOIN vote_events ve ON ve.id = vr.vote_event_id "
            "JOIN person_party_spans pps ON pps.person_id = vr.person_id "
            "AND ve.vote_date >= pps.start_date AND ve.vote_date < pps.end_date "
            "WHERE vr.vote_event_id = %s AND vr.\"option\" IN ('yea', 'nay')",
            (eid,),
        )
        splits: dict[str, dict[str, int]] = {}
        ids: dict[str, dict[str, list[str]]] = {}
        for party, option, pid in cur.fetchall():
            splits.setdefault(party, {"yea": 0, "nay": 0})[option] += 1
            ids.setdefault(party, {"yea": [], "nay": []})[option].append(pid)
        eligible = _eligible_party_sides(splits)
        if not eligible:
            continue
        party = pick_one(sorted(eligible), seed)
        minority = "nay" if eligible[party] == "yea" else "yea"
        crossers = set(ids[party][minority])
        assert len(crossers) == min(splits[party]["yea"], splits[party]["nay"]), (
            f"{eid}/{party}: crosser set size != defection count"
        )
        motion = (motions.get(eid) or "the recorded motion").strip()
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_CROSSED_PARTY}:{seed}:{eid}:{party}",
                template_id=TEMPLATE_CROSSED_PARTY,
                tier="C",
                params={"vote_event_id": eid, "party": party},
                prompt=f"On roll call {eid} ({motion}), which members of the {party} party crossed "
                f"party lines (voted against their party's majority)? List the member ids.",
                gold=crossers,
                grader="set_match",
                is_refusal=False,
            )
        )

    instances.extend(_party_event_refusals(cur, TEMPLATE_CROSSED_PARTY, n, seed))
    return instances


def _party_event_refusals(cur, template_id: str, n: int, seed: int) -> list[Instance]:
    """Shared refusal twins for the party-keyed event templates: synthetic nonexistent vote_event
    ids, proven absent before emit, gold=REFUSAL."""
    n_refusal = max(3, n // 4)
    synthetic = [f"NX-EVENT-{seed}-{i:04d}" for i in range(n_refusal)]
    cur.execute(f"SELECT id FROM vote_events WHERE id IN ({_in_clause(len(synthetic))})", synthetic)
    if cur.fetchall():
        raise AssertionError("synthetic refusal event ids unexpectedly exist in vote_events")
    return [
        Instance(
            instance_id=f"{template_id}:{seed}:refusal:{eid}",
            template_id=template_id,
            tier="C",
            params={"vote_event_id": eid, "party": "D"},  # placeholder party for shape parity
            prompt=f"On roll call {eid}, how many members of the D party voted against their "
            f"party's majority?",
            gold=REFUSAL,
            grader="refusal_correct",
            is_refusal=True,
            refusal_reason="event_not_in_data",
        )
        for eid in synthetic
    ]


# Template registry — each entry exposes `.generate(conn, n, seed, precomputed)` for the harness.
TEMPLATE_REGISTRY = {
    "vote_lookup": SimpleNamespace(name="vote_lookup", generate=generate),
    "tally": SimpleNamespace(name="tally", generate=generate_tally),
    "closest_by_margin": SimpleNamespace(
        name="closest_by_margin", generate=generate_closest_by_margin
    ),
    "member_summary": SimpleNamespace(name="member_summary", generate=generate_member_summary),
    "pairwise_agreement": SimpleNamespace(
        name="pairwise_agreement", generate=generate_pairwise_agreement
    ),
    "party_breakdown": SimpleNamespace(name="party_breakdown", generate=generate_party_breakdown),
    "party_defection": SimpleNamespace(name="party_defection", generate=generate_party_defection),
    "crossed_party": SimpleNamespace(name="crossed_party", generate=generate_crossed_party),
}
