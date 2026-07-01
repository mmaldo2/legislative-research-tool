---
title: "feat(lab): harness-lift ablation over the existing suite (S+H vs S+T vs F+T)"
type: feat
status: active
date: 2026-06-29
origin: docs/scopes/2026-06-29-harness-lift-ablation-scope.md
---

# feat(lab): harness-lift ablation (S+H vs S+T vs F+T)

## Overview
Measure **harness lift** on the existing task suite per [[project_condorcet_experimental_design]]:
the controlled ablation **S+H − S+T** (model fixed; isolates the harness) plus the **S+H ≥ F+T**
cost/capability headline (small+harness ≥ frontier+honest-tools). The honest baseline (web + code)
shipped (PR #48). This plan IS the **pre-registration** — suite, arms, models, metric, and tier
cutoff are fixed here before the full run, which is the core bias defense.

## The crux: ablation-fairness (public-resolvability)
For the comparison to be valid AND defensible, each task's **question and answer must both be
expressible in public terms** — otherwise the web arm is unfairly handicapped by *our* id-space, not
by capability:
- **Question** must be resolvable from public info (member NAME, public bill id, congress/chamber/
  date) — NOT our internal `vote_event_id`/`person_id`/`bill_id` (the web arm can't map those to a
  public page).
- **Answer** must be public-expressible (a count, a party, an option) — NOT a set of OUR internal
  ids (the web arm finds "Roll Call 145" on the Clerk site, never our `vote_event_id`).

Auditing the suite against this:
- **READY (public Q + public A):** `member_summary` (a named member's yea/nay/other counts in a
  congress/chamber) and `pairwise_agreement` (agreement count between two named members). Both are
  **counts over many records** — exactly where the harness's completeness/scale value should appear
  (the web arm must find + tally a whole session's votes by scraping; H pulls them exactly).
- **Fair after re-phrasing the EVENT publicly (count answers, internal-id questions):** `tally`,
  `party_breakdown`, `party_defection`. (Defer — touches templates.py / content_hash.)
- **Needs a public answer id-space (set-of-internal-id answers):** `covoting`, `crossed_party`,
  `closest_by_margin`, `cite_record_id`, `cosponsored_and_voted_against`. (Defer.)
- **Control / low-lift floor:** `vote_lookup` (a lookup — web should match; expect ~0 lift).

**So the first lift run targets `member_summary` + `pairwise_agreement`** (ready, and the right
computation-at-scale shape). The re-phrasings are a later scoped expansion, not this plan.

## Arms & models (pre-registered)
Surfaces: **H = `surface="ours"`** (our domain tools), **T = `surface="web"`** (WebSearch +
fetch_url + run_python). Small **S ∈ {haiku, sonnet}**, frontier **F = opus**. Cells:
`haiku×{H,T}`, `sonnet×{H,T}`, `opus×{T}` (+ `opus×H` later for goal #2). Seed 42, fixed n.
- **Lift** (per task, per small model) = pass-rate(S+H) − pass-rate(S+T). The causal core.
- **Punch-up** = is pass-rate(S+H) ≥ pass-rate(opus+T)? The headline.

## Implementation phases

### Phase 1: Plumbing + pilot (STOP for review)
- [x] ~~Add **`--surface {ours,web}`** to `lab/run.py`~~ — **SUPERSEDED by decouple (REV 4.2).**
      The driver is `lab/ablation.py` (already a surface×model matrix), not `run.py`. Built instead
      (commit `578560d`): non-frozen `lab/experiments/lift_instances.py` (118-House member_summary /
      pairwise generators, public-resolvability prompt, `fields` gold mirror — no `content_hash`
      move); `ablation._resolve_template` falls back to `LIFT_TEMPLATES`; opus pinned to
      `claude-opus-4-8`. Tests: pure pairing + hermetic DuckDB gold mirror + requires_pg live shape.
- [x] **Roster spot-check (REQUIRED, REV 4.2)** — `lab/experiments/lift_roster_spotcheck.py`,
      READ-ONLY cast-level vs the Clerk (count reconciliation misses option-swaps). **Live: 40/40
      casts matched, 0 mismatch, 0 unresolved** -> 118-House gold trustworthy at the cast level.
- [ ] **Budget/turn probe:** one `--n 1` run on the pilot template for each surface; read the
      persisted `cost`/`result_subtype` from the jsonl; set `--max-budget-usd ≈ 3× observed` and
      confirm `--max-turns` headroom (member_summary/pairwise need ~name-resolve + a window read +
      compute; web arm needs several WebSearch/fetch_url + run_python).
- [ ] **Pilot:** `pairwise_agreement` (or `member_summary`), `haiku×{ours,web}` + `opus×web`, small n
      (~6), agent-sdk, truncation-excluded. **Read the web-arm traces** to confirm it genuinely
      finds + computes from public pages (and the integrity check: no `run_python` rollout touched
      our DB).
- [ ] STOP — surface pilot lift + budget numbers; do not launch the full matrix.

### Phase 2: The lift run + analysis
- [ ] Run the full cell matrix over `member_summary` + `pairwise_agreement` at the chosen n/seed,
      per-cell logs + jsonl. Exclude non-success rollouts (record how many).
- [ ] **Lift-analysis script** over `lab/runs/*.jsonl` (post-hoc; no frozen-core touch): per (task,
      model, surface) pass-rate; lift = S+H − S+T; punch-up = S+H vs opus+T; for set/count tasks also
      the symmetric-diff / off-by-one distribution (reuse the screen-hardening metric). Honest
      reporting of the existing diagnostics (name-collision exclusions, no-retrieval passes).
- [ ] Trace-read trust bar: confirm the web arm's wins/losses are real (found the right records),
      and no S+T rollout reached our data.

### Phase 3: Tier + write-up
- [ ] Tier each task **demonstration** (lift real: S+H wins, S+T frays on completeness/scale) vs
      **research-frontier** (S+H also fails → harness-R&D / RLVR headroom). Pre-registered cutoff.
- [ ] Short results write-up (the eval's first lift result). (Optional `opus×H` for goal #2.)

## Acceptance criteria
- [ ] `--surface` selectable in `run.py`; web arm runs end-to-end on the pilot; full suite green.
- [ ] Budget/turns sized so non-success truncations are excluded, not scored as misses.
- [ ] Lift (S+H − S+T) + punch-up (S+H vs F+T) reported per task for member_summary + pairwise.
- [ ] Trace-read confirms ablation-fairness (web arm could fairly resolve the question) AND integrity
      (no baseline rollout reached our DB).
- [ ] Tasks tiered demonstration vs research, cutoff pre-registered (this doc).

## Risks
- **Ablation-unfairness** (the crux): mitigated by restricting to public-Q+public-A tasks; re-phrasing
  is explicitly deferred. If even member_summary/pairwise prove unfair (e.g. name ambiguity on the
  web), the existing name-collision diagnostic flags it.
- **Baseline-crippling bias:** the web arm is the strong, public Agent-SDK scaffold (WebSearch +
  fetch_url + run_python); pre-registered here; do NOT weaken it. The honest negative (web matches H
  on lookups) is a credibility asset, not a failure.
- **Cost/latency:** agent-sdk × multi-cell × web-arm (many fetches) is the heaviest run yet — pilot
  first, size budget, run cells as separate invocations (or extend `lab/batch.py`).
- **run_python integrity:** experiment-grade (not network-isolated); the trace-read is the live guard;
  OS isolation + security-sentinel before any published number.

## Panel synthesis (rev 2 — 5-lens, 2026-06-29) — plan needs a reframe + 2 blockers fixed
**Sound / smaller than scoped (lenses 4, 5):** arms are fair, NO gold leak, secrets contained, `-S`
does NOT cripple the baseline (ssl/socket/urllib work); `--surface` is clean, backward-compatible,
hash-safe; and **`lab/ablation.py` ALREADY is the matrix driver + computes lift** (`_delta` = web-ours)
and sizes budget/turns/timeout — Phase 2 = EXTEND it (add member_summary/pairwise), not a new driver,
not `batch.py`. `cost` is already persisted in `TraceRecord`.

**BLOCKER 1 — gold != public truth (lens 1 P1.1, lens 2 P1-A).** Our gold is *our-ingest*-complete
(`_fully_complete_windows`), NOT Clerk-complete. A web arm tallying the TRUE public roll-call set is
graded FAIL against our short gold -> **spurious positive "lift" = our ingest gap, not harness value**
(worse than the pass-2 finding; every instance is an aggregate). FIX (gate, before any number):
reconcile each sampled window's gold vs the Clerk/GovTrack authoritative totals; drop/re-gold where
ours != public; pin option-bucketing to public labels; independent gold-sample confirmation.

**BLOCKER 2 — wrong metric (lens 3).** Lift-as-difference-of-marginal-pass-rates discards the pairing
and isn't the trust metric. FIX: **paired McNemar** per (task,model) on shared instance_ids (the
discordant cells ARE the lift) + CI; the **3-rate** accuracy/hallucination/over-refusal split (the
philosophy's non-negotiable; the refusal twins probe it), NOT one pass-rate; **persist
`result_subtype`** (additive TraceRecord field, hash-safe) or the truncation-exclusion is impossible
post-hoc; size n (~40+ answerable/task/cell) + k>=3 web rollouts/instance + variance CIs; report
truncation as a bounded interval [exclude, count-as-miss] per arm; per-task not pooled.

**The deep finding (lens 1 P1.2 + lens 2): the lift on these tasks is DATA-COMPLETENESS, not harness.**
member_summary/pairwise win because H has the records in a table and the web arm must scrape+tally
hundreds of pages -- that is the data-access axis the philosophy concedes 3x is NOT the moat, and a
genuinely strong web baseline (browser/JS, not our no-JS silently-truncating fetch_url + unnecessary
WebFetch block -- lens 2 P1-B) may close much of the *accuracy* gap. So an ACCURACY-LIFT headline here
is confounded and likely weak. **Recommended reframe: measure COST + RELIABILITY at accuracy PARITY**
(small+harness reaches frontier+browser+code accuracy at ~1/N cost + lower variance) -- the defensible
form of goal #1, independent of the conceded data-moat. `cost` is already persisted; add variance.

**Integrity (lens 4 P1) — fine for an UNPUBLISHED pilot, HARD GATE before any published number:** the
`-S` "no DB driver" wall is bypassable (sys.path re-add to the same venv; stdlib socket -> wire
protocol with the PUBLIC `DEFAULT_DB_URL` creds; urllib -> the API port). FIX before publishing:
OS-level egress isolation (netns / `--network none` / separate user) + rotate the local DB creds off
the public default; a static pre-filter in `_exec_sandboxed_python` (reject sys.path/site-packages/
psycopg2/asyncpg/ctypes/socket/5432/8000/urllib/legis); a MECHANICAL trace-read grep for those tokens
(add the list to the trust-bar step). `test_no_db_driver_importable` gives FALSE assurance (naive
import only). Also: fetch_url has a TOCTOU/DNS-rebind gap (resolve->validate->httpx re-resolves) ->
pin the validated IP; `_safe_err` redacts only `sk-ant-`, not OAuth bearer tokens.

**Bias/defensibility (lens 2): pre-registration must fix NUMBERS** (exact n, pinned model snapshots,
the tier-cutoff threshold, the literal excluded-subtype set) + commit the doc hash; publish gold+SQL+
ALL baseline traces (reframe "baseline auditable," not bit-reproducible — live WebSearch); anchor the
H tools to product-independence (they predate the eval, return RAW records not server-side aggregates;
a tool returning a gold-shaped aggregate disqualifies that task as a demonstration headline).

**DISPOSITION (rev 3, user 2026-06-29): COST/RELIABILITY AT ACCURACY PARITY.** The headline is no
longer accuracy-lift (S+H - S+T). It is: **small+harness reaches frontier+browser+code ACCURACY at
~1/N the cost and lower variance.** Concretely:
- **Parity (the precondition):** paired McNemar per (task, model) on the gold-reconciled instances,
  reported as the 3-rate (accuracy / hallucination / over-refusal). Establishes that S+H is AT or
  ABOVE the F+T accuracy band -- not a lift claim, a not-worse claim.
- **Headline = COST:** per-rollout USD (already in `TraceRecord.cost`) -> cost-per-correct-answer,
  S+H vs F+T, per task. The punch-up becomes "same accuracy, fraction of the cost."
- **Headline = RELIABILITY:** k>=3 rollouts/instance -> per-instance pass-probability + variance/CIs;
  report S+H vs S+T/F+T variance (lower = more reliable). This is also why S+T's silent
  scrape-undercount matters less -- variance/cost capture the flakiness directly.
- Still required under this framing: BLOCKER-1 gold-vs-Clerk reconciliation (a wrong gold breaks the
  parity claim too); BLOCKER-2's paired 3-rate machinery + `result_subtype` persistence + sized n +
  variance CIs; a genuinely STRONG baseline (browser/JS or higher-cap fetch + a WebFetch sensitivity
  arm) so "parity at lower cost" isn't "parity vs a crippled baseline"; the integrity GATE
  (OS isolation + cred rotation) before any PUBLISHED number.
- Build is small: EXTEND `lab/ablation.py` (member_summary/pairwise + the cost/variance/3-rate
  rollup); add `result_subtype` to `TraceRecord`. rev-4 will fill the pre-registration NUMBERS
  (exact n, pinned model snapshots, the parity band, the excluded-subtype set) — pinned below.

## Pre-registration (rev 4 — FROZEN before any cell runs; the git commit of this doc is the anchor)
These values are fixed in advance to remove post-hoc degrees of freedom. Changing any after a cell
has run invalidates the result and requires a new pre-registration commit.

**REV 4.1 (2026-06-29): congress corrected 119 -> 118.** member_summary/pairwise gate their windows
to COMPLETED congresses (`templates.py` `_fully_complete_windows`), so the ongoing 119th is excluded
-- the study targets the **118th House** (calendar 2023+2024), whose Clerk data is also final/stable
(better for reproducibility). No cell had run, so this supersedes the `3fa0784` anchor cleanly.

**REV 4.2 (2026-06-29): decoupled instance source (5-lens panel + user decision A).** The frozen
member_summary/pairwise gate to `_fully_complete_windows` (ALL completed congresses x BOTH chambers,
~18 windows) -- incompatible with a single pinned 118-House window (would give n~=1) and a House-only
reconciliation (can't cover Senate / 110-117). So the lift study generates its OWN NON-FROZEN
instances: **40 named 118-House members; bill-linked yea/nay/other gold; prompt "roll-call votes on
bills and resolutions ... any question type."** NOT the frozen templates -> no content_hash move, no
frozen-edit bias. Reconciliation: gap=31, ALL procedural (no `bill_not_ingested`) -> our bill-linked
set == the public bill/resolution set (a deterministic public-`legis_num` rule). REQUIRED in the
build: a per-member roster spot-check vs the Clerk (count-level reconciliation misses option-swaps).

**REV 4.3 (2026-06-29): compute held constant across surfaces (cost-probe finding + user decision).**
The n=1 cost probe (`lift_member_summary`, agent-sdk) found the **ours** arm had NO code tool, so the
agent had to hand-tally a member's ~1210 records and **truncated at the 10-turn cap** (`err=100%`),
while the **web** arm has `run_python`. That asymmetry would invert the lift (ours unreliable on the
RELIABILITY axis the study headlines). FIX (commit `356b9bb`): add the SAME guarded `run_python` to
the **ours** surface, so the ablation isolates **DATA ACCESS** (our domain tools vs web scrape), not
"ours can't compute." Compute is now identical on both arms; the only surface difference is the data
conduit. Re-probe confirms: `haiku x ours` acc=**100%** ($0.31, 31s) vs the prior truncation;
`haiku x web` still over-refuses ($0.85, 99s). **Provisional caps** (frozen here pending the full
pilot): `_MAX_TURNS=20` (ours, window retrieve + compute), `_MAX_TURNS_WEB=20`, `_MAX_BUDGET_USD=2.5`
(~3x the $0.80 observed), `_TIMEOUT_S=180`. Two integrity findings for the GATE (do NOT block the
unpublished pilot): (a) the `-I -S` sandbox is **not filesystem-isolated** — the ours `run_python`
read its retrieved records from the SDK's `tool-results/*.txt` cache (benign for ours: its own raw
tool output, not gold; but the OS-isolation gate must add FS confinement so the WEB arm cannot read
the cache or gold before publishing); (b) the mechanical grep token `legis` **false-positives on the
repo path** `legislative-research-tool` — narrow it to the cred form (`legis:` / `legis_dev` /
`@localhost`); the real DB-reach tokens (`psycopg2`/`asyncpg`/`5432`/`connect(`/`PGPASSWORD`) had
ZERO hits.

**Tasks (gold-reconciled).** `member_summary` and `pairwise_agreement`, **118th House** only (a
COMPLETED congress; see REV 4.1). Reported PER TASK (never pooled — Simpson). HARD pre-filter: each
sampled window's `vote_events` count is reconciled against the House Clerk's published roll-call
total for the 118th; **any window
where ours != Clerk is dropped** (not re-gold'd, first run) and the drop count is reported.

**Instances.** n = **40 answerable** per task + the template's natural refusal twins; selection by
**seed = 42** (existing `sample`/`hash_order`). The SAME instance_ids in every cell (the pairing).
H-arm AND web-arm name-collision exclusions computed; the **same excluded set removed from both
arms**; reported.

**Cells (5).** S ∈ {`claude-haiku-4-5`, `claude-sonnet-4-6`}, F = `claude-opus-4-8`; surfaces
H = `ours`, T = `web`: `haiku×{ours,web}`, `sonnet×{ours,web}`, `opus×web`. (`opus×ours` = goal #2,
deferred.) Backend `agent-sdk`. Pinned by these IDs; the run DATE is recorded (alias drift caveat).

**Rollouts.** **k = 3** per instance per cell (per-instance p-hat + variance). `--max-turns`/
`--max-budget-usd`/`timeout_s` from `ablation.py`'s `_MAX_TURNS`/`_MAX_TURNS_WEB`/`_MAX_BUDGET_USD`/
`_TIMEOUT_S`, after a Phase-1 cost probe confirms headroom.

**Exclusion rule.** Keep only `result_subtype == "success"`; every other subtype = truncation/error,
**excluded from the paired population AND reported as a per-arm rate**. Paired population = instances
where **all** of {S+H, S+T, F+T} succeeded on ≥1 of k. Report parity/cost as the bounded interval
**[exclude-truncation, count-truncation-as-miss]**.

**Metrics.**
- **Accuracy parity (precondition):** paired **McNemar** per (task, model) S+H vs F+T; the **3-rate**
  split (accuracy = correct-on-answerable; hallucination = answered-wrong-not-refused; over-refusal =
  refused-an-answerable). **Parity = non-inferiority margin δ = 0.05:** S+H at parity iff the upper CI
  bound of (F+T_acc − S+H_acc) ≤ 0.05.
- **Headline COST:** mean `TraceRecord.cost` per cell + **cost-per-correct-answer**, S+H vs F+T.
- **Headline RELIABILITY:** per-instance p-hat over k=3; cell-level **variance of p-hat** + CI; S+H
  vs S+T/F+T (lower = more reliable).
- Secondary diagnostic only: the S+H − S+T paired delta (the controlled ablation).

**Integrity (pilot = unpublished; the GATE binds before PUBLISHING).** Mechanical trace-grep of every
`run_python` `code` for: `sys.path`, `site-packages`, `psycopg2`, `asyncpg`, `ctypes`, `socket`,
`connect(`, `5432`, `8000`, `urllib`, `legis:`/`legis_dev`/`@localhost` (the cred form — NOT bare
`legis`, which false-positives on the repo path; REV 4.3), `PGPASSWORD` — any hit invalidates that
rollout + investigate. Before any PUBLISHED number: OS egress isolation + **filesystem confinement**
(the `-I -S` sandbox reads disk — REV 4.3) + rotate the local DB creds.

**Strong-baseline check.** Before trusting "parity at lower cost," run a **WebFetch / higher-cap /
browser sensitivity arm** on a ≥10-instance sample of one task; if S+H's cost/reliability edge
survives the stronger baseline, the `fetch_url` caps weren't manufacturing it. (Largely SATISFIED by
the egress work: under the 32MB fetch-to-mount cap the web arm reaches VoteView and hits 100% on
member_summary — not cap-starved; see REV 4.5.)

**REV 4.4 (2026-06-29): the egress integrity GATE is built + merged (PR #52 + #53, main @ f0bafd3).**
`run_python` executes in a `--network none` Docker container (zero egress to our PG/API); the web arm
reaches bulk public data ONLY via the SSRF-guarded `fetch_url` streamed to a RO `/sandbox/inputs/`
mount (cap 32MB, sized for the ~14.6MB H118 votes matrix; `--memory 2g`). security-sentinel passed
(M2 fixed; M1 = accepted residual). Re-pilot validated the gate is NEUTRAL (web 33%->100%, no drop;
mechanical trace-grep EMPTY on live web traces). The "OS egress isolation + filesystem confinement"
the rev-4 integrity clause demanded before publishing is now DONE. DB-cred rotation remains deferred
(deny-by-default egress already blocks the path).

**REV 4.5 (2026-06-29): FROZEN powered-run pre-registration (after the n=6 all-cells smoke `smoke1`).**
The git commit of THIS doc is the anchor, passed to `ablation --prereg-sha` and stamped into
`manifest_<run_id>.json`; any change after a powered cell runs invalidates the result.
- **Templates:** `lift_member_summary` + `lift_pairwise` (118th House; pairwise JOIN gold cross-checked
  8/8 vs an independent recompute, `lift_pairwise_validate.py`). Reported PER TEMPLATE (never pooled).
- **Instances:** **n = 40** answerable per template, **seed = 42**, the SAME instance_ids in every cell
  (the pairing). Refusal twins are filtered before cells run (`ablation.py` answerable-only), so the
  over-refusal signal is read from the answerable arm (`decision_correct==0`), not refusal rows.
- **Cells (5):** `haiku/sonnet x {ours, web}` + `opus x web`; `opus x ours` EXCLUDED (goal #2) via
  `--exclude opus:ours`. Backend **agent-sdk**, **SEQUENTIAL** (the `ANTHROPIC_API_KEY` pop is a
  process-global race). Models pinned: `claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-8`.
- **Rollouts:** **k = 3** per instance per cell. **As-run caps (REV 4.4):** `max_turns` 20 (ours) /
  30 (web), `max_budget_usd` $3.5, `timeout_s` 300; sandbox image digest-pinned, fetch cap 32MB,
  `--memory 2g`.
- **Exclusion:** keep `result_subtype == "success"` for the conditional/paired population; report BOTH
  the **conditional** (complete-case) and **ITT** (truncation = wrong) bounds + the **completion rate**
  (Wilson) and **flip-rate**. PAIRWISE cost exclusion (drop an instance from the cost vectors if EITHER
  arm's cost is null).
- **Stats (`lift_analysis.py`; estimation-first):** exact-binomial McNemar; **Newcombe (1998) method-10**
  paired-difference CI = the PARITY interval; Wilson per-proportion; **paired cluster bootstrap** of the
  cost ratio, **B = 10000**, the bootstrap seed pinned in `lift_analysis_<run_id>.json` (the rollout
  seed is the manifest's). Majority-vote rep aggregation (post-exclusion 1-1 tie -> incorrect). **Holm
  deferred** (no family-wise claim registered).
- **Parity margin Δ = 0.10** (NOT 0.05): the smoke confirms even n=40 with both arms at ceiling gives a
  punch-up parity CI of ~±0.09; δ=0.05 is unachievable, and claiming it would be dishonest (Card 2020).
- **PRIMARY endpoint (one, no multiplicity correction):** the **cost ratio at accuracy parity, S+H vs
  F+T** on the designated cell **`haiku/ours` vs `opus/web`, member_summary**. SECONDARY (reported with
  CIs, labeled): the per-model S+H−S+T controlled lift, and pairwise.
- **Smoke evidence (`smoke1`, n=6, k=1; the pilot motivating these numbers):** punch-up = `[6,0,0,0]`
  in all 4 cells (parity at ceiling) at 2-10x lower cost; lift = sonnet-web hallucinates the join
  (member_summary 0/6, McNemar p=0.031 ALREADY) and haiku-web can't complete (0-17%). Integrity-grep
  clean. Envelope ~$650.
- **Provenance chain:** pre-reg doc SHA -> `--prereg-sha` -> `manifest_pre45.json` (+ rollout seed,
  caps, cell files) -> the per-cell traces (carry contract/content/fingerprint hashes) ->
  `lift_analysis_pre45.json` (asserts hash-homogeneity; copies the hashes + seeds in).

## REV 4.6 (2026-07-01): RESULTS — `pre45ms` (member_summary powered run)
Post-hoc results addendum. The pre-registration NUMBERS above are UNCHANGED; the frozen anchor
`--prereg-sha 9fe4ffbb2871877592c0f008efaae57caa8d5192` is stamped immutably into
`manifest_pre45ms.json`. This section is a later commit and does not alter the pre-reg. Full machine
output: `lab/runs/lift_analysis_pre45ms.json`. `lift_pairwise` (`pre45pw`) is PENDING.

**Per-cell (member_summary, n=40, k=3; completion / correct-of-completed):**

| cell | completion | correct | dominant failure |
|---|---|---|---|
| `haiku/ours` | 100% | **120/120** | — |
| `haiku/web` | 5.8% | 0/7 | can't complete the join (113 errored) |
| `sonnet/ours` | 99.2% | 118/120 | — |
| `sonnet/web` | 95.0% | 12/114 | **hallucinates** (102 wrong; flip-rate 25%) |
| `opus/web` | 99.2% | **119/120** | — |

**PRIMARY (cost ratio at accuracy parity, S+H vs F+T = `haiku/ours` vs `opus/web`):** accuracy 2×2
`[40,0,0,0]` → **parity within Δ=0.10** (McNemar p=1.000, Newcombe diff-CI [−0.088,+0.088]); cost
ratio **4.24× cheaper** (paired cluster bootstrap, 95% CI **[3.94, 4.56]**, coverage 100%, n=40). The
headline holds: a small model + our harness matches the frontier model + generic web/code at PERFECT
accuracy, ~4× cheaper. (`sonnet/ours` vs `opus/web`: also parity, 1.79× cheaper.)

**SECONDARY — controlled same-model lift (S+H − S+T):** LARGE at both tiers, via two distinct failure
modes. `haiku`: web can't complete (5.8%); on the 7 it finished, ours wins all 7 (`[0,7,0,0]`,
p=0.016), 3.61× cheaper. `sonnet`: web completes (95%) but **hallucinates** (`[2,38,0,0]`, p=0.000,
diff-CI [+0.805,+0.986]), 1.81× cheaper.

**Honest framing (the crux):** `opus/web` IS accurate (119/120) — the frontier model CAN do the
multi-record join with generic tools. So the finding is NOT "web tools are useless"; it is **"generic
web+code needs a frontier model; the harness lets a small, cheap model match it — the harness
substitutes for model scale."**

**Integrity:** egress-grep over all 9 web cells CLEAN — the only hit (`legis:`) was a Python variable
name in an `opus` `run_python` snippet, not the DB credential; credential tokens (`legis_dev`,
`@localhost`, `:5432`, `psycopg2`, `asyncpg`) all zero. The `--network none` gate held.

**Operational notes (not part of the result):** two drift-guard false positives were fixed live at the
harness layer without touching any frozen hash — alias↔dated-snapshot (`2900a93`) and the SDK
`<synthetic>` sentinel (`b54922a`); `lift_analysis.load_run` now triages benign drift and restores the
true subtype while a genuine foreign model still hard-errors. A mid-run credit exhaustion contaminated
`sonnet/web` rep1–2 + all `opus/web` (160 `agent_infra` rollouts); those 5 cells were evicted from the
manifest (backup `manifest_pre45ms.json.bak_precredit`, garbage in `runs/contaminated_pre45ms/`) and
re-run clean after top-up. Neither issue touched the grading contract or the pre-reg numbers.

## Sources & References
- Scope: `docs/scopes/2026-06-29-harness-lift-ablation-scope.md`. Design:
  [[project_condorcet_experimental_design]] (arms, lift, bias defense).
- Code: `lab/solvers.py` `AgentSolver(surface=...)`, `_sdk_tool_config` (ours/web), the guarded
  `fetch_url`/`run_python` conduits (PR #48); `lab/run.py` `_run_agent` (+ `--max-turns`/
  `--max-budget-usd` from PR #47, needs `--surface`); `lab/batch.py` (possible matrix driver);
  the existing templates in `lab/templates.py` (member_summary/pairwise are ablation-ready).
- Precedent: the paused pass-1/2 moat ablation (the web vs ours infra this revives), see
  [[project_condorcet_eval_philosophy]]; [[feedback_lab_find_hard_families]] (superseded).
