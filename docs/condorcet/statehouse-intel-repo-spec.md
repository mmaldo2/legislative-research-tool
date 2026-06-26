# Repo Specification: `statehouse-intel`
## Standalone State Legislature Intelligence System — Louisiana Pilot (v1)

**Status:** Draft for build
**Entity home:** Condorcet Institute (c)(3) — repo is Institute work product from commit one; methodology intended for publication
**Scope of v1:** Louisiana House + Senate, current term. Engine A (legislator profiles) complete; Engine B through first MRP wave and cross-pressure index. Creative testing (Phase 3) and listening panels (Phase 4) are out of scope for v1 but the schema anticipates them.

---

## 1. Design Principles

1. **Batch, not service.** Everything is a pipeline run producing versioned artifacts. No daemons, no API server in v1. The unit of work is a session, a poll wave, or a report — not a request.
2. **Files over database.** Canonical storage is versioned Parquet in a structured data directory. DuckDB is the query engine over those files. Postgres only enters if/when a multi-user web frontend exists (not v1). This keeps the whole system portable, diffable, and trivially backed up.
3. **Idempotent, resumable ingestion.** Every ingestion job can be re-run safely; raw API responses are cached to disk before any parsing so that parser bugs never require re-fetching.
4. **The crosswalk is sacred.** Entity resolution is its own module with its own tests, its own versioned output, and human-review checkpoints. Every other table foreign-keys to `ci_leg_id`. Nothing joins on names downstream of the crosswalk, ever.
5. **Models are pinned and reproducible.** Every model run records git SHA, input data versions, random seeds, and full config. MRP and IRT outputs are artifacts with provenance, because they will be published and challenged.
6. **External systems are dependencies, not couplings.** Open States and LegiScan are hit directly via their public APIs. Nothing reads the legislative platform's database. If the bill-outcome model ever feeds in, it arrives as a flat feature file or API response, schema-validated at the boundary.
7. **Survey data is segregated.** Individual-level survey responses (both citizen and legislator) live in a separate data root with stricter access, retention metadata, and no copies into the main lake. Aggregates flow out; microdata never does.

---

## 2. Repository Layout

```
statehouse-intel/
├── README.md
├── METHODOLOGY.md              # public-facing methods doc, versioned with code
├── pyproject.toml              # uv-managed; python 3.12
├── config/
│   ├── states/la.yaml          # state-specific config (chambers, session ids, geo codes)
│   ├── pipeline.yaml           # global pipeline settings, data roots, cache policy
│   └── models/                 # per-model config (irt.yaml, mrp_licensing.yaml, ...)
├── data/                       # gitignored; structure enforced by code
│   ├── raw/                    # immutable API/file pulls, content-addressed
│   │   ├── openstates/
│   │   ├── shor_mccarty/
│   │   ├── la_ethics/
│   │   ├── ftm/                # FollowTheMoney historical pull
│   │   ├── census_acs/
│   │   ├── elections/          # precinct results, VEST/RDH
│   │   └── sos_voterfile/      # if/when acquired; encrypted at rest
│   ├── staged/                 # parsed, typed, per-source Parquet
│   ├── curated/                # crosswalked, analysis-ready marts
│   └── artifacts/              # model outputs, versioned: irt/, mrp/, network/, reports/
├── data_sensitive/             # separate root, separate backup policy, encrypted
│   ├── surveys_citizen/        # raw response microdata + sample management
│   └── surveys_legislator/
├── src/statehouse_intel/
│   ├── ingest/                 # one module per source (§4)
│   ├── crosswalk/              # entity resolution (§5)
│   ├── marts/                  # curated table builders (§6)
│   ├── models/
│   │   ├── irt/                # ideal point estimation (§7)
│   │   ├── network/            # co-sponsorship graph metrics (§8)
│   │   ├── mrp/                # district opinion (§9)
│   │   └── crosspressure/      # composite index (§10)
│   ├── survey/                 # instrument mgmt, sample mgmt, fielding trackers (§11)
│   ├── outputs/                # report generation (§12)
│   └── common/                 # schemas (pandera), io, caching, run-metadata
├── pipelines/                  # thin CLI entrypoints, one per pipeline stage
│   ├── ingest_all.py
│   ├── build_crosswalk.py
│   ├── build_marts.py
│   ├── fit_irt.py
│   ├── fit_mrp.py
│   ├── build_crosspressure.py
│   └── render_report.py
├── notebooks/                  # exploration only; nothing downstream depends on these
├── tests/
│   ├── unit/
│   ├── contracts/              # schema/data-contract tests per source
│   └── golden/                 # tiny frozen fixtures; full pipeline runs end-to-end on them
└── docs/
    ├── data_contracts/         # one md per source (§4 rendered out)
    ├── adr/                    # architecture decision records
    └── runbooks/               # how to execute a poll wave, a session refresh, etc.
```

