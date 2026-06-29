"""CLI: python -m lab.run --template vote_lookup --n 20 --seed 42        (deterministic solvers)
       python -m lab.run --template vote_lookup --agent --n 10           (live agent — real LLM)

Deterministic mode runs the SQL-oracle + wrong-baseline + over-refuse solvers and ASSERTS the v1
machinery invariants (oracle 100% / wrong-baseline 0% / over-refuse fails answerable). Agent mode
runs the live AgentSolver: a non-deterministic measurement, so it asserts NO invariant — its pass
rate is the signal. The two modes are separate code paths (the agent run has no oracle/wrong/over
keys, so it must never touch the deterministic-invariant block).
"""

import argparse
import re
import sys
from collections import Counter

from lab import templates
from lab.harness import get_connection, run
from lab.precompute import Precomputed, precompute
from lab.solvers import AgentSolver, OverRefuseSolver, SqlOracleSolver, WrongBaselineSolver
from src.ingestion.vote_parsers import OPTION_BUCKETS


def _counts(rows) -> tuple[int, int, int, int]:
    ans = [v.passed for (_id, ref, v) in rows if not ref]
    ref = [v.passed for (_id, ref, v) in rows if ref]
    return sum(ans), len(ans), sum(ref), len(ref)


def vote_lookup_name_collisions(conn, instances) -> set[str]:
    """Answerable vote_lookup instance ids whose looked-up member shares a NAME with another voter
    in the SAME event. The prompt gives a name but the gold is person_id-keyed, so a collision is
    INPUT AMBIGUITY, not an agent error — excluded from the *reported* clean rate. Read-only; never
    touches gold."""
    cur = conn.cursor()
    collided: set[str] = set()
    for inst in instances:
        if inst.is_refusal or not inst.template_id.endswith("vote_lookup"):
            continue
        eid = inst.params["vote_event_id"]
        pid = inst.params["person_id"]
        cur.execute(
            "SELECT COUNT(*) FROM vote_records vr JOIN people p ON p.id = vr.person_id "
            "WHERE vr.vote_event_id = %s AND p.name = (SELECT name FROM people WHERE id = %s)",
            (eid, pid),
        )
        if cur.fetchone()[0] > 1:
            collided.add(inst.instance_id)
    return collided


def _core_name_tokens(full_name: str) -> list[str]:
    """The natural-name tokens a reasonable agent would pass: people.name is stored
    'Sen. Murkowski, Lisa [R-AK]' -> ['murkowski', 'lisa'] (drop the title prefix + the
    [party-state-district] bracket, keep alphabetic tokens). Mirrors find_people's tokenization so
    the collision check models the same query the agent makes."""
    s = re.sub(r"\[.*?\]", " ", full_name)  # drop [party-state-district]
    s = re.sub(r"^\s*\w+\.\s+", " ", s)  # drop a leading title ('Sen. ' / 'Rep. ')
    return [t for t in s.lower().replace(",", " ").split() if t.isalpha()]


