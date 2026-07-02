"""Hermetic tests for the paired lift analysis (no DB, no SDK, no network).

Two layers:
  - the stat primitives, pinned to PUBLISHED / hand-verifiable oracles (the asymmetric Newcombe case
    catches a phi-sign error; the McNemar values are exact-binomial closed forms);
  - the trace-reading pipeline on a synthetic JSONL fixture: pairing, hash-homogeneity, the
    conditional-vs-ITT split, the post-exclusion tie rule, pairwise cost exclusion, and the pinned
    report-JSON shape.
"""

import json

import pytest

from lab.experiments import lift_analysis as la
from lab.manifest import RunManifest


# --- stat primitives --------------------------------------------------------------------------
def test_mcnemar_exact_oracles():
    assert la.mcnemar_exact(4, 0)[0] == pytest.approx(0.125)  # 2*C(4,0)*0.5^4
    assert la.mcnemar_exact(8, 0)[0] == pytest.approx(2 / 256)  # 2*0.5^8
    assert la.mcnemar_exact(3, 3)[0] == 1.0  # symmetric -> clips to 1
    p, note = la.mcnemar_exact(0, 0)
    assert p == 1.0 and "degenerate" in note  # the ceiling case is flagged, not fabricated


def test_mcnemar_power_wall():
    # cannot reach p<0.05 until b+c >= 6 (2*0.5^6 = 0.03125) -- documents the small-N limit
    assert la.mcnemar_exact(5, 0)[0] > 0.05
    assert la.mcnemar_exact(6, 0)[0] < 0.05


def test_wilson_oracles():
    assert la.wilson(0, 0) == (0.0, 1.0)  # no information
    lo, hi = la.wilson(1, 1)  # ceiling p_hat=1 -> NON-zero width (Wald would give width 0)
    assert hi == 1.0 and 0.0 < lo < 1.0
    lo, hi = la.wilson(5, 10)
    assert lo < 0.5 < hi  # symmetric around 0.5


def test_newcombe_published_example():
    # Newcombe (1998) method 10, the worked example: a=10,b=4,c=1,d=5 -> ~[-0.056, +0.336].
    # The asymmetry (theta=0.15, phi~0.5) makes this discriminate a sign error in the correction.
    lo, hi = la.newcombe_paired(10, 4, 1, 5)
    assert lo == pytest.approx(-0.056, abs=0.004)
    assert hi == pytest.approx(0.336, abs=0.004)


def test_newcombe_properties():
    # symmetric table (b==c) -> theta=0 -> CI symmetric about 0
    lo, hi = la.newcombe_paired(5, 3, 3, 5)
    assert lo == pytest.approx(-hi, abs=1e-9)
    # boundary (a=0 -> a margin's factor zero -> phi=0 path) must not crash + stays in [-1,1]
    lo, hi = la.newcombe_paired(0, 4, 0, 6)
    assert -1.0 <= lo <= hi <= 1.0
    # fully degenerate
    assert la.newcombe_paired(0, 0, 0, 0) == (-1.0, 1.0)
    # both arms perfect (a=n) -> theta 0, still a valid (non-NaN) interval
    lo, hi = la.newcombe_paired(10, 0, 0, 0)
    assert lo <= 0.0 <= hi


def test_boot_ratio_deterministic_and_guards():
    # A clearly cheaper than B -> ratio B/A > 1; same seed -> identical CI (reproducible)
    cost_a = [0.10, 0.12, 0.11, 0.09]
    cost_b = [0.40, 0.42, 0.38, 0.41]
    r1 = la.boot_ratio_ci(cost_b, cost_a, n_boot=2000, seed=7)
    r2 = la.boot_ratio_ci(cost_b, cost_a, n_boot=2000, seed=7)
    assert r1 == r2 and r1[2] > 2.0  # median ratio ~ 0.40/0.105 ~ 3.8
    assert la.boot_ratio_ci([], [], n_boot=10) is None  # empty -> None
    assert la.boot_ratio_ci([0.0, 0.0], [1.0, 1.0], n_boot=50)[2] == 0.0  # mean(A)=0 ok (num)


# --- instance aggregation (the tie rule + conditional/ITT) ------------------------------------
def _rep(subtype="success", correct=1.0):
    return {"result_subtype": subtype, "verdict": {"subscores": {"answer_correct": correct}}}


