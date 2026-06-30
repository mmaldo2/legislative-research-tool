"""Paired statistical analysis of a harness-lift matrix run (NON-FROZEN; reads traces only).

Consumes the per-cell trace JSONL named by `manifest_<run_id>.json` (written by
`ablation.run_matrix`) and computes the pre-registered headline: COST + RELIABILITY at accuracy
PARITY. Posture is ESTIMATION-FIRST (CIs are the result; p-values secondary) -- at N<=40 a
non-significant McNemar is near-guaranteed regardless of truth (Card et al. 2020), so we report a
confidence interval + an explicit equivalence margin for every claim.

Stats are hand-rolled (stdlib `math` + `numpy`; NO scipy/statsmodels) so every formula is visible
and pinned to a PUBLISHED oracle in the tests:
  - mcnemar_exact   : two-sided exact binomial on the discordant pairs (McNemar 1947; exact, since
                      b+c < 25 at our N). b=c=0 -> "not applicable" (the ceiling case), pivot to CI.
  - wilson          : score interval for a single proportion (Brown/Cai/DasGupta 2001; never Wald).
  - newcombe_paired : Newcombe (1998) method 10 paired-difference CI -- the PARITY interval.
  - boot_ratio_ci   : paired cluster bootstrap of a cost ratio (resample QUESTIONS, same index both
                      arms; Efron & Tibshirani 1993). THE single primary cost statistic.
Holm is DEFERRED (no family-wise "wins everywhere" claim is registered).

This file is in NEITHER frozen hash.
Run: PYTHONPATH=. uv run python -m lab.experiments.lift_analysis --run-id <id>
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from lab.harness import RUNS_DIR
from lab.manifest import RunManifest

# Fallback cost proxy ONLY when ResultMessage.total_cost_usd is null (OAuth/subscription). LIST
# prices, USD per token (input, output); verify against current pricing if the proxy ever fires.
# The merged Phase-3 pilots reported real total_cost_usd, so this is insurance, not the main path.
_PRICES = {
    "claude-haiku-4-5": (1.0e-6, 5.0e-6),
    "claude-sonnet-4-6": (3.0e-6, 15.0e-6),
    "claude-opus-4-8": (15.0e-6, 75.0e-6),
}


# --- stat primitives (PURE; oracle-pinned in tests) ------------------------------------------
def mcnemar_exact(b: int, c: int) -> tuple[float, str]:
    """Two-sided exact-binomial McNemar p on the discordant counts b, c. Returns (p, note).
    b=c=0 -> degenerate (0 discordant pairs); the test is uninformative, pivot to the CI."""
    n = b + c
    if n == 0:
        return 1.0, "degenerate: 0 discordant pairs -- not applicable, pivot to CI"
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5**n)
    return min(1.0, 2.0 * tail), "ok"


def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for x successes in n trials. (0,1) when n=0 (no information)."""
    if n == 0:
        return (0.0, 1.0)
    p = x / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def newcombe_paired(a: int, b: int, c: int, d: int, z: float = 1.96) -> tuple[float, float]:
    """Newcombe (1998) method-10 CI for the paired difference p1 - p2, where the 2x2 is
    [[a (A+B+), b (A+B-)], [c (A-B+), d (A-B-)]] so p1=(a+b)/n is arm A, p2=(a+c)/n is arm B.
    Square-and-add of the two Wilson intervals + the phi-hat correlation correction; degrades
    gracefully at the boundary (non-zero width at p_hat=1)."""
    n = a + b + c + d
    if n == 0:
        return (-1.0, 1.0)
    p1, p2 = (a + b) / n, (a + c) / n
    theta = p1 - p2
    l1, u1 = wilson(a + b, n, z)
    l2, u2 = wilson(a + c, n, z)
    denom = (a + b) * (c + d) * (a + c) * (b + d)
    phi = 0.0 if denom == 0 else (a * d - b * c) / math.sqrt(denom)
    lo = theta - math.sqrt((p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2)
    hi = theta + math.sqrt((u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2)
    return (max(-1.0, lo), min(1.0, hi))


def boot_ratio_ci(
    cost_a, cost_b, n_boot: int = 10000, seed: int = 0
) -> tuple[float, float, float] | None:
    """Paired cluster bootstrap of mean(cost_a)/mean(cost_b): resample QUESTION indices with
    replacement (SAME index set both arms), recompute the ratio, percentile 95% CI. Returns
    (lo, hi, median) or None if there is no usable paired cost data. The bootstrap reflects -- it
    cannot reduce -- the genuine N-driven uncertainty; report median+IQR alongside (skew)."""
    a = np.asarray(cost_a, dtype=float)
    b = np.asarray(cost_b, dtype=float)
    n = len(a)
    if n == 0:
        return None
    rng = np.random.default_rng(seed)
    ratios = np.empty(n_boot)
    drawn = 0
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        mb = b[idx].mean()
        if mb == 0:  # guard div-by-zero on a degenerate resample
            continue
        ratios[drawn] = a[idx].mean() / mb
        drawn += 1
    if drawn == 0:
        return None
    ratios = ratios[:drawn]
    return (
        float(np.percentile(ratios, 2.5)),
        float(np.percentile(ratios, 97.5)),
        float(np.median(ratios)),
    )


# --- trace loading + hash homogeneity --------------------------------------------------------
def load_run(run_id: str, runs_dir: Path = RUNS_DIR) -> tuple[list[dict], RunManifest]:
    """Load ONLY the cell files the run's manifest enumerates (deterministic provenance, not a
    timestamp glob). Asserts hash-homogeneity across every row: a mixed grading_contract_hash /
    content_hash / dataset_fingerprint means a stale/wrong file slipped in (gold is computed vs a
    MUTATING live DB) -> hard error."""
    manifest = RunManifest.load(run_id, runs_dir)
    rows: list[dict] = []
    for name in manifest.cell_files:
        path = runs_dir / name
        with open(path, encoding="utf-8") as fh:
            rows.extend(json.loads(line) for line in fh if line.strip())
    if not rows:
        raise RuntimeError(
            f"run {run_id!r}: manifest lists no rows ({len(manifest.cell_files)} files)"
        )
    sigs = {
        (
            r["grading_contract_hash"],
            r["content_hash"],
            json.dumps(r["dataset_fingerprint"], sort_keys=True),
        )
        for r in rows
    }
    if len(sigs) != 1:
        raise RuntimeError(
            f"run {run_id!r}: {len(sigs)} distinct (contract/content/fingerprint) signatures in "
            f"the loaded rows -- a stale or cross-run file is mixed in; refusing to analyze."
        )
    return rows, manifest


# APPARATUS failures (sandbox down / OOM / SDK-transport / auth / CREDIT exhaustion) -- NOT a
# capability outcome. Dropped ENTIRELY (not even counted against completion), unlike a `timeout` or
# `error_max_turns` which are legitimate non-completions the agent owns.
_INFRA_SUBTYPES = {"sandbox_infra", "agent_infra"}


# --- pure aggregation helpers (decomposed for testability) ------------------------------------
def _cell_key(row: dict) -> tuple[str, str, str]:
    return (row["template_id"], row["policy"]["model"], row["policy"]["surface"])


def _is_infra(row: dict) -> bool:
    return row.get("result_subtype") in _INFRA_SUBTYPES


def _rep_success(row: dict) -> bool:
    return row.get("result_subtype") == "success"


def _rep_correct(row: dict) -> bool:
    return _rep_success(row) and row["verdict"]["subscores"].get("answer_correct") == 1.0


def pair_by_instance(rows: list[dict]) -> dict[tuple[str, str, str], dict[str, list[dict]]]:
    """cells[(template, model, surface)][instance_id] -> [rep rows]. ANSWERABLE arm only (the
    refusal twins are filtered before cells run in run_ablation; split on the row's is_refusal
    field, never an id substring)."""
    cells: dict[tuple[str, str, str], dict[str, list[dict]]] = {}
    for r in rows:
        if r.get("is_refusal") or _is_infra(r):  # drop refusal twins + apparatus failures entirely
            continue
        cells.setdefault(_cell_key(r), {}).setdefault(r["instance_id"], []).append(r)
    return cells


def instance_outcome(reps: list[dict]) -> dict:
    """Aggregate one instance's k reps in one cell. Majority-vote correctness (strict majority;
    a post-exclusion tie -> INCORRECT, the conservative rule). `cond_correct` is None when no rep
    succeeded (the instance is then outside the conditional/paired population)."""
    total = len(reps)
    successes = [r for r in reps if _rep_success(r)]
    n_succ = len(successes)
    cond_correct = None
    if successes:
        c = sum(_rep_correct(r) for r in successes)
        cond_correct = c > n_succ / 2  # strict majority; 1-1 tie -> False (incorrect)
    itt_c = sum(1 for r in reps if _rep_correct(r))  # non-success reps count as wrong
    itt_correct = itt_c > total / 2
    flipped = (0 < sum(_rep_correct(r) for r in successes) < n_succ) if n_succ >= 2 else None
    return {
        "total": total,
        "n_succ": n_succ,
        "cond_correct": cond_correct,
        "itt_correct": itt_correct,
        "flipped": flipped,
    }


def build_2x2(out_a: dict[str, dict], out_b: dict[str, dict], *, key: str) -> tuple[int, ...]:
    """The paired 2x2 (a,b,c,d) for arm A vs arm B over their COMMON instances, using per-instance
    outcome field `key` ("cond_correct" -> conditional/complete-case population only; "itt_correct"
    -> the full intent-to-treat population). a=A+B+, b=A+B-, c=A-B+, d=A-B-."""
    common = set(out_a) & set(out_b)
    a = b = c = d = 0
    for iid in common:
        ca, cb = out_a[iid][key], out_b[iid][key]
        if key == "cond_correct" and (ca is None or cb is None):
            continue  # conditional: only instances BOTH arms answered (>=1 success rep)
        ca, cb = bool(ca), bool(cb)
        if ca and cb:
            a += 1
        elif ca and not cb:
            b += 1
        elif not ca and cb:
            c += 1
        else:
            d += 1
    return a, b, c, d


def rollout_cost(row: dict) -> tuple[float | None, str]:
    """A rollout's cost: real `total_cost_usd` if present, else a token x list-price proxy, else
    missing. Returns (cost, source) where source in {real, proxy, missing}."""
    c = row.get("cost")
    if c is not None:
        return float(c), "real"
    it, ot = row.get("input_tokens"), row.get("output_tokens")
    price = _PRICES.get(row["policy"]["model"])
    if it is not None and ot is not None and price is not None:
        return it * price[0] + ot * price[1], "proxy"
    return None, "missing"


def instance_cost(reps: list[dict]) -> float | None:
    """Per-instance cost = mean of the reps' usable rollout costs; None if every rep is missing."""
    vals = [c for c, _src in (rollout_cost(r) for r in reps) if c is not None]
    return sum(vals) / len(vals) if vals else None


def cost_vectors(
    inst_reps_a: dict[str, list[dict]], inst_reps_b: dict[str, list[dict]]
) -> tuple[list[float], list[float], float]:
    """PAIRWISE-aligned per-instance cost vectors for two arms over their common instances: an
    instance is kept ONLY if BOTH arms have a usable cost (else the shared-index bootstrap is
    meaningless). Returns (cost_a, cost_b, coverage) where coverage = kept / common."""
    common = sorted(set(inst_reps_a) & set(inst_reps_b))
    ca: list[float] = []
    cb: list[float] = []
    for iid in common:
        x, y = instance_cost(inst_reps_a[iid]), instance_cost(inst_reps_b[iid])
        if x is not None and y is not None:
            ca.append(x)
            cb.append(y)
    coverage = (len(ca) / len(common)) if common else 0.0
    return ca, cb, coverage


def _classify_row(row: dict) -> str:
    """The 3-rate + error partition for ONE rollout, mirroring ablation.classify (read from the
    persisted verdict/subtype rather than the live flag)."""
    if not _rep_success(row):
        return "errored"
    sub = row["verdict"]["subscores"]
    if sub.get("format_valid") == 0.0:
        return "format_fail"
    if sub.get("decision_correct") == 0.0:
        return "over_refusal"
    return "correct" if sub.get("answer_correct") == 1.0 else "hallucination"


def arm_summary(inst_reps: dict[str, list[dict]]) -> dict:
    """Per-arm reliability + 3-rate over a cell's instances/rollouts: completion rate (gradeable
    rollouts / total, Wilson CI), flip-rate (non-unanimous answered instances / N), per-rollout
    bucket counts, and a cost-source tally."""
    rollouts = [r for reps in inst_reps.values() for r in reps]
    total = len(rollouts)
    gradeable = sum(_rep_success(r) for r in rollouts)
    outs = [instance_outcome(reps) for reps in inst_reps.values()]
    flippable = [o for o in outs if o["flipped"] is not None]
    buckets: dict[str, int] = {}
    for r in rollouts:
        buckets[_classify_row(r)] = buckets.get(_classify_row(r), 0) + 1
    sources: dict[str, int] = {}
    for r in rollouts:
        _c, src = rollout_cost(r)
        sources[src] = sources.get(src, 0) + 1
    return {
        "n_instances": len(inst_reps),
        "rollouts": total,
        "completion": gradeable / total if total else 0.0,
        "completion_ci": wilson(gradeable, total),
        "flip_rate": (sum(o["flipped"] for o in flippable) / len(flippable)) if flippable else 0.0,
        "buckets": buckets,
        "cost_sources": sources,
    }


# --- orchestration ----------------------------------------------------------------------------
def _comparisons(arms: set[tuple[str, str]]) -> list[tuple[str, tuple, tuple]]:
    """The arm-pairs to report, driven by which (model, surface) cells are present (robust to a
    smoke subset). Lift (secondary, model held fixed): m/ours vs m/web. Punch-up (primary family):
    m/ours vs opus/web (F+T). Each emitted only if BOTH arms ran."""
    out: list[tuple[str, tuple, tuple]] = []
    models = sorted({m for m, _s in arms})
    ft = ("claude-opus-4-8", "web")
    for m in models:
        sh, st = (m, "ours"), (m, "web")
        if sh in arms and st in arms:
            out.append(("lift_SH_vs_ST", sh, st))
        if sh in arms and ft in arms and sh != ft:
            out.append(("punchup_SH_vs_FT", sh, ft))
    return out


def _pair_report(cells, template, arm_a, arm_b, *, delta, n_boot, seed) -> dict:
    """All metrics for one (arm_a vs arm_b) comparison within a template."""
    reps_a = cells[(template, *arm_a)]
    reps_b = cells[(template, *arm_b)]
    out_a = {i: instance_outcome(r) for i, r in reps_a.items()}
    out_b = {i: instance_outcome(r) for i, r in reps_b.items()}
    # set-equality is the design invariant (instances generated once, reused); report any singleton.
    only_a, only_b = set(out_a) - set(out_b), set(out_b) - set(out_a)
    cond = build_2x2(out_a, out_b, key="cond_correct")
    itt = build_2x2(out_a, out_b, key="itt_correct")
    ca, cb, cov = cost_vectors(reps_a, reps_b)
    boot = boot_ratio_ci(cb, ca, n_boot=n_boot, seed=seed)  # ratio = B/A (>1 => arm A cheaper)
    med = float(np.median(np.asarray(cb) / np.asarray(ca))) if ca else None
    cond_ci = newcombe_paired(*cond)
    itt_ci = newcombe_paired(*itt)
    return {
        "arm_a": list(arm_a),
        "arm_b": list(arm_b),
        "singletons": {"only_a": sorted(only_a), "only_b": sorted(only_b)},
        "conditional": {
            "table_abcd": list(cond),
            "mcnemar_p": mcnemar_exact(cond[1], cond[2]),
            "diff_ci_A_minus_B": cond_ci,
            "parity_within_delta": abs(cond_ci[0]) <= delta and abs(cond_ci[1]) <= delta,
        },
        "itt": {
            "table_abcd": list(itt),
            "mcnemar_p": mcnemar_exact(itt[1], itt[2]),
            "diff_ci_A_minus_B": itt_ci,
        },
        "cost_ratio_B_over_A": {  # >1 => arm A (the ours/harness arm) is cheaper
            "bootstrap_ci_median": boot,
            "per_instance_median": med,
            "pairwise_coverage": cov,
            "n_paired": len(ca),
        },
        "delta": delta,
    }


def analyze(
    run_id: str,
    runs_dir: Path = RUNS_DIR,
    *,
    delta: float = 0.10,
    n_boot: int = 10000,
    bootstrap_seed: int = 0,
) -> dict:
    """The full report: load the run, group into cells, and per template emit per-arm summaries +
    the lift/punch-up comparisons. Writes a self-describing lift_analysis_<run_id>.json."""
    rows, manifest = load_run(run_id, runs_dir)
    cells = pair_by_instance(rows)
    templates = sorted({t for t, _m, _s in cells})
    report: dict = {
        "run_id": run_id,
        "prereg_doc_sha": manifest.prereg_doc_sha,
        "grading_contract_hash": rows[0]["grading_contract_hash"],
        "content_hash": rows[0]["content_hash"],
        "dataset_fingerprint": rows[0]["dataset_fingerprint"],
        "rollout_seed": manifest.rollout_seed,
        "bootstrap_seed": bootstrap_seed,
        "delta": delta,
        "templates": {},
    }
    for template in templates:
        arms = {(m, s) for t, m, s in cells if t == template}
        report["templates"][template] = {
            "arms": {f"{m}|{s}": arm_summary(cells[(template, m, s)]) for m, s in sorted(arms)},
            "comparisons": [
                {
                    "kind": kind,
                    **_pair_report(
                        cells, template, a, b, delta=delta, n_boot=n_boot, seed=bootstrap_seed
                    ),
                }
                for kind, a, b in _comparisons(arms)
            ],
        }
    out_path = runs_dir / f"lift_analysis_{run_id}.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def _print_report(report: dict) -> None:
    print(f"\n=== LIFT ANALYSIS [{report['run_id']}] (delta={report['delta']}) ===")
    print(
        f"  prereg={report['prereg_doc_sha']} contract={report['grading_contract_hash'][:12]} "
        f"content={report['content_hash'][:12]} boot_seed={report['bootstrap_seed']}"
    )
    for template, t in report["templates"].items():
        print(f"\n  [{template}]")
        for arm, s in t["arms"].items():
            print(
                f"    {arm:28} compl={_pct(s['completion'])} flip={_pct(s['flip_rate'])} "
                f"buckets={s['buckets']} cost_src={s['cost_sources']}"
            )
        for cmp in t["comparisons"]:
            a, b = "|".join(cmp["arm_a"]), "|".join(cmp["arm_b"])
            cd = cmp["conditional"]
            cr = cmp["cost_ratio_B_over_A"]
            boot = cr["bootstrap_ci_median"]
            boot_s = f"{boot[2]:.2f}x [{boot[0]:.2f}, {boot[1]:.2f}]" if boot else "n/a"
            ci = cd["diff_ci_A_minus_B"]
            print(f"    {cmp['kind']}: {a} vs {b}")
            print(
                f"      acc(cond) 2x2={cd['table_abcd']} mcnemar_p={cd['mcnemar_p'][0]:.3f} "
                f"diff_CI=[{ci[0]:+.3f},{ci[1]:+.3f}] parity<=d={cd['parity_within_delta']}"
            )
            print(
                f"      cost ratio(B/A) bootstrap={boot_s} (>1 => {a} cheaper) "
                f"coverage={_pct(cr['pairwise_coverage'])} n={cr['n_paired']}"
            )
            if cmp["singletons"]["only_a"] or cmp["singletons"]["only_b"]:
                print(f"      WARNING singleton instances (not paired): {cmp['singletons']}")


def main(argv=None) -> int:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description="Paired analysis of a harness-lift matrix run")
    p.add_argument("--run-id", required=True)
    p.add_argument("--delta", type=float, default=0.10, help="parity equivalence margin")
    p.add_argument("--bootstrap-iters", type=int, default=10000)
    p.add_argument("--bootstrap-seed", type=int, default=0)
    args = p.parse_args(argv)
    report = analyze(
        args.run_id,
        delta=args.delta,
        n_boot=args.bootstrap_iters,
        bootstrap_seed=args.bootstrap_seed,
    )
    _print_report(report)
    print(f"\n  wrote {RUNS_DIR / f'lift_analysis_{args.run_id}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