def window_name_collisions(conn, instances, person_keys) -> set[str]:
    """Answerable window-template (member_summary / pairwise) instance ids where a sampled member's
    natural NAME (first + last) token-matches >1 voter in the SAME (congress, chamber) window. The
    prompt names the member but gold is person_id-keyed, so a collision is INPUT AMBIGUITY, not an
    agent error — excluded from the *reported* clean rate. `person_keys` = the params key(s) holding
    the person id(s). The match (every core token a substring of the name; any vote in the window,
    NO option filter) is IDENTICAL to find_people's, so the excluded set matches what the agent
    actually sees. Read-only; never touches gold."""
    cur = conn.cursor()
    collided: set[str] = set()
    for inst in instances:
        if inst.is_refusal:
            continue
        congress = inst.params["congress"]
        chamber = inst.params["chamber"]
        for key in person_keys:
            pid = inst.params[key]
            cur.execute("SELECT name FROM people WHERE id = %s", (pid,))
            row = cur.fetchone()
            if row is None:
                continue
            tokens = _core_name_tokens(row[0])
            if not tokens:
                continue
            like = " AND ".join(["LOWER(p.name) LIKE %s"] * len(tokens))
            params = [f"%{t}%" for t in tokens] + [congress, chamber]
            cur.execute(
                "SELECT COUNT(DISTINCT p.id) FROM people p "
                "JOIN vote_records vr ON vr.person_id = p.id "
                "JOIN vote_events ve ON ve.id = vr.vote_event_id "
                "JOIN bills b ON b.id = ve.bill_id "
                "JOIN sessions s ON s.id = b.session_id "
                f"WHERE {like} AND s.identifier = %s AND ve.chamber = %s",
                params,
            )
            if cur.fetchone()[0] > 1:
                collided.add(inst.instance_id)
                break  # one ambiguous member is enough to exclude the instance
    return collided


def _trivial_baseline(template, name: str, n: int, seed: int):
    """For templates whose gold is often a trivial constant (party_defection -> 0, crossed_party ->
    ∅), the share of ANSWERABLE golds equal to that constant — the floor an agent that always
    answers 0 / [] would hit WITHOUT reasoning. Read-only; regenerates the seed-deterministic
    instances (needs the real precompute for the party eligibility gate). Returns (floor, n_ans)
    or None when not applicable."""
    if name not in ("party_defection", "crossed_party"):
        return None
    conn = get_connection()
    try:
        instances = template.generate(conn, n, seed, precompute(conn))
    finally:
        conn.close()
    answerable = [i for i in instances if not i.is_refusal]
    if not answerable:
        return None
    if name == "party_defection":
        trivial = sum(1 for i in answerable if i.gold == 0)
    else:  # crossed_party
        trivial = sum(1 for i in answerable if len(i.gold) == 0)
    return trivial, len(answerable)


def _name_collisions(template, name: str, n: int, seed: int) -> set[str]:
    """Regenerate the (seed-deterministic) instances read-only and flag name collisions (INPUT
    ambiguity — the prompt names a member but gold is id-keyed). Dispatches per template:
    vote_lookup is event-scoped (and ignores `precomputed`, so an empty one yields the identical
    set); member_summary / pairwise are window-scoped and CONSUME precompute (the fully-complete-
    window gate), so they MUST regenerate with the REAL precompute (P4) — an empty one yields zero
    instances and
    the exclusion would silently never fire."""
    conn = get_connection()
    try:
        if name == "vote_lookup":
            instances = template.generate(conn, n, seed, Precomputed())
            return vote_lookup_name_collisions(conn, instances)
        if name == "member_summary":
            instances = template.generate(conn, n, seed, precompute(conn))
            return window_name_collisions(conn, instances, ["person_id"])
        if name == "pairwise_agreement":
            instances = template.generate(conn, n, seed, precompute(conn))
            return window_name_collisions(conn, instances, ["person_a", "person_b"])
        return set()
    finally:
        conn.close()


def _run_deterministic(template, name: str, n: int, seed: int) -> int:
    solvers = [SqlOracleSolver(), WrongBaselineSolver(), OverRefuseSolver()]
    results = run(template, solvers, n, seed, set(OPTION_BUCKETS))

    print(f"Template {name}, n={n}, seed={seed}")
    for sname, rows in results.items():
        ap, at, rp, rt = _counts(rows)
        passed = sum(v.passed for *_, v in rows)
        mean_score = sum(v.score for *_, v in rows) / len(rows)
        print(
            f"  {sname:14} pass {passed}/{len(rows)} "
            f"(answerable {ap}/{at}, refusal {rp}/{rt})  mean_score={mean_score:.2f}"
        )

    oracle = results["oracle"]
    wrong = results["wrong-baseline"]
    over = results["over-refuse"]
    assert oracle and all(v.passed for *_, v in oracle), "INVARIANT FAIL: oracle must pass 100%"
    assert not any(v.passed for *_, v in wrong), "INVARIANT FAIL: wrong-baseline must pass nothing"
    assert all(
        v.subscores["decision_correct"] == 1.0 and v.subscores["answer_correct"] == 0.0
        for (_id, ref, v) in wrong
        if not ref
    ), "INVARIANT FAIL: wrong-baseline answerable must be attempted-but-wrong"
    assert all(v.subscores["decision_correct"] == 0.0 for (_id, ref, v) in over if not ref), (
        "INVARIANT FAIL: over-refuse must over-refuse every answerable instance"
    )
    print("INVARIANTS OK: oracle 100% · wrong-baseline 0% · over-refuse fails all answerable")
    return 0


