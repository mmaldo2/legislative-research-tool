---
title: Family 1 Graded-Task Benchmark Harness (lab/)
type: feat
status: active
date: 2026-06-24
origin: docs/scopes/2026-06-24-family1-harness-scope.md
---

# ✨ Family 1 Graded-Task Benchmark Harness (`lab/`)

> Revised 2026-06-24 after a technical-review panel (data-integrity, simplicity, architecture, performance). Accepted findings are folded in; see **Resolved Review Findings** and the **⚠️ flags**.

## Overview

Build a new top-level **`lab/`** module: a frozen, code-graded benchmark harness for the Condorcet Lab's **Family 1** (roll-call retrieval/aggregation). It generates task instances, computes **gold by trusted, engine-portable SQL** over the vote tables we populated (13,848 events / 5.4M records, Congress 110–119), code-grades, and logs JSONL traces. **v1 validates the machinery without a live LLM**: a SQL-oracle proves the *graders* accept correct answers; a wrong baseline proves they *catch* failures; **hand-written adversarial fixtures prove the *gold itself* is correct.**

Mirrors `autoresearch/prepare.py` discipline (frozen core, gold-by-SQL, `experiments/`-style logging) but is task-eval-shaped, and lives in `lab/` (not `autoresearch/lab/`) so the later live-agent slice can import `src/`.

> **The one property that matters:** a *wrong gold answer* launders a SQL bug as ground truth. Every choice below is weighted toward the templates where SQL "runs cleanly and lies."

## Problem
Family 1 is the Lab's factual trust floor; the autoresearch scaffold is ML-shaped, not task-eval-shaped. Build the durable "author once, grade forever" foundation — and get the subtle gold definitions provably right before anything is scored.

## Module layout
```
lab/
  __init__.py
  harness.py    # FROZEN: Postgres connection (psycopg2, mirrors prepare.py:33-71); per-run precompute
                #   (reconciliation set, party-majority-per-event); BATCH gold dispatch; gold-validation
                #   gate; grading dispatch; one-connection lifecycle; JSONL logging
  templates.py  # FROZEN: the 8 templates — each = {id, tier, prompt, BATCH gold_sql, sampler-spec,
                #   grader, FROZEN-DEFINITION note, undefined-handling, refusal-classification}
  graders.py    # FROZEN: exact, set_match, ranked_match, refusal_correct (+ provenance_present = agent-slice)
  generate.py   # sampling MECHANICS only (seeded hash-order over candidate-id lists); refusal RULES live in templates.py
  solvers.py    # SWAPPABLE: SqlOracleSolver (returns gold), WrongBaselineSolver (+ over-refuse variant)
  run.py        # CLI: python -m lab.run --n 20 --seed 42   (Postgres only; no --engine)
  summary.py    # SEPARATE reader: per-template/family pass rates from runs/*.jsonl (not in the frozen loop)
  runs/         # JSONL traces (.gitkeep)
  README.md     # frozen-vs-iterated contract + ALL frozen-definition notes (the C-def boundary)
tests/test_lab/
  test_gold_definitions.py    # HAND-WRITTEN-LITERAL golds over DuckDB-in-memory adversarial fixtures (the real gold proof)
  test_graders.py
  test_oracle_invariant.py    # oracle 100%; wrong-baseline fails; over-refuse caught (small fixture)
  test_engine_portability.py  # every gold SQL parses+runs on DuckDB; AST/grep guard vs banned constructs
  test_schema_columns.py      # reflection: every column the gold SQL references still exists
```

**Exact `src/` import surface (frozen, listed to prevent drift):** from `src.ingestion.vote_parsers` — the pure constants `VOTE_OPTION_MAP`, `OPTION_BUCKETS`, `CHAMBER_HOUSE`, `CHAMBER_SENATE`, and the PK helpers `house_vote_event_id`, `senate_vote_event_id`, `house_years_for_congress` (for labeling only). **Not** `build_member_map` — the duplicate-person resolution is already baked into `vote_records.person_id`, so gold SQL joins `people` *only* via `vote_records.person_id` (never `COUNT(DISTINCT people.id)`); that rule *is* the dup defense.

