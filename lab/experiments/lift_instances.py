"""NON-FROZEN lift-study instance generator (harness-lift ablation, REV 4.2 / decision A).

The frozen `member_summary` / `pairwise_agreement` templates gate to `_fully_complete_windows`
(ALL completed congresses x BOTH chambers, ~18 windows) -- incompatible with a single pinned
118-House window and a House-only Clerk reconciliation. So the lift study generates its OWN
instances here, pinned to the **118th House** (the gold-reconciled window: gap=31, 100% procedural
-> our bill-linked set == the public bill/resolution set), with the public-resolvability prompt
phrasing "roll-call votes on bills and resolutions ... any question type."

This module lives OUTSIDE the frozen core: it imports the frozen gold-shape/grader/sampling but
defines NO template in `lab/templates.py`, so `content_hash` does NOT move. The gold SQL is a
byte-for-byte mirror of the frozen `generate_member_summary` / `generate_pairwise_agreement`
aggregates (same joins, same option bucketing, same `fields` grader) -- only the window is pinned
and the prompt re-phrased for public resolvability. See
docs/plans/2026-06-29-feat-lab-harness-lift-ablation-plan.md (pre-registration rev 4.2).

Plugs into `lab.harness.prepare_run` / `lab.ablation.run_ablation` via the duck-typed template
shape (`name`, `template_id`, `generate(conn, n, seed, precomputed)`).
"""

from types import SimpleNamespace

from lab.generate import hash_order, sample
from lab.graders import REFUSAL
from lab.harness import Instance
from lab.templates import _n_refusals

CONGRESS = "118"
CHAMBER = "house"
TEMPLATE_LIFT_MEMBER_SUMMARY = "lift.member_summary_118house"
TEMPLATE_LIFT_PAIRWISE = "lift.pairwise_118house"

# The public-resolvability frame (the lift crux): a NAMED member + the 118th House + the explicit
# "bills and resolutions, any question type" scope, so BOTH arms compute the SAME quantity our
# bill-linked gold holds (matches `is_bill_ref` = bills AND resolutions; gold counts every question
# type already -- only the prompt is made explicit). NO internal vote_event_id / person_id leaks.
_WINDOW_PHRASE = (
    "the roll-call votes on bills and resolutions in the 118th House of Representatives "
    "(any question type)"
)


def _require_complete_window(precomputed) -> None:
    """Guard: the pinned (118, house) window must be a COMPLETED congress (point-in-time gold).
    Tolerant of the empty `Precomputed()` tests pass (skips the 5.4M-row scan) -- only trips on a
    real precompute that does not list the 118th as completed."""
    completed = getattr(precomputed, "completed_congresses", None)
    if completed and CONGRESS not in completed:
        raise RuntimeError(
            f"lift study pins Congress {CONGRESS} but it is not in completed_congresses={completed}"
        )