def _run_agent(
    template,
    name: str,
    n: int,
    seed: int,
    model: str | None = None,
    backend: str = "messages-api",
    max_turns: int | None = None,
    max_budget_usd: float | None = None,
) -> int:
    # NON-DETERMINISTIC: a live agent's pass rate IS the measurement; no invariant is asserted.
    # max_turns matters for long tool-loops (an agent issuing many sequential tool calls): the
    # agent-sdk default is 14, far below a long loop's needs -> raise it for those templates.
    kw = {"backend": backend, "max_turns": max_turns, "max_budget_usd": max_budget_usd}
    solver = AgentSolver(model=model, **kw) if model else AgentSolver(**kw)
    try:
        results = run(template, [solver], n, seed, set(OPTION_BUCKETS))
    finally:
        solver.close()

    rows = results["agent"]
    ap, at, rp, rt = _counts(rows)
    passed = sum(v.passed for *_, v in rows)
    mean_score = sum(v.score for *_, v in rows) / len(rows)
    print(f"AGENT run: template {name}, n={n}, seed={seed}, model={solver.model}")
    print(
        f"  pass {passed}/{len(rows)} "
        f"(answerable {ap}/{at}, refusal {rp}/{rt})  mean_score={mean_score:.2f}"
    )
    for iid, ref, v in rows:
        kind = "refusal" if ref else "answerable"
        print(f"    [{'PASS' if v.passed else 'FAIL'}] {kind:10} {iid}  score={v.score:.2f}")

    # Fairness diagnostics (additive — NEVER touch a grader): separate a protocol/format miss from
    # a knowledge miss, surface a harness/API problem, and flag passes that did NO retrieval (a
    # base-rate / prompt-phrasing game, not real lookup).
    hist = {h["instance_id"]: h for h in solver.history}
    fmt_fail = sum(1 for (_i, _r, v) in rows if v.subscores.get("format_valid") == 0.0)
    errored = sum(1 for h in solver.history if h["errored"])
    no_retrieval_pass = sum(
        1 for (iid, _ref, v) in rows if v.passed and not hist.get(iid, {}).get("retrieved", False)
    )
    print(
        f"  diagnostics: format-fail (never-submitted/non-canonical/error) {fmt_fail}/{len(rows)}; "
        f"agent-errors {errored}; passes with NO retrieval {no_retrieval_pass}"
    )
    if errored:
        print("  WARNING: agent-errors present — high count = harness/API problem, not the agent")
    if no_retrieval_pass:
        print("  WARNING: passes WITHOUT retrieval — possible base-rate/phrasing game; inspect")

    # P7: SDK stop-reason distribution. A budget/turn-truncated rollout submits nothing ->
    # NO_ANSWER, which looks identical to a wrong answer. Surface the subtypes so a truncation is
    # distinguishable from a miss (only the agent-sdk backend populates result_subtype; else None).
    subtypes = Counter(h["result_subtype"] for h in solver.history if h.get("result_subtype"))
    if subtypes:
        dist = ", ".join(f"{k}={v}" for k, v in sorted(subtypes.items()))
        print(f"  SDK result subtypes: {dist}")
        non_success = sum(v for k, v in subtypes.items() if k != "success")
        if non_success:
            print(
                f"  NOTE: {non_success} rollout(s) ended non-success (budget/turn truncation?) — "
                "their NO_ANSWER is a protocol miss, not a wrong answer; inspect before trusting"
            )

    # Trivial-constant baseline (additive; never touches a grader): defection gold is often 0,
    # crossed often ∅ — an agent that always answers 0/[] hits this floor WITHOUT reasoning.
    try:
        baseline = _trivial_baseline(template, name, n, seed)
    except Exception as exc:  # noqa: BLE001 — a diagnostic must never abort the measurement
        print(f"  (trivial-constant baseline skipped: {type(exc).__name__}: {exc})")
    else:
        if baseline is not None:
            floor, n_ans = baseline
            ans_pass = sum(1 for (_i, ref, v) in rows if v.passed and not ref)
            fr = floor / n_ans if n_ans else 0.0
            ar = ans_pass / n_ans if n_ans else 0.0
            print(
                f"  trivial-constant baseline (always-0 / always-empty): {floor}/{n_ans} "
                f"({fr:.2f}); agent answerable pass {ans_pass}/{n_ans} ({ar:.2f})"
            )
            if n_ans and ar <= fr:
                print("  WARNING: agent does NOT beat the trivial-constant baseline — likely guess")

    # A4b: name-collision noise floor (read-only; never touches gold; must not break the run).
    try:
        collided = _name_collisions(template, name, n, seed)
    except Exception as exc:  # noqa: BLE001 — a diagnostic must never abort the measurement
        print(f"  (name-collision diagnostic skipped: {type(exc).__name__}: {exc})")
    else:
        if collided:
            clean = [r for r in rows if r[0] not in collided]
            cap = sum(v.passed for *_, v in clean)
            rate = cap / len(clean) if clean else 0.0
            print(
                f"  name-collision instances excluded: {len(collided)}; "
                f"clean pass {cap}/{len(clean)} ({rate:.2f})"
            )
        else:
            print("  no name-collision ambiguity in this sample")
    print("(measurement — no invariant asserted for a non-deterministic agent)")
    return 0