```mermaid
flowchart TD
    A[config + connect Postgres + seed] --> B[pre-flight census + PRECOMPUTE once: reconciliation set, party-majority-per-event, completed-congress set]
    B -->|sparse| Z[STOP: backfill prerequisite]
    B --> C[per-template: hash-order sample candidate IDs in Python]
    C --> D[BATCH gold-by-SQL: one query per template over the sampled ID set]
    D --> E[gold-validation gate: non-empty, total-order, type, DEFINED]
    E -->|undefined: tie majority / zero-shared / empty denom| R[REFUSAL bucket, never a numeric gold]
    E --> F[solve: SqlOracle returns gold | WrongBaseline perturbs, guaranteed-wrong + over-refuse variant]
    F --> G[grade: exact | set_match | ranked_match | refusal_correct]
    G --> H[append JSONL trace -> lab/runs/]
    H --> I[invariants: oracle==100%, wrong-baseline fails, zero empty gold]
```

## Technical Approach

### Connection, engines & dependencies
Run loop is **Postgres-only** via psycopg2 (mirror `prepare.py:33-71`; strip `+asyncpg`), **one connection held per run**, closed in `finally`. There is **no runtime `--engine` switch** — gold SQL strings are plain importable constants. DuckDB appears **only in tests**: `test_gold_definitions.py`/`test_engine_portability.py` load the same gold SQL strings into in-memory DuckDB over tiny fixtures. The only engine difference is paramstyle (`%s` vs `?`) — normalized in the test harness, not a production abstraction. **New deps (declare in `pyproject.toml`): `psycopg2-binary` (the project uses `asyncpg`, not psycopg2, today) as a lab runtime dep; `duckdb` in the `dev` extra.**

### Count authority & the reconciliation gate (review C1/C3 — corrected)
The ingester stores **official source totals** on `vote_events.{yes,no,other}_count`, but inserts `vote_records` **only for resolved members** (`reconcile()` guarantees `computed + dropped == official`). Therefore:
- **Stored counts are canonical** for #2 tally and #8 margin (the official totals). `other_count = present + not_voting` (combined; no stored split).
- The reconciliation gate is **`SUM(records per bucket) ≤ stored per bucket`** (records are a resolved subset). The real hazard to catch is **overcount** (`SUM(records) > stored` → data bug → exclude+surface). **Equality is NOT required** (it would exclude every event with any dropped voter).
- **#3/#4/#5/#6 compute from `vote_records`** (need per-member party/option) and are therefore defined over the **resolved record subset** — i.e. "majority among *resolved* co-partisans." This is a frozen-definition note, stated explicitly.

### Congress scoping (review C2 + arch#1 — corrected)
There is **no `congress` column**. Frozen rule: an event's congress = `vote_events → bills → sessions`, `congress = sessions.identifier` (string); **completeness** = `sessions.end_date IS NOT NULL` (incomplete/ongoing congresses excluded from #6/#8). The **hot-path row filter** uses the indexed, portable PK-prefix `vote_events.id LIKE 'us-{chamber}-{congress}-%'` (note the **trailing dash** so `11` ≠ `110`). A fixture asserts PK-congress and session-congress agree; the completeness gate uses only the `sessions` path.

### The 8 templates + FROZEN gold definitions