**Stack:** Python 3.12, `uv` for environment management, `polars` for transforms (pandas only at model-library boundaries), `duckdb` for ad hoc query, `pandera` for schema enforcement, `cmdstanpy` for IRT and MRP (PyMC acceptable fallback; Stan preferred for MRP because the published-methodology story benefits from the standard tooling), `networkx` for graphs, `jinja2` + `weasyprint`/pandoc for report rendering. Orchestration is `make` or a thin `typer` CLI in v1 — no Airflow/Dagster until there's a recurring multi-state cadence to justify it.

---

## 3. Identifier Scheme

```
ci_leg_id      CI-LA-{chamber}-{seq}     canonical legislator id, stable across terms
ci_dist_id     LA-{H|S}-{district_num}   legislative district, post-2022 maps
ci_bill_id     LA-{session}-{chamber}{num}
ci_person_ids  crosswalk table maps ci_leg_id ↔ external ids (§5)
```

`ci_leg_id` is assigned once per human and never reused. District renumbering across redistricting cycles is handled in a `district_lineage` table, not by mutating ids.

---

## 4. Ingestion Modules and Data Contracts

Every ingestion module implements the same interface: `fetch() -> raw cache`, `parse() -> staged parquet`, `validate() -> pandera report`. Raw responses are stored content-addressed with fetch timestamp and request params in a sidecar JSON. A source is "green" when its contract tests pass on the latest staged output.

### 4.1 `ingest/openstates.py`
| | |
|---|---|
| Source | Open States v3 API (people, bills, votes) for LA |
| Cadence | Per-session refresh; weekly during session |
| Key outputs | `staged/openstates/people.parquet`, `bills.parquet`, `votes.parquet`, `vote_events.parquet`, `sponsorships.parquet` |
| Contract | `people`: openstates_id (pk), name, party, current_district, chamber, active. `votes`: vote_event_id, openstates_person_id, option ∈ {yes,no,absent,excused,other}. `sponsorships`: bill_id, person_id, classification ∈ {primary,cosponsor}. |
| Known quirks | Vote-event coverage gaps for some LA committee votes — floor votes are the reliable spine; committee votes flagged `coverage_partial=true` and excluded from IRT by default. Person records can duplicate across terms; dedup deferred to crosswalk. |

### 4.2 `ingest/shor_mccarty.py`
| | |
|---|---|
| Source | Harvard Dataverse, individual-level April 2023 release (one-time pull; check for newer release at run time) |
| Key outputs | `staged/shor_mccarty/ideology.parquet` |
| Contract | name, st='LA', party, chamber-year coverage flags, `np_score` (common-space ideal point) |
| Known quirks | Names only — no external ids. Trails current sessions by several years; used as anchor, never as current-term estimate. Name formats differ from Open States ("LASTNAME, First" vs "First Lastname"); normalization lives in crosswalk, not here. |

### 4.3 `ingest/la_ethics.py`
| | |
|---|---|
| Source | Louisiana Ethics Administration campaign finance bulk/portal exports |
| Cadence | Quarterly; pre-session refresh |
| Key outputs | `staged/la_ethics/contributions.parquet`, `filers.parquet`, `expenditures.parquet` |
| Contract | contributions: filer_id, contributor_name, contributor_employer, amount, date, report_id. Amounts non-negative; dates within filing period. |
| Known quirks | Contributor names are free-text and filthy; donor entity resolution is a *separate, lower-stakes* fuzzy-match pass (canonical donor ids are best-effort, flagged with confidence scores — unlike the legislator crosswalk, imperfection here is tolerable). Filer→legislator mapping goes through the crosswalk. |