def test_instance_outcome_tie_and_exclusion():
    # 3 success reps, 2 correct -> majority correct
    o = la.instance_outcome([_rep(), _rep(), _rep(correct=0.0)])
    assert o["cond_correct"] is True and o["itt_correct"] is True and o["flipped"] is True
    # 2 success reps split 1-1 (post-exclusion tie) -> INCORRECT (conservative rule)
    o = la.instance_outcome([_rep(), _rep(correct=0.0)])
    assert o["cond_correct"] is False
    # no success rep -> outside the conditional population, ITT scores wrong
    o = la.instance_outcome([_rep("error_max_turns"), _rep(None)])
    assert o["cond_correct"] is None and o["itt_correct"] is False and o["n_succ"] == 0
    # a truncation among reps lowers ITT but not conditional (1 of 2 success, that one correct)
    o = la.instance_outcome([_rep(), _rep("error_max_turns")])
    assert o["cond_correct"] is True and o["itt_correct"] is False  # 1/2 not a majority of total


def test_build_2x2_conditional_drops_unanswered():
    out_a = {
        "i1": {"cond_correct": True, "itt_correct": True},
        "i2": {"cond_correct": None, "itt_correct": False},
    }
    out_b = {
        "i1": {"cond_correct": False, "itt_correct": False},
        "i2": {"cond_correct": True, "itt_correct": True},
    }
    # conditional: i2 dropped (A is None) -> only i1: A+ B- -> b=1
    assert la.build_2x2(out_a, out_b, key="cond_correct") == (0, 1, 0, 0)
    # ITT: both kept -> i1 A+B- (b), i2 A-B+ (c)
    assert la.build_2x2(out_a, out_b, key="itt_correct") == (0, 1, 1, 0)


def test_rollout_cost_real_then_proxy():
    row = {"cost": 0.5, "policy": {"model": "claude-haiku-4-5"}}
    assert la.rollout_cost(row) == (0.5, "real")
    row = {
        "cost": None,
        "input_tokens": 1000,
        "output_tokens": 100,
        "policy": {"model": "claude-haiku-4-5"},
    }
    c, src = la.rollout_cost(row)
    assert src == "proxy" and c == pytest.approx(1000 * 1e-6 + 100 * 5e-6)
    row = {"cost": None, "input_tokens": None, "output_tokens": None, "policy": {"model": "x"}}
    assert la.rollout_cost(row) == (None, "missing")


def test_cost_vectors_pairwise_exclusion():
    reps_a = {
        "i1": [{"cost": 0.1, "policy": {"model": "m"}}],
        "i2": [{"cost": 0.2, "policy": {"model": "m"}}],
    }
    reps_b = {
        "i1": [{"cost": 0.3, "policy": {"model": "m"}}],
        "i2": [
            {"cost": None, "input_tokens": None, "output_tokens": None, "policy": {"model": "m"}}
        ],
    }  # i2 missing in B -> dropped from BOTH
    ca, cb, cov = la.cost_vectors(reps_a, reps_b)
    assert ca == [0.1] and cb == [0.3] and cov == 0.5


# --- end-to-end pipeline over a synthetic JSONL fixture ---------------------------------------
def _trace_row(
    iid,
    model,
    surface,
    *,
    subtype="success",
    ac=1.0,
    dc=1.0,
    fv=1.0,
    cost=0.1,
    refusal=False,
    ch="C1",
    coh="CT1",
    raw="",
):
    return {
        "trace_schema_version": "v1",
        "instance_id": iid,
        "template_id": "lift.t",
        "tier": "C",
        "params": {},
        "prompt": "p",
        "gold": {},
        "grader": "fields",
        "is_refusal": refusal,
        "refusal_reason": None,
        "policy": {"name": "agent", "backend": "agent-sdk", "surface": surface, "model": model},
        "solver_kind": "agent",
        "answer": {},
        "trajectory": [],
        "raw": raw,
        "verdict": {
            "passed": True,
            "score": 1.0,
            "feedback": "",
            "subscores": {
                "format_valid": fv,
                "decision_correct": dc,
                "answer_correct": ac,
                "grounded": None,
            },
        },
        "seed": 42,
        "engine": "postgres",
        "grading_contract_hash": ch,
        "content_hash": coh,
        "dataset_fingerprint": {"vote_events": 1},
        "latency_ms": 1.0,
        "input_tokens": None,
        "output_tokens": None,
        "cost": cost,
        "result_subtype": subtype,
    }