def main(argv: list[str] | None = None) -> int:
    # The summary carries unicode (·, etc.); keep a Windows cp1252 console from crashing on print.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="Condorcet Lab — Family 1 harness")
    parser.add_argument(
        "--n", type=int, default=None, help="answerable instances (default 20; 10 for --agent)"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--template",
        default="vote_lookup",
        choices=sorted(templates.TEMPLATE_REGISTRY),
        help="which Family 1 template to run",
    )
    parser.add_argument(
        "--agent",
        action="store_true",
        help="run the live AgentSolver (real LLM calls); skips the deterministic invariants",
    )
    parser.add_argument(
        "--model", default=None, help="override the agent model (default claude-sonnet-4-6)"
    )
    parser.add_argument(
        "--backend",
        default="messages-api",
        choices=("messages-api", "agent-sdk"),
        help="agent backend: messages-api (OAuth, Option X) or agent-sdk (subscription, Option W)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="agent-sdk turn budget (default 14; raise for long sequential tool-loops)",
    )
    parser.add_argument(
        "--max-budget-usd",
        type=float,
        default=None,
        help="agent-sdk per-rollout USD budget (default 6.0)",
    )
    args = parser.parse_args(argv)

    n = args.n if args.n is not None else (10 if args.agent else 20)
    template = templates.TEMPLATE_REGISTRY[args.template]
    if args.agent:
        return _run_agent(
            template,
            args.template,
            n,
            args.seed,
            args.model,
            args.backend,
            args.max_turns,
            args.max_budget_usd,
        )
    return _run_deterministic(template, args.template, n, args.seed)


if __name__ == "__main__":
    sys.exit(main())
