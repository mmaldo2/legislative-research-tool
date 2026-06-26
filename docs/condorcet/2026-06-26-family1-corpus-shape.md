# Family 1 — corpus-shape snapshot (2026-06-26)

First real corpus batch over all 8 Family 1 templates, post the refusal-proportionality fix and
the 5-lens review. Produced by `lab/batch.py` (precompute-once diagnostic) at **n=200 × seeds
42/43/44**, deterministic solvers only (no live agent). Raw traces + per-run summaries are
gitignored run artifacts; this is the curated snapshot. Reproduce with:

```
uv run python -m lab.batch --n 200 --seeds 42,43,44
```

**Every template, every solver, full distribution: invariants green** — oracle 100% / wrong-baseline
0% (attempted-but-wrong, never format-fail) / over-refuse fails every answerable item. `content_hash`
moved (templates.py changed); `grading_contract_hash` unchanged (no grader/scoring edit).

## Eligibility yield (gate funnel)

| Stage | Count |
|---|---|
| `vote_events` total | 13,848 |
| `complete_events` (records reconcile exactly to official counts) | 13,096 |
| `party_eligible_events` (complete ∩ completed-congress ∩ exactly-one-span) | 13,092 |
| `fully_complete_windows` ((congress, chamber), all-or-nothing) | **18** |
| completed congresses | 110–118 (9) |

The party pool is deep (13,092). The **window pool is 18** (9 completed congresses × 2 chambers) —
the binding ceiling for the window-based templates.

## Per-template distribution

| Template | grader | answerable | refusal ratio | gold shape (highlights) |
|---|---|---|---|---|
| `vote_lookup` | exact | 600 | 0.20 | yea 358 / nay 221 / not_voting 20 / present 1 |
| `tally` | fields | 600 | 0.20 | yea median 226; **margin min −344, 169 negative**; result 19 distinct strings |
| `closest_by_margin` | set_match | 54 ⚠️ | 0.18 | size always 5 (K); **only 18 distinct gold sets** (seed-independent) |
| `member_summary` | fields | 54 ⚠️ | 0.18 | yea up to 1296; other zero-frac 0.11 |
| `pairwise_agreement` | fields | 54 ⚠️ | 0.18 | agreements up to 1415; shared_events up to 1618 |
| `party_breakdown` | fields | 600 | 0.20 | yea median 160; nay zero-frac 0.25 (unanimous-yea parties) |
| `party_defection` | exact_int | 600 | 0.20 | median 2; **zero-frac 0.347**; max 116 |
| `crossed_party` | set_match | 600 | 0.20 | **empty-frac 0.347** (== defection zero-frac, by construction); max 116 |

⚠️ = saturated: answerable < n×seeds because the template draws from the 18-window pool.

## Findings

1. **Refusal imbalance — FIXED.** Window templates previously hit a 0.735 refusal ratio at scale
   (refusal count keyed off requested n, but answerable saturates at 18 windows). `_n_refusals(n)`
   now keys off actual answerable yield → ~0.2 across the whole family. (templates.py; this branch.)
2. **Window diversity ceiling (inherent, not a bug).** `closest_by_margin` gold is seed-independent,
   so its 54 instances are only **18 distinct gold sets**. member_summary/pairwise vary via the
   per-seed member pick. Future option if more diversity is wanted: vary K, sample multiple members
   per window, or move to per-session windows. Not blocking.
3. **`party_defection`/`crossed_party` are 34.7% zero-gold** (208/600). An "always answer 0 / ∅"
   baseline scores 34.7% on answer-correctness. But 0 defectors is a legitimate, common fact
   (unanimous party). Decision: **do NOT rebalance gold generation** — over-weighting contested
   events would bias the corpus off the true political distribution. Handle at training-sample time
   if needed. The `crossed_party` empty-frac matching the `party_defection` zero-frac exactly is a
   live confirmation of the `len(crossers) == min(yea,nay)` construction invariant.
4. **`tally.result` is the most brittle gold for the live agent** — 19 distinct verbose,
   case-sensitive strings ("Passed" vs "passed", "Agreed to" vs "agreed"). When answer extraction is
   built, the `result` field needs either the enum handed to the agent or a lenient match. Carried to
   the live-agent slice.

## Review hardening (5-lens panel, all "fix-then-ship", folded in)

- The frozen solve→grade→write loop is now a single shared chokepoint (`harness.solve_grade_write`)
  that both `run()` and `batch.py` call — no forked grading path.
- Load phase runs in ONE read-only `REPEATABLE READ` snapshot; a per-(template,seed) generator error
  rolls back so it can't poison the rest of the matrix.
- `_party_eligible_events` / `_fully_complete_windows` memoized for the run (the heavy gate query
  was running ~10×).
- `_int_buckets` gained a `<0` bucket (tally.margin is negative on every failed roll call); saturation
  is flagged loudly; the zero-answerable case no longer shows a vacuous green.