def _write_run(tmp_path, run_id, files):
    names = []
    for fname, rows in files:
        (tmp_path / fname).write_text("".join(json.dumps(r) + "\n" for r in rows))
        names.append(fname)
    RunManifest(
        run_id=run_id,
        params={},
        rollout_seed=42,
        grading_contract_hash="C1",
        content_hash="CT1",
        dataset_fingerprint={"vote_events": 1},
        cell_files=names,
    ).save(tmp_path)


def test_analyze_end_to_end(tmp_path):
    mdl = "claude-haiku-4-5"
    # ours: both instances correct & cheap; web: i1 correct (pricey), i2 TRUNCATED (non-success)
    ours = [
        _trace_row("lift.t:1", mdl, "ours", cost=0.1),
        _trace_row("lift.t:2", mdl, "ours", cost=0.1),
    ]
    web = [
        _trace_row("lift.t:1", mdl, "web", cost=0.5),
        _trace_row("lift.t:2", mdl, "web", subtype="error_max_turns", ac=0.0, cost=0.5),
    ]
    _write_run(
        tmp_path,
        "t0",
        [("ablation_t0_haiku_ours_all_x.jsonl", ours), ("ablation_t0_haiku_web_all_x.jsonl", web)],
    )
    rep = la.analyze("t0", runs_dir=tmp_path, n_boot=500, bootstrap_seed=1)

    t = rep["templates"]["lift.t"]
    # web completion 1/2 (i2 truncated); ours 2/2
    assert t["arms"][f"{mdl}|web"]["completion"] == 0.5
    assert t["arms"][f"{mdl}|ours"]["completion"] == 1.0
    cmp = next(c for c in t["comparisons"] if c["kind"] == "lift_SH_vs_ST")
    # conditional: only i1 paired (web i2 unanswered) -> both correct -> a=1
    assert cmp["conditional"]["table_abcd"] == [1, 0, 0, 0]
    # ITT: i1 both correct (a), i2 ours-correct web-wrong (b) -> [1,1,0,0]
    assert cmp["itt"]["table_abcd"] == [1, 1, 0, 0]
    # cost ratio web/ours ~ 0.5/0.1 = 5x (>1 => ours cheaper); coverage 100% (both arms have cost)
    assert cmp["cost_ratio_B_over_A"]["per_instance_median"] == pytest.approx(5.0)
    assert cmp["cost_ratio_B_over_A"]["pairwise_coverage"] == 1.0
    # the artifact is written + self-describing
    written = json.loads((tmp_path / "lift_analysis_t0.json").read_text())
    assert written["grading_contract_hash"] == "C1" and written["bootstrap_seed"] == 1


def test_analyze_report_json_keys_pinned(tmp_path):
    """The analysis JSON IS the pre-reg result record -- pin its top-level shape so a refactor can't
    silently reshape the published artifact."""
    mdl = "claude-haiku-4-5"
    _write_run(
        tmp_path,
        "t1",
        [
            ("ablation_t1_haiku_ours_all_x.jsonl", [_trace_row("lift.t:1", mdl, "ours")]),
            ("ablation_t1_haiku_web_all_x.jsonl", [_trace_row("lift.t:1", mdl, "web")]),
        ],
    )
    rep = la.analyze("t1", runs_dir=tmp_path, n_boot=100)
    assert set(rep) == {
        "run_id",
        "prereg_doc_sha",
        "grading_contract_hash",
        "content_hash",
        "dataset_fingerprint",
        "rollout_seed",
        "bootstrap_seed",
        "delta",
        "templates",
    }


def test_load_run_rejects_mixed_hashes(tmp_path):
    mdl = "claude-haiku-4-5"
    _write_run(
        tmp_path,
        "bad",
        [
            ("ablation_bad_a.jsonl", [_trace_row("lift.t:1", mdl, "ours", coh="CT1")]),
            (
                "ablation_bad_b.jsonl",
                [_trace_row("lift.t:2", mdl, "ours", coh="CT2")],
            ),  # different!
        ],
    )
    with pytest.raises(RuntimeError, match="signatures"):
        la.load_run("bad", runs_dir=tmp_path)


def test_load_run_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match="no manifest"):
        la.load_run("nope", runs_dir=tmp_path)


