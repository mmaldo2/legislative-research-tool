"""A4 + A4b: the run.py --agent code path (skips invariants) and the name-collision diagnostic.
`run` is mocked so no live LLM / DB call happens; the collision logic is tested with a mocked conn.
"""

from unittest.mock import Mock

import lab.run as run_mod
from lab.graders import REFUSAL, grade
from lab.harness import Instance


def _row(answer, gold="yea", grader="exact", is_refusal=False, iid="i1"):
    return (iid, is_refusal, grade(grader, gold, answer, is_refusal=is_refusal))


def test_agent_branch_skips_invariants_and_defaults_n_10(monkeypatch):
    captured = {}

    def fake_run(template, solvers, n, seed, valid):
        captured["n"] = n
        captured["names"] = [s.name for s in solvers]
        return {"agent": [_row("yea")]}  # the agent run has NO oracle/wrong/over keys

    monkeypatch.setattr(run_mod, "run", fake_run)
    monkeypatch.setattr(run_mod, "_name_collisions", lambda *a: set())
    rc = run_mod.main(["--agent", "--template", "vote_lookup"])  # no --n
    assert rc == 0  # must NOT KeyError on results["oracle"]
    assert captured["n"] == 10  # agent default
    assert captured["names"] == ["agent"]


def test_deterministic_branch_runs_invariants(monkeypatch):
    captured = {}

    def fake_run(template, solvers, n, seed, valid):
        captured["n"] = n
        return {
            "oracle": [_row("yea")],  # correct -> pass
            "wrong-baseline": [_row("nay")],  # attempted-but-wrong (decision 1, answer 0)
            "over-refuse": [_row(REFUSAL)],  # over-refusal (decision 0)
        }

    monkeypatch.setattr(run_mod, "run", fake_run)
    rc = run_mod.main(["--template", "vote_lookup", "--n", "5"])
    assert rc == 0  # invariants hold
    assert captured["n"] == 5  # deterministic default path honours --n


def _vl(iid, eid, pid):
    return Instance(
        instance_id=iid,
        template_id="family1.vote_lookup",
        tier="C",
        params={"vote_event_id": eid, "person_id": pid},
        prompt="q",
        gold="yea",
        grader="exact",
        is_refusal=False,
    )


def test_name_collisions_flags_only_shared_names():
    refusal = Instance(
        instance_id="r",
        template_id="family1.vote_lookup",
        tier="C",
        params={"vote_event_id": "e1", "person_id": "NX"},
        prompt="q",
        gold=REFUSAL,
        grader="refusal_correct",
        is_refusal=True,
    )
    insts = [_vl("a", "e1", "p1"), _vl("b", "e1", "p2"), refusal]  # refusal is skipped
    counts = iter([(2,), (1,)])  # p1's name is shared (2), p2 is unique (1)
    cur = Mock()
    cur.fetchone = Mock(side_effect=lambda: next(counts))
    conn = Mock(cursor=Mock(return_value=cur))
    assert run_mod.vote_lookup_name_collisions(conn, insts) == {"a"}