def _house_member_ids(conn) -> list[str]:
    """Distinct person_ids with a bill-linked 118-House vote record (the answerable population)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT vr.person_id "
        "FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN bills b ON b.id = ve.bill_id "
        "JOIN sessions s ON s.id = b.session_id "
        "WHERE s.identifier = %s AND ve.chamber = %s",
        (CONGRESS, CHAMBER),
    )
    return [r[0] for r in cur.fetchall()]


def _member_summary_gold(cur, pid: str) -> dict[str, int]:
    """{yea, nay, other} over the member's bill-linked 118-House records (present + not_voting
    collapse into `other`). Byte-for-byte the frozen `generate_member_summary` aggregate."""
    cur.execute(
        'SELECT vr."option", COUNT(*) '
        "FROM vote_records vr "
        "JOIN vote_events ve ON ve.id = vr.vote_event_id "
        "JOIN bills b ON b.id = ve.bill_id "
        "JOIN sessions s ON s.id = b.session_id "
        "WHERE vr.person_id = %s AND s.identifier = %s AND ve.chamber = %s "
        'GROUP BY vr."option"',
        (pid, CONGRESS, CHAMBER),
    )
    gold = {"yea": 0, "nay": 0, "other": 0}
    for option, count in cur.fetchall():
        key = option if option in ("yea", "nay") else "other"
        gold[key] += count
    return gold


def _pairwise_gold(cur, person_a: str, person_b: str) -> dict[str, int]:
    """{agreements, shared_events} restricted to events where BOTH cast yea/nay (a mutual
    present/not_voting is neither shared nor an agreement). Mirror of frozen `generate_pairwise`."""
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
        (person_a, person_b, CONGRESS, CHAMBER),
    )
    shared, agreements = 0, 0
    for a_opt, b_opt in cur.fetchall():
        shared += 1
        if a_opt == b_opt:
            agreements += 1
    return {"agreements": agreements, "shared_events": shared}


def member_pairs(member_ids: list[str], n: int, seed: int) -> list[tuple[str, str]]:
    """Deterministically pick up to `n` DISJOINT member pairs: hash-order the population (seed),
    then take adjacent non-overlapping pairs. PURE (no DB) so it is hermetically testable; disjoint
    pairing means no member is double-sampled into two pairs (independent instances)."""
    ordered = hash_order(member_ids, seed)
    pairs: list[tuple[str, str]] = []
    for i in range(n):
        a, b = 2 * i, 2 * i + 1
        if b >= len(ordered):
            break
        pairs.append((ordered[a], ordered[b]))
    return pairs


def _names(cur, ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    placeholders = ",".join(["%s"] * len(ids))
    cur.execute(f"SELECT id, name FROM people WHERE id IN ({placeholders})", ids)
    return {r[0]: r[1] for r in cur.fetchall()}


def _synthetic_refusal_ids(conn, seed: int, count: int) -> list[str]:
    """`count` synthetic person_ids guaranteed absent from `people` (the refusal arm)."""
    ids = [f"NX-{seed}-{i:04d}" for i in range(count)]
    if ids:
        cur = conn.cursor()
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(f"SELECT id FROM people WHERE id IN ({placeholders})", ids)
        if cur.fetchall():
            raise AssertionError("synthetic refusal ids unexpectedly exist in people")
    return ids


def generate_lift_member_summary(conn, n: int, seed: int, precomputed) -> list[Instance]:
    """`n` answerable 118-House member-summary instances (+ proportional refusal twins)."""
    _require_complete_window(precomputed)
    cur = conn.cursor()
    member_ids = _house_member_ids(conn)
    if not member_ids:
        raise RuntimeError(f"no bill-linked {CONGRESS}-{CHAMBER} members found")
    chosen = sample(member_ids, n, seed)
    names = _names(cur, chosen)
    instances: list[Instance] = []
    for pid in chosen:
        name = names.get(pid, pid)
        gold = _member_summary_gold(cur, pid)
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_LIFT_MEMBER_SUMMARY}:{seed}:{pid}",
                template_id=TEMPLATE_LIFT_MEMBER_SUMMARY,
                tier="C",
                params={"person_id": pid, "congress": CONGRESS, "chamber": CHAMBER},
                prompt=f"Across {_WINDOW_PHRASE}, how many did {name} vote yea, how many nay, "
                f"and how many other (present or not voting)?",
                gold=gold,
                grader="fields",
                is_refusal=False,
            )
        )

    for i, pid in enumerate(_synthetic_refusal_ids(conn, seed, _n_refusals(len(instances)))):
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_LIFT_MEMBER_SUMMARY}:{seed}:refusal:{pid}",
                template_id=TEMPLATE_LIFT_MEMBER_SUMMARY,
                tier="C",
                params={"person_id": pid, "congress": CONGRESS, "chamber": CHAMBER},
                prompt=f"Across {_WINDOW_PHRASE}, how did the member with id '{pid}' vote "
                f"(yea / nay / other)?",
                gold=REFUSAL,
                grader="refusal_correct",
                is_refusal=True,
                refusal_reason="person_not_in_data",
            )
        )
    return instances


def generate_lift_pairwise(conn, n: int, seed: int, precomputed) -> list[Instance]:
    """`n` answerable 118-House pairwise-agreement instances (+ proportional refusal twins)."""
    _require_complete_window(precomputed)
    cur = conn.cursor()
    member_ids = _house_member_ids(conn)
    if len(member_ids) < 2:
        raise RuntimeError(
            f"need >=2 bill-linked {CONGRESS}-{CHAMBER} members, got {len(member_ids)}"
        )
    pairs = member_pairs(member_ids, n, seed)
    names = _names(cur, [pid for pair in pairs for pid in pair])
    instances: list[Instance] = []
    for person_a, person_b in pairs:
        gold = _pairwise_gold(cur, person_a, person_b)
        name_a, name_b = names.get(person_a, person_a), names.get(person_b, person_b)
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_LIFT_PAIRWISE}:{seed}:{person_a}:{person_b}",
                template_id=TEMPLATE_LIFT_PAIRWISE,
                tier="C",
                params={
                    "person_a": person_a,
                    "person_b": person_b,
                    "congress": CONGRESS,
                    "chamber": CHAMBER,
                },
                prompt=f"Across {_WINDOW_PHRASE}, on how many did both {name_a} and {name_b} "
                f"vote yea or nay (shared_events), and on how many of those did they vote the "
                f"same way (agreements)?",
                gold=gold,
                grader="fields",
                is_refusal=False,
            )
        )

    for i, pid in enumerate(_synthetic_refusal_ids(conn, seed, _n_refusals(len(instances)))):
        instances.append(
            Instance(
                instance_id=f"{TEMPLATE_LIFT_PAIRWISE}:{seed}:refusal:{pid}",
                template_id=TEMPLATE_LIFT_PAIRWISE,
                tier="C",
                params={
                    "person_a": pid,
                    "person_b": None,
                    "congress": CONGRESS,
                    "chamber": CHAMBER,
                },
                prompt=f"Across {_WINDOW_PHRASE}, on how many did the member with id '{pid}' and "
                f"any other member vote the same way?",
                gold=REFUSAL,
                grader="refusal_correct",
                is_refusal=True,
                refusal_reason="person_not_in_data",
            )
        )
    return instances


# Duck-typed template objects (name/template_id/generate) for prepare_run / run_ablation.
LIFT_TEMPLATES = {
    "lift_member_summary": SimpleNamespace(
        name="lift_member_summary",
        template_id=TEMPLATE_LIFT_MEMBER_SUMMARY,
        generate=generate_lift_member_summary,
    ),
    "lift_pairwise": SimpleNamespace(
        name="lift_pairwise",
        template_id=TEMPLATE_LIFT_PAIRWISE,
        generate=generate_lift_pairwise,
    ),
}