### 4.4 `ingest/ftm.py`
| | |
|---|---|
| Source | FollowTheMoney legacy API/exports, LA historical (through 2024 cycle) |
| Purpose | Cleaned historical contributions as the base layer; `la_ethics` patches forward from where FTM coverage ends |
| Contract | ftm_eid (their entity id — capture it, it's a crosswalk asset), recipient, contributor, industry codes (their coding is the main value-add over raw Ethics data) |

### 4.5 `ingest/census_acs.py`
| | |
|---|---|
| Source | Census API, ACS 5-year, geographies SLDL/SLDU for LA |
| Key outputs | `staged/census_acs/district_demographics.parquet`, `district_occupation.parquet`, plus PUMS pulls for the poststratification frame (§9) |
| Contract | One row per ci_dist_id × table; margins of error retained as columns, never dropped |
| Notes | Occupation detail (SOC-coded employment by district) feeds the licensed-worker-share feature; the licensing-relevant SOC code list is config (`config/states/la.yaml`), not code |

### 4.6 `ingest/elections.py`
| | |
|---|---|
| Source | LA Secretary of State results; VEST/Redistricting Data Hub precinct shapefiles + results for presidential disaggregation |
| Key outputs | `staged/elections/district_results.parquet` (legislative races: margins, contested flags, primary history), `district_pres_share.parquet` (presidential vote reaggregated to current legislative districts) |
| Contract | Vote shares ∈ [0,1] and sum ≈ 1 per race; every ci_dist_id present |
| Known quirks | LA's jungle primary structure means "primary vulnerability" is defined differently than in closed-primary states — vulnerability metrics are state-parameterized in config |

### 4.7 Deferred sources (schema reserved, no v1 build)
`ingest/text_corpus.py` (press releases, floor video transcripts, social — Phase 1.5, feeds the persuasion-pathway typology), `ingest/voterfile.py` (LA SOS file; encrypted root, permissible-use review gate before any code touches it), `ingest/lobbyist_reg.py` (LA Board of Ethics lobbyist registrations).

---

## 5. Crosswalk Module (`crosswalk/`)

The highest-stakes module. Output is `curated/crosswalk/legislators.parquet`:

```
ci_leg_id            string  pk
full_name_canonical  string
chamber              enum {H, S}
ci_dist_id           string  fk
party                enum
term_start, term_end date
openstates_id        string  nullable
shor_mccarty_name    string  nullable
la_ethics_filer_ids  list[string]
ftm_eid              string  nullable
sos_member_url       string  nullable
match_method         struct per id: {exact, fuzzy, manual}
match_confidence     struct per id: float
reviewed_by          string  nullable   # human sign-off
reviewed_at          timestamp nullable
```

**Resolution pipeline:** (1) seed from Open States people (most complete current roster); (2) deterministic joins where possible (district + party + term overlap + normalized surname); (3) fuzzy pass (Jaro-Winkler on normalized names with chamber/party/era blocking) producing candidate pairs; (4) **every fuzzy match below 0.95 confidence goes to a human-review queue** rendered as a markdown checklist — at 144 LA legislators per term this is an afternoon, and it buys total downstream trust; (5) emit versioned crosswalk with review metadata.

Crosswalk versions are tagged (`crosswalk-la-2026.1`) and every mart records which version it was built against. Tests include: no duplicate external ids, every active roll-call voter resolves, every Shor-McCarty LA row either resolves or is explicitly marked `pre_term_window`.

This file (plus the build code) is the artifact shared with the legislative platform — published as its own small versioned dataset so either system can import it without touching the other.

---

## 6. Curated Marts (`marts/`)

Analysis-ready tables, all keyed on `ci_leg_id` / `ci_dist_id`:

- `legislator_core` — roster + party + district + tenure + leadership/committee positions (committee assignments scraped from chamber sites; small bespoke parser, config-listed URLs)
- `rollcall_matrix` — legislators × vote events, filtered per IRT inclusion rules (§7)
- `sponsorship_edges` — weighted co-sponsorship pairs per session
- `money_summary` — per-legislator totals, top donors, industry mix (FTM codes), shared-donor edge list
- `district_profile` — demographics, occupation/licensed-share, presidential lean, vulnerability composite
- `legislator_profile` — the Block 1–4 join: one wide row per member, the substrate for reports

Mart builders are pure functions from staged + crosswalk to curated, with pandera schemas as the contract between marts and models.

---

## 7. IRT Module (`models/irt/`)

**Goal:** current-term ideal points anchored to Shor-McCarty common space.

**Spec:** 2PL Bayesian IRT per chamber. Vote inclusion rules (config): floor votes only by default; drop unanimous and near-unanimous (>95% lopsided) votes; drop legislators with <20 scorable votes (report them as `insufficient_votes`, don't silently impute). Model 1D as the headline; fit 2D as a diagnostic and for the establishment/insurgent second dimension where it emerges. Identification: anchor via returning members — soft-center the prior for each returning legislator's θ on their Shor-McCarty score (normal prior, σ as config), which both identifies the scale and projects new members into approximate common space. Document this projection honestly in METHODOLOGY.md: it is an approximation, not a Shor-McCarty replication.

**Issue-specific ideal points:** same machinery on bill subsets defined by topic tags (v1 tagging: keyword + LLM classification of bill titles/digests into a small config-defined taxonomy — licensing/occupational, fiscal, criminal justice, education, other). Only fit issue-specific models where the subset has ≥25 informative votes; otherwise report "insufficient roll-call signal" rather than a noisy score.

**Artifacts:** `artifacts/irt/{run_id}/` containing draws summary (mean, sd, 5/95), convergence diagnostics (R-hat, ESS — run fails loudly if R-hat > 1.01), config snapshot, input data hashes. A standard validation notebook compares θ against party medians and known-member sanity checks.

---

## 8. Network Module (`models/network/`)

NetworkX over `sponsorship_edges` and `money_summary` shared-donor edges. Per-legislator outputs: degree/betweenness/eigenvector centrality on the co-sponsorship graph, cross-party edge share (the broker signal), community assignment (Louvain), and money-network centrality. One artifact table plus a rendered graph visual (SVG) for the report. Deliberately simple in v1 — the value is the broker list, not graph-theory sophistication.

---

## 9. MRP Module (`models/mrp/`)

**Goal:** district-level (SLDL + SLDU) opinion estimates with honest uncertainty, per issue item, publication-grade.

**Poststratification frame builder (`mrp/frame.py`):** ACS PUMS for LA → person-level microdata with age band × sex × race/ethnicity × education; PUMA→district allocation via the geographic correspondence files (population-weighted crosswalk; document the allocation method — PUMAs straddle legislative districts and this is the main approximation). Frame output: cell counts per ci_dist_id × demographic cell, versioned like everything else. Optional party-registration dimension enters only if/when the voter file is acquired.

**Response model (`mrp/model.py`):** Stan. Binary or ordinal outcome per item; varying intercepts for age, race, education, district; district-level predictors (presidential vote share, urbanicity, licensed-worker share — the structured prior that makes house-district estimation from n≈3–4k feasible). One model per survey item, shared codebase, per-item YAML config (outcome coding, predictors, priors).

**Validation harness (`mrp/validate.py`):** mandatory before any estimate ships — (a) recover statewide toplines within the design margin; (b) where a comparable CES item exists, compare state and large-area estimates; (c) leave-one-region-out checks; (d) calibration against any available election/ballot benchmark. The published methodology cites this harness; it is the credibility instrument.

**Artifacts:** `artifacts/mrp/{issue}/{wave}/district_estimates.parquet` (posterior mean, 50/90% intervals per district), diagnostics, frame version, model config.

---

## 10. Cross-Pressure Module (`models/crosspressure/`)

The composite that joins the engines. For each (legislator, issue):

```
position_gap   = f(θ_issue or θ_general, district_opinion_mean)   # signed, standardized
salience_w     = district issue-salience proxy (licensed-worker share for licensing; survey salience item when available)
vulnerability  = composite from district_profile (margin history, contested flags, term-limit status — LA-parameterized)
perception_gap = legislator's stated belief about district opinion − MRP estimate   # null until legislator survey wave lands
CPI            = weighted combination (weights in config, sensitivity analysis in report appendix)
```

Output: ranked target table with a `target_class` derived field — `information_target` (large perception_gap, modest position_gap), `pressure_target` (small perception_gap, large position_gap, high vulnerability), `low_leverage`, `aligned`. Classification thresholds are config and reported transparently. Uncertainty propagates: CPI carries intervals from both θ and MRP posteriors; the report never prints a point rank without its interval.

---

## 11. Survey Module (`survey/`)

Lives against `data_sensitive/`. Three submodules:

**`survey/instruments/`** — versioned instrument definitions (YAML: item ids, wording, response options, randomization blocks). Item ids are stable across waves so trackers join cleanly. Citizen wave 1 and legislator wave 1 instruments are content work, not code — the module just enforces versioning and renders to fielding formats (Qualtrics import / panel-vendor spec).

**`survey/sample.py`** — citizen-side panel sample management: quota tracking against the frame, vendor file ingestion, attention/speeder QC flags, weighting inputs. Legislator-side: a fielding tracker (contact log, channel, response status, confidentiality tier) — operationally this is a spreadsheet with a schema; the code just validates and ingests it.

**`survey/exports.py`** — the *only* path from `data_sensitive/` to the main lake. Citizen microdata exports as de-identified modeling files (demographic cells + responses, no PII, no panel ids) into MRP input. Legislator survey exports as: (a) per-legislator perception-gap values keyed on ci_leg_id *only for the confidential-tier-compliant fields*, (b) chamber-level aggregates. Retention metadata (collection date, consent scope, deletion date) is mandatory columns on everything in the sensitive root.

---

## 12. Outputs Module (`outputs/`)

Jinja2 templates → markdown → PDF (pandoc/weasyprint). v1 deliverables:

1. **Chamber report** (`render_report.py --chamber H`): ideal-point distribution and member table, 2D map if the second dimension is informative, co-sponsorship network visual with broker callouts, money summaries, district fundamentals appendix.
2. **Issue brief** (per MRP issue): district estimate map (choropleth via geopandas/matplotlib — static SVG, no web stack in v1), methodology box, topline + extremes table.
3. **Cross-pressure target memo**: ranked CPI table with target_class, intervals, and per-target one-paragraph rationales (template-generated, analyst-edited).
4. **METHODOLOGY.md** rendered to the public methods PDF — versioned with the code so every published estimate cites an exact methods version.

All client-facing artifacts watermark the data/crosswalk/model versions in a colophon.

---

## 13. Testing, CI, Runbooks

- **Contract tests** per source run on every staged rebuild; a red contract blocks mart builds.
- **Golden pipeline**: a frozen miniature fixture set (≈12 fake legislators, 40 votes, 2 districts) runs the entire pipeline — ingest-parse through report render — in CI on every commit. Model fits on goldens use 200 iterations just to prove the plumbing.
- **Stat-model checks** (R-hat/ESS gates, MRP validation harness) are runtime gates, not CI — they run per real fit and fail the artifact, loudly.
- **Runbooks** in `docs/runbooks/`: "session refresh," "citizen poll wave," "legislator survey wave," "publish issue brief" — each a checklist mapping to pipeline commands, so the operation survives being handed to a research assistant later.

---

## 14. Build Sequence

| Step | Deliverable | Depends on |
|---|---|---|
| 1 | Repo scaffold, config, common schemas, golden fixtures | — |
| 2 | Open States + Shor-McCarty ingestion green | 1 |
| 3 | Crosswalk v1 with human review pass | 2 |
| 4 | ACS + elections ingestion; `district_profile` mart | 1 |
| 5 | IRT fit + validation; `legislator_profile` mart | 3 |
| 6 | Network metrics; **Chamber report v1 ships** | 5 |
| 7 | LA Ethics/FTM ingestion + money mart (parallel to 5–6) | 3 |
| 8 | Poststratification frame; citizen wave 1 instrument finalized | 4 |
| 9 | Wave 1 fields; MRP fit + validation harness; **Issue brief ships** | 8 |
| 10 | Cross-pressure index; **target memo ships** | 5, 9 |
| 11 | Legislator survey wave (relationship-gated, calendar-gated); perception_gap lands in CPI | 3, 9 |

Steps 1–6 are pure public data and can ship a real deliverable before any survey dollar is spent — which is also the demo that justifies the survey budget to a client or donor.

---

## 15. Decisions Deliberately Deferred (logged as ADRs)

- Postgres/web frontend (trigger: second concurrent state or second concurrent analyst)
- Orchestrator adoption (trigger: recurring multi-state cadence)
- Text-corpus pipeline and persuasion-pathway typology (Phase 1.5; schema slot reserved in `legislator_profile`)
- Voter file acquisition (gated on permissible-use legal review; encrypted root reserved)
- Bill-outcome model integration (consumed as external feature feed if/when wanted; explicitly *not* a shared codebase)
- Creative-testing module (Phase 3; will reuse `survey/` sample management)