def test_load_run_rejects_foreign_model_drift(tmp_path):
    """A genuine served-model swap (e.g. a freshly-released Sonnet 5 aliased in) must HARD-ERROR the
    analysis, never be silently averaged into the pre-registered comparison."""
    mdl = "claude-sonnet-4-6"
    marker = "<MODEL_DRIFT requested=claude-sonnet-4-6 served=['claude-sonnet-5-20260601']>"
    _write_run(
        tmp_path,
        "drift",
        [
            ("ablation_drift_a.jsonl", [_trace_row("lift.t:1", mdl, "ours")]),
            (
                "ablation_drift_b.jsonl",
                [_trace_row("lift.t:2", mdl, "ours", subtype="model_drift", raw=marker)],
            ),
        ],
    )
    with pytest.raises(RuntimeError, match="FOREIGN model"):
        la.load_run("drift", runs_dir=tmp_path)


def test_load_run_unparseable_drift_fails_closed(tmp_path):
    """A `model_drift` row whose marker can't be parsed is treated as REAL drift (fail closed) --
    the benign reclassification must never be reachable without a verified served set."""
    mdl = "claude-sonnet-4-6"
    _write_run(
        tmp_path,
        "drift",
        [("ablation_drift_a.jsonl", [_trace_row("lift.t:1", mdl, "ours", subtype="model_drift")])],
    )
    with pytest.raises(RuntimeError, match="MODEL-DRIFT|FOREIGN"):
        la.load_run("drift", runs_dir=tmp_path)


def test_load_run_tolerates_benign_drift_and_restores_subtype(tmp_path):
    """The guard MIS-FIRES on an SDK `<synthetic>` sentinel and on the pinned alias's dated snapshot
    -- there the pinned model DID serve the (correctly graded) rollout, so the row is restored to
    its true subtype and analyzed, not blocked."""
    mdl = "claude-sonnet-4-6"
    synthetic = (
        "<MODEL_DRIFT requested=claude-sonnet-4-6 "
        "served=['<synthetic>', 'claude-sonnet-4-6']>"
    )
    snapshot = "<MODEL_DRIFT requested=claude-sonnet-4-6 served=['claude-sonnet-4-6-20250930']>"
    _write_run(
        tmp_path,
        "benign",
        [
            (
                "ablation_benign_a.jsonl",
                [_trace_row("lift.t:1", mdl, "ours", subtype="model_drift", raw=synthetic)],
            ),
            (
                "ablation_benign_b.jsonl",
                [_trace_row("lift.t:2", mdl, "ours", subtype="model_drift", raw=snapshot)],
            ),
        ],
    )
    rows, _ = la.load_run("benign", runs_dir=tmp_path)  # does NOT raise
    # both benign drifts restored to `success` (they completed with a passing verdict)
    assert [r["result_subtype"] for r in rows] == ["success", "success"]
    assert all(la._rep_correct(r) for r in rows)


def test_refusal_rows_excluded_from_pairing(tmp_path):
    mdl = "claude-haiku-4-5"
    rows = [
        _trace_row("lift.t:1", mdl, "ours"),
        _trace_row("lift.t:refusal:NX", mdl, "ours", refusal=True),
    ]
    cells = la.pair_by_instance(rows)
    # the refusal twin is filtered; only the answerable instance is in the cell
    assert set(cells[("lift.t", mdl, "ours")]) == {"lift.t:1"}


def test_infra_rollouts_dropped_entirely():
    """An apparatus failure (sandbox/SDK/credit) is dropped ENTIRELY -- not counted against
    completion -- unlike a `timeout`, a legitimate non-completion the agent owns."""
    mdl = "claude-sonnet-4-6"
    rows = [
        _trace_row("lift.t:1", mdl, "web", subtype="success", ac=1.0),
        _trace_row("lift.t:2", mdl, "web", subtype="agent_infra", ac=0.0),  # credit/SDK -> dropped
        _trace_row("lift.t:3", mdl, "web", subtype="sandbox_infra", ac=0.0),  # sandbox -> dropped
        _trace_row("lift.t:4", mdl, "web", subtype="timeout", ac=0.0),  # KEPT (non-completion)
    ]
    cell = la.pair_by_instance(rows)[("lift.t", mdl, "web")]
    assert set(cell) == {"lift.t:1", "lift.t:4"}  # the two infra rollouts are gone
    summ = la.arm_summary(cell)
    # completion = 1 success / 2 kept rollouts (timeout counts against it; infra does not)
    assert summ["rollouts"] == 2 and summ["completion"] == 0.5