| # | Template | Gold (frozen) | Grader | Undefined → | Phase |
|---|---|---|---|---|---|
| 1 | vote lookup | the member's `option` for the event (answerable sampled **from `vote_records`**) | `exact` | dichotomy: recorded option vs **person_id with no `vote_records` anywhere → refusal** (no eligible/ineligible claim — schema can't support it) | **proving** |
| 4 | defection count | COUNT of {party} members whose yea/nay ≠ their party's **resolved yea/nay majority** on the event | `exact` int | majority undefined (`yea==nay`, or 0 yea/nay) → (party,event) → refusal | **proving** |
| 5 | crossed-party set | SET of canonical `person_id` (same def as #4) | `set_match` | same as #4 | **proving** |
| 7 | pairwise agreement | over events where **both** have a yea/nay record (same chamber): `(matches, shared)` integer pair | `exact` (pair) | `shared==0` → refusal | **proving** |
| 8 | closest-by-margin | top-N events by total order `(margin ASC, id ASC-lexicographic)`, `margin=abs(stored yes-no)`, completed congress, single chamber | `ranked_match` | N>available → all | **proving** |
| 2 | tally | `{yea, nay, other, margin, result}` from **stored** counts | `exact` (dict) | overcount event excluded | fast-follow |
| 3 | party breakdown | COUNT over `vote_records` where `option='yea'` AND canonical person `party={party}` | `exact` int | {party} drawn from non-NULL parties present | fast-follow |
| 6 | per-member summary over {congress} | `{vote_count, defection_rate=(defections, denom)}`, denom = events where member cast yea/nay AND party majority defined | `exact` (dict, rate as int pair) | empty denom → refusal | fast-follow |

**Sequencing (review: simplicity):** the **proving set #1/#4/#5/#7/#8 exercises all 4 v1 graders + every hazard class** (defection/majority/tie, set, pairwise zero-shared, ranked tie-break, windowing, dup-people, NULL party). #2/#3/#6 are mechanically derivative → **fast-follow** (Phase 4). All 8 still delivered.

### Frozen-definition notes (the C-def boundary; documented, not registry — except party)
- **Majority/defection (#4/#5/#6):** over **resolved yea/nay records only** (exclude present/not_voting). A strict majority exists **iff `yea ≠ nay`** (a lone 1-0 voter *is* a defined majority → defects 0; **"single voter excluded" is removed** per review H1). Tie/zero → undefined → refusal.
- **⚠️ Party (review H2 — flagged):** `people.party` is **current/last party, NOT point-in-time** (schema has no party history). A member who switched parties mid-range is labeled by current party → defection/breakdown gold can be wrong for switchers. v1 freezes "party = current `people.party`" as a **documented limitation**, adds a switcher fixture asserting the documented behavior, and **flags this as registry-worthy** (it's a contested definition, contra the earlier "no contested numerics" claim). Surface at the #4/#5 checkpoint.
- **Agreement (#7):** denominator = events where **both** cast yea/nay; chamber from `vote_events.chamber` (sample same-chamber pairs); `shared==0` → refusal. Return `(matches, shared)` integer pair (not a float → engine-exact).
- **Party policy (#3/#4):** verbatim party strings; **NULL excluded, never bucketed**; no `I`/`ID` merge; {party} params drawn only from non-NULL parties present on the event.
- **#8 order:** `(margin ASC, id ASC)`; `id` sort is **lexicographic** (deterministic total order; House ids embed year so order is year-then-roll — documented, not chronological). Margin from **stored** counts.
- **NULL handling:** events with NULL `chamber` excluded from chamber-scoped templates; a whole event with zero yea/nay → every party → refusal, and excluded from #8 "closest" if degenerate.

### Engine-portability rules (gold SQL)
ANSI-only. **Avoid** `@>`/`ARRAY[]`, `FILTER`, `string_agg`/`array_agg`, `::cast`, `DISTINCT ON`, `generate_series`, engine `random()`/`TABLESAMPLE`, JSONB ops, `ILIKE`. **Use** `COUNT(*)`/`SUM(CASE WHEN…)`, `GROUP BY`, joins, `CAST(AS)`, `CURRENT_DATE`, left-anchored `LIKE`. The adapter returns **engine-neutral Python types** (rates/fractions as `(num, denom)` int pairs, never driver floats) so the DuckDB cross-check compares values, not driver formatting.

### Performance (review C1/C2/C3/H1-H4/M1-M3)
- **Precompute once per run** in the census, cached in `harness`: the reconciliation/overcount set (one 5.4M grouped scan, ~13.8K groups), the **party-majority-per-event** table (one `GROUP BY vote_event_id, party` per completed (congress,chamber) — shared by #4/#5/#6), and the completed-congress set.
- **Batch gold per template:** one query per template over the sampled `IN (…)`/`VALUES` id set (≈8–12 queries/run, not 160+ N+1). Stage large id sets (a ~1–2K-event congress) as a **per-run temp table** the gold SQL joins, not giant inline `IN`.
- **Seeded portable sampling:** pull only the small candidate **id list** (≤~13.8K events / ≤~1.5K people), order in Python by `sha256(f"{seed}:{id}")`, take N. Never `random()`, never pull 5.4M rows.
- **#7 indexed form:** drive both sides by `person_id` (the `ix_vote_records_person_id` index), join on `vote_event_id`; never a bare `option IN (...)` scan.
- **Add a covering index** (migration): `CREATE INDEX ix_vote_records_event_option ON vote_records (vote_event_id, option)` → makes the one-time reconciliation/derive aggregate index-only (Postgres; DuckDB unaffected).
- **Live-Postgres full run gated behind `--run-eval`**; default `pytest` uses the tiny DuckDB fixtures.

### Solvers (validate graders) + hand-literal fixtures (validate gold) — three distinct proofs
- **SqlOracleSolver** returns gold → graders pass 100% (validates **graders**).
- **WrongBaselineSolver** returns a provably-wrong-per-instance perturbation (assert `answer != gold` first) + an **over-refuses-everything** variant → graders fail / over-refusal caught (validates **graders** from the wrong direction).
- **Hand-written-literal fixtures** (review H4): each adversarial scenario is a hand-built fixture whose correct gold is a **human-reasoned constant asserted literally**; the gold SQL must reproduce it. This — not a second SQL — is the **gold** proof. (The same SQL also running on DuckDB proves portability.)

### Graders & trace
v1 critical path = **4 graders**: `exact` (type-normalized; dicts/pairs), `set_match` (order/dup-insensitive canonical-id sets), `ranked_match` (ordered list), `refusal_correct` (refuses when it should, not over-refuse). `provenance_present` shape is **frozen now** (a structured **per-claim mapping** `claim → [source ids]`, not a scalar) but graded as an **agent-slice** concern (the oracle can't meaningfully fail it). Trace JSONL per instance: `{instance_id="{template}:{seed}:{event_id}", template_id, tier, params, gold, gold_sql_hash, frozen_hash, solver, answer, pass, grader, provenance, seed, engine, model, prompt_version, cost}` — sentinels `model="oracle"|"wrong-baseline"`, `prompt_version/cost=null`. Append+flush; partial-last-line tolerant. **Anti-cheat hash** covers the frozen `lab/` files **+ the imported vocab values + `generate.py` sampler**, so a `src/` vocab drift or a sampler change is detectable from a trace alone. `summary.py` is a separate reader, not in the frozen loop.

### Schema-drift coupling (arch#7)
Gold SQL hard-codes columns across `vote_events`/`vote_records`/`people`/`sessions`. **Add** the `bill.py:10-11`-style drift warning to `vote.py`, `person.py`, `session.py` (each naming `lab/templates.py`), and a `test_schema_columns.py` reflection test so a rename fails CI, not a scored run.

## Implementation Phases (checkpoint between each)
- **Phase 0 — one-template slice — ✅ DONE (2026-06-24):** `lab/` scaffolded (harness/templates/graders/generate/solvers/run; psycopg2-binary + duckdb deps); **template #1 (vote_lookup)** end-to-end on live Postgres — seeded hash-order sampling, gold read by trusted SQL from `vote_records`, synthetic-nonexistent refusal instances (absence proven), exact + refusal_correct graders, oracle + wrong-baseline + over-refuse solvers, JSONL trace. **Invariants hold: oracle 25/25 (100%), wrong-baseline 0/25, over-refuse fails all 20 answerable.** 8 grader tests + 234-suite green, ruff clean.
- **Phase 1 — frozen spine:** 4 graders, both solvers (+over-refuse), trace schema, the DuckDB **test** fixtures + portability/AST guard, the precompute scaffolding (reconciliation, party-majority, completed-congress), hash-anti-cheat, drift warnings + reflection test.
- **Phase 2 — proving templates #4/#5/#7/#8 + frozen definitions:** the dangerous gold SQLs (resolved-majority defection, pairwise pair, ranked margin) + samplers + refusal classification; congress-scoping seam; **surface the party-switcher flag**.
- **Phase 3 — adversarial gold fixtures + full run:** hand-literal fixtures for every Severity-1 hazard (tie majority, present contamination, NULL party, duplicate people, zero-shared, margin ties, PK-vs-session congress, window leakage, #1 dichotomy, party switcher); seeded full run on live Postgres (`--run-eval`); per-template pass-rate summary.
- **Phase 4 — fast-follow templates #2/#3/#6:** mechanically derivative on the proven foundation (tally/stored-counts, party breakdown, per-member summary).

## Resolved Review Findings
DI-C1/C3 reconciliation = `records ≤ stored`, stored canonical, majorities over resolved subset ✅ · DI-C2/arch#1 congress via sessions + PK-prefix filter + agreement fixture ✅ · DI-H1 majority iff yea≠nay; single-voter rule removed ✅ · **DI-H2 party = current (documented limitation, registry-flagged) ⚠️** · DI-H3 #1 dichotomy; refusal proven via absence in `vote_records` ✅ · DI-H4 gold proof = hand-literal fixtures, not 2nd SQL ✅ · DI-H5 #7 chamber via events, yea/nay-only denom ✅ · DI-H6/M1 #8 lexicographic total order, margin from stored ✅ · Simplicity: Postgres-only run loop (DuckDB→tests); 4 graders (provenance=agent-slice); summary.py separate; templates sequenced 5+3 ✅ · Arch#2 exact import surface listed ✅ · Arch#3 engine-neutral types / int-pair rates ✅ · Arch#4 declare psycopg2-binary + duckdb deps ✅ · Arch#5 hash covers vocab + sampler ✅ · Arch#6 provenance per-claim shape + instance-id grammar frozen ✅ · Arch#7 drift warnings + reflection test ✅ · Arch#8 refusal rules in frozen layer ✅ · Perf C1/C2/M2 precompute-once + batch gold + party-majority cache ✅ · Perf H1/H3 PK-prefix scoping + hash-order sampling ✅ · Perf H2 covering-index migration ✅ · Perf H4/M3 one connection; live run behind `--run-eval` ✅.

## ⚠️ Flags to surface
- **Party point-in-time (DI-H2):** v1 uses current party; switchers mislabeled. Documented limitation + registry flag; confirm at the #4/#5 checkpoint whether that's acceptable for the trust floor or whether party-dependent templates need a party-history source first.
- **Template sequencing:** you chose "all 8"; the panel shows #1/#4/#5/#7/#8 prove the whole foundation, so #2/#3/#6 are sequenced as a fast-follow (still delivered). Override if you want all 8 in one pass.

## Acceptance Criteria

### Machinery & invariants
- [ ] One command runs generate → batch gold-by-SQL → solve (oracle+wrong) → grade → log; ≥20 instances/template; **logged seed reproduces identical instances+gold**.
- [ ] **SqlOracle passes 100%**; **WrongBaseline fails 100%** of designed instances (per-instance `answer != gold` asserted); **over-refuse caught**.
- [ ] Run does **≈8–12 gold queries** (batched), not N-per-instance; precompute (reconciliation, party-majority, congress sets) runs **once**; **one DB connection** per run.
- [ ] JSONL trace per instance with the frozen schema (incl. `instance_id` grammar, `seed`, `gold_sql_hash`, `frozen_hash`); `summary.py` prints per-template/family rates.

### Gold correctness (the brand-fatal gate)
- [ ] Each Severity-1 gold reproduced by the SQL against a **hand-literal fixture** whose expected answer is a human-written constant (not a second SQL).
- [ ] Reconciliation gate = `records ≤ stored` (overcount excluded+surfaced); #2/#8 use stored; #4/#5/#6 majority over resolved subset (fixture-proven).
- [ ] Undefined (#4 tie, #7 zero-shared, #6 empty denom) → refusal, never numeric.
- [ ] Congress via `sessions.identifier`; incomplete (`end_date NULL`) excluded from #6/#8; PK-prefix filter asserted equal to session-congress; leakage fixture (event just outside window) absent.
- [ ] Duplicate-people fixture → no inflation (joins via `vote_records.person_id`; no `COUNT(DISTINCT people.id)`).
- [ ] present/not_voting excluded from #4/#5/#7 yea/nay computations; NULL party excluded from #3/#4 (no NULL bucket); I≠ID.
- [ ] #1 dichotomy: recorded `not_voting` ≠ refusal (no `vote_records` anywhere); no eligible/ineligible claim.
- [ ] #8 `(margin ASC, id ASC)` total order stable across two seeded runs; N>available → all.
- [ ] Party-switcher fixture asserts the documented current-party behavior.
- [ ] Run-start census asserts `DISTINCT option ⊆ OPTION_BUCKETS`.

### Portability & anti-cheat
- [ ] Every gold SQL parses+runs on DuckDB fixtures; AST/grep guard rejects banned constructs; sampling seeded+portable (no engine `random()`).
- [ ] `frozen_hash` (lab files + vocab values + sampler) recorded per trace; wrong-baseline still fails after any grader edit.
- [ ] `test_schema_columns.py` fails if a referenced column is renamed; drift warnings added to `vote.py`/`person.py`/`session.py`.

## Risks & Mitigations
- **Silently-wrong gold.** Frozen-definition notes + per-hazard hand-literal fixtures + undefined→refusal + the corrected reconciliation/congress/majority rules.
- **Tautological gold check.** Gold validated by hand-written literals, not a second SQL.
- **Party point-in-time error.** Documented limitation + switcher fixture + registry flag (⚠️).
- **Scale (5.4M rows).** Precompute-once + batched gold + PK-prefix scoping + covering index; live run gated.
- **Dependency surprise.** psycopg2-binary + duckdb declared in pyproject (psycopg2 not a main dep today).

## Test Plan
- **`test_gold_definitions.py`** — hand-literal golds over DuckDB fixtures per Severity-1 hazard (the heart; no live DB/LLM).
- **`test_graders.py`** — the 4 graders incl. type/dup normalization + the over-refuse direction.
- **`test_oracle_invariant.py`** — oracle 100%, baseline fails, over-refuse caught.
- **`test_engine_portability.py`** — all gold SQL on DuckDB + banned-construct guard.
- **`test_schema_columns.py`** — reflection check.
- **Integration (`--run-eval`)** — seeded full run on live Postgres; oracle 100% + zero empty gold at scale.

## Sources & References
- **Origin:** [docs/scopes/2026-06-24-family1-harness-scope.md](../scopes/2026-06-24-family1-harness-scope.md)
- **Design:** `docs/Condorcet/lab-factual-layer-task-suite.md` (Family 1 + tiers; §1 smuggled-definition warning), `handoff-track-a-claude-code.md`, `definition-registry-schema.md` (party-switcher → registry).
- **Pattern to mirror:** `autoresearch/prepare.py:33-71` (psycopg2 connect, one-connection lifecycle), `:240-286` (experiments/+summary.jsonl). NB `:112` `@> ARRAY[...]` is the portability anti-example — do NOT carry into `lab/`.
- **Schema + the corrected contracts:** `src/models/vote.py` (no congress col; nullable chamber/vote_date), `person.py` (party current-only), `session.py` (congress via `identifier`, completeness via `end_date`); `src/ingestion/votes.py:259-293,426-450` (stored=official, records=resolved subset; `other_count=present+not_voting`); `src/ingestion/vote_parsers.py:16-31` vocab (import), `:171-205` dup-map + reconcile. Indexes: migration `003` (`ix_vote_records_person_id`).
- **Test pattern:** `tests/eval/test_eval_quality.py` (`TestGoldenSetIntegrity`), `tests/conftest.py` (`--run-eval`).
- **Live-agent slice (deferred):** `run_agentic_chat()` `src/services/chat_service.py:87`; backend `claude-sdk`; needs a `get_bill_votes` tool.
