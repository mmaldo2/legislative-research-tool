# The Factual / Computational Layer — Task Suite

*Legislative Advocacy Benchmark (LAB-adjacent), Condorcet — the clean, auto-gradable foundation*

---

## What belongs in this layer (the cleanliness test)

A task belongs here only if its answer is a **deterministic function of the database**, checkable by code, with no contestable judgment between the data and the answer. To keep the layer honest, every template carries a cleanliness tier:

- **C — Clean.** Answer is an exact function of stored data. Code grades it precisely. No definitions to argue about. (*"How did member X vote on bill Y?"*)
- **C-def — Clean given a pinned definition.** The computation is deterministic *once* a definition/threshold/mapping is frozen and versioned. The task grades the *computation*, never the *choice* of definition. The definition itself is a methodological-layer artifact that lives in a versioned registry. (*"Members whose vote diverged from their district estimate by >X."*) These are clean to **grade** and contestable to **specify** — keep that boundary visible.
- **→M — Kick to methodological.** Looks computational, but the answer depends on a judgment that can't be cleanly pinned. Do not fake determinism here; grade as method.

The discipline that protects the whole benchmark: **a task that smuggles a contestable definition into a "factual" answer is the single most dangerous kind of task you can write**, because it launders a methodological choice as a fact. Every C-def template must name its frozen definition explicitly and cite the registry version. If you can't pin it, it's →M.

---

## The ten families

### 1. Roll-call retrieval & aggregation
Pure lookups and counts over the vote record — the layer where a single hallucinated vote is brand-fatal, and therefore the highest-trust-value family.

| Template | Tier | Checks |
|---|---|---|
| How did member X vote on roll call Y? | C | Exact vote-value retrieval |
| Tally a roll call (yea/nay/present/absent, margin, pass/fail) | C | Aggregation correctness |
| Vote breakdown by party / chamber / committee / region | C | Grouped aggregation |
| Party-line vs. defection count on a vote | C | Conditional count |
| Members who crossed their party on roll call Y | C | Set membership |
| Per-member vote summary over a period (count, defection rate) | C | Windowed aggregation |
| Pairwise raw agreement rate between two members' records | C | Boolean agreement over shared votes (*not* "ideological similarity" — that's →M) |
| Closest / most-contested votes in a session (by margin) | C | Ranking by margin |

**Presumes:** normalized vote store (member × vote-event × value), member dimension table with party/chamber/region.

### 2. Sponsorship & cosponsorship graph
Relational queries over the bill–sponsor graph — your "leverage" family in raw form.

| Template | Tier | Checks |
|---|---|---|
| Bills sponsored / cosponsored by member X | C | Edge retrieval |
| Cosponsor list & count for bill Y | C | Edge aggregation |
| Members who cosponsored bill Y **and** voted against it | C | Graph × vote join |
| Lead-sponsor passage rate for member X | C | Success-rate computation |
| Bipartisan cosponsorship count on bill Y | C | Conditional count over party attribute |
| Most frequent cosponsorship pairs / blocs | C | Edge-frequency ranking |
| Members who never cosponsor across the aisle (in window) | C | Negative set membership |

**Presumes:** sponsor/cosponsor edge table (bill × member × role: primary/co), join to votes.

### 3. Bill status & procedural history
Facts about where bills are and how they moved.

| Template | Tier | Checks |
|---|---|---|
| Current status of bill X | C | State retrieval |
| Full procedural path (introduced → committee → floor → …) | C | Event-sequence retrieval |
| Bills that died in committee Z (in session S) | C | Filtered set |
| Time-in-stage for bill X (days in committee, etc.) | C | Timestamp arithmetic |
| Bills referred to committee X | C | Filtered set |
| Amendment count / amendment history for bill X | C | Event retrieval |
| Companion / cross-chamber bill identification | C-def | Clean once "companion" is pinned (text-similarity threshold or explicit linkage); else →M |

**Presumes:** bill lifecycle / event log with timestamps and stage labels.

### 4. Committee structure & membership
Org-chart facts.

| Template | Tier | Checks |
|---|---|---|
| Members of committee X (as of date T) | C | Membership retrieval (temporal) |
| Chair / ranking member of committee X | C | Role retrieval |
| Member X's committee assignments | C | Reverse membership |
| Committee vote tally on bill Y | C | Aggregation within committee scope |
| Which committee(s) have jurisdiction over bill type T | C-def | Clean once jurisdiction mapping is frozen |

**Presumes:** committee dimension + temporal membership table + role flags.

### 5. Member biographical / tenure / electoral facts
Facts about the members themselves.

| Template | Tier | Checks |
|---|---|---|
| Tenure / seniority rank of member X | C | Computed from service record |
| District represented by member X | C | Attribute retrieval |
| Party / leadership position | C | Attribute retrieval |
| Margin of member X's last election | C | Attribute retrieval (if stored) |
| Freshman vs. returning / term-limited status | C | Derived flag |
| Members up for election in cycle C | C | Filtered set |

**Presumes:** member dimension table with service history, electoral attributes.

### 6. Ideal-point retrieval, ranking & geometry
Facts about *your pipeline's stored outputs* (Shor-McCarty, Bonica DIME). Clean to retrieve and rank; **interpretation** ("X is an extremist") is →M.

| Template | Tier | Checks |
|---|---|---|
| Retrieve member X's ideal-point score (run R) | C | Versioned output retrieval |
| Rank chamber by score (run R) | C | Sort |
| Most / least conservative members **by the score** | C | Ranking (pinned to the metric) |
| Median (pivotal) member of the chamber | C | Median-voter computation |
| Ideal-point distance between two members | C | Metric computation |
| Members lacking roll-call history (need DIME bridging) | C | Set membership over data coverage |
| Bridge observations (returning members used as anchors) | C | Set membership by anchored-IRT design |

**Presumes:** versioned ideal-point store keyed by (member, estimation run); run-id discipline so "the score" is never ambiguous.

### 7. District-level data & MRP estimate retrieval
Facts about districts and about *your MRP pipeline's stored outputs*.

| Template | Tier | Checks |
|---|---|---|
| District X demographic / partisan composition | C | Attribute retrieval |
| MRP estimate for issue Q in district X (run R) | C | Versioned output retrieval |
| Districts ranked by estimated support for Q | C | Sort over outputs |
| Credible interval / uncertainty on an MRP estimate | C | Output retrieval |
| Districts where the MRP estimate is "thin" / low-reliability | C-def | Clean once the reliability threshold is frozen |
| District-to-member crosswalk (who represents district X) | C | Join via crosswalk |

**Presumes:** versioned MRP estimate store (district × issue × estimate × CI × run-id); district attribute store; crosswalk.

### 8. Cross-layer "leverage" joins
The heart of the product — and the sharpest cleanliness boundary. **The join is clean; the definitions feeding it are methodological.** Author every one as *"compute under frozen definition D vN."*

| Template | Tier | Checks |
|---|---|---|
| Members whose recorded vote on Y diverges from their district's MRP estimate on Y's issue, by >δ | C-def | Clean given: issue→bill mapping, δ threshold, estimate run — all frozen & cited |
| Members in the cross-pressure set under cross-pressure index vK | C-def | Applying a *frozen* index is computational; *building* the index is →M |
| Members who are pivotal (near median) **and** cross-pressured | C-def | Composition of two pinned computations |
| Members holding a position "against" district preference | →M unless every term pinned | "Against" and "preference" are choices; pin them or kick up |
| Rank members by per-member leverage score vK | C-def | Sort over a frozen leverage definition |

**Presumes:** the crosswalk, the versioned ideal-point and MRP stores, **and a frozen definition registry** so every C-def task cites the exact operational definition it computed against.

### 9. Temporal reconstruction & retrodiction
Using the historical record as a free labeled dataset — the family Harvey structurally cannot build.

| Template | Tier | Checks |
|---|---|---|
| Point-in-time: status of bill X **as of date T** | C | Bitemporal reconstruction |
| Point-in-time: committee membership / scores as of date T | C | Bitemporal reconstruction |
| Retrodiction: given the actual roll call, score a prior prediction | C | Comparison to recorded outcome |
| A member's vote / defection shift across sessions | C | Trend computation (the *number*; "drift" interpretation is →M) |
| Session-over-session turnover / composition change | C | Set difference over time |

**Presumes:** bitemporal store (valid-time + transaction-time) — a real engineering requirement, and the same point-in-time-freeze discipline already flagged for the legal-data work.

### 10. Data-integrity & provenance
Meta-tasks that directly target the unsurvivable failure mode: confident hallucination. **These are arguably the most important tasks in the entire benchmark for product trust.**

| Template | Tier | Checks |
|---|---|---|
| Does a vote exist for member X on bill Y? (yes/no) | C | Existence check — catches invented votes |
| Cite the record ID / source for this claim | C | Provenance verifiability |
| Is this attributed quote actually in the bill text / floor record? | C | Verifiable against the corpus |
| Correct answer is "not in the data" — does the agent say so? | C | **Refusal / uncertainty calibration** |
| Reconcile a member across sources via the crosswalk | C | Identity resolution correctness |

**Presumes:** provenance/record-ID on every fact; text corpus with exact-match/full-text index; crosswalk; and a deliberate population of *unanswerable* tasks so the model is graded on knowing what it doesn't know.

---

## Why this layer scales for free

The strategic property, restated as a build fact: **author once, grade forever, for free.** Each template is parameterized over members, bills, districts, committees, sessions, and run-ids. A single template becomes thousands of concrete tasks, each with an answer the database computes and a grader that's a code equality check (or set/rank comparison). No expert labels the instances — the schema is the answer key. This is why the layer is both the cheapest to build and the one with zero ideological-bias exposure: there is no human in the grading loop to encode a worldview.

| | Factual layer | Methodological layer |
|---|---|---|
| Grading | Code (exact) | LLM-judge + expert rubric |
| Instance generation | Automatic from DB | Hand-authored |
| Cost per 1,000 instances | ~free | Expert-hours |
| Bias exposure | ~none (and provable) | Real; needs calibration |
| Best for | Trust floor + clean RLVR | Differentiation |

---

## Difficulty tiers (doubles as the RL curriculum)

The same enumeration sorts into a natural curriculum — train the model up the tiers:

1. **Single-hop lookups** (families 1, 3, 4, 5, 6, 7 retrieval). One table, one fact.
2. **Aggregations & rankings** (1, 2, 6, 7). Group, count, sort, median.
3. **Two-table joins** (2's cosponsor-×-vote, 7's district-×-member). The first place frontier models start to fabricate.
4. **Multi-hop / compositional joins** (family 8). The leverage computations — where reliability is most valuable and most fragile.
5. **Temporal reconstruction** (family 9). Bitemporal correctness; hardest engineering.
6. **Adversarial / unanswerable** (family 10). Graded on correct refusal, not correct answer.

Tiers 3–6 are exactly where a general frontier model produces fluent, confident, wrong output — so they are where a trained specialist earns its trust premium, and where the auto-graded RLVR signal is cleanest and most abundant.

---

## What to build first

1. **Family 10 (integrity/provenance) + Family 1 (roll-call).** Together they establish the trust floor: the model never invents a vote, always cites, and says "not in the data" when that's the answer. Cheapest to build, highest brand-protective value.
2. **Families 2 and 6–7 retrieval.** The substance of advocacy intelligence in clean form.
3. **The definition registry**, *before* any Family 8 task. The registry is the artifact that lets the leverage joins be C-def rather than →M — and it's the bridge into the methodological layer, where the same frozen definitions get their *justification* graded by experts.

---

## Scale summary

| Family | ~Templates | Instances per template | Grader |
|---|---|---|---|
| 1. Roll-call | ~8 | thousands | code |
| 2. Sponsorship | ~7 | thousands | code |
| 3. Bill status | ~7 | hundreds–thousands | code |
| 4. Committee | ~5 | hundreds | code |
| 5. Biographical | ~6 | hundreds | code |
| 6. Ideal-point | ~7 | hundreds | code |
| 7. District / MRP | ~6 | hundreds–thousands | code |
| 8. Leverage joins | ~5 | thousands | code (vs. frozen defs) |
| 9. Temporal | ~5 | thousands | code |
| 10. Integrity | ~5 | thousands | code |
| **Total** | **~60–70 core (~100 with variants)** | **tens of thousands graded, auto-generated** | **all code** |

So: **~100 task types, effectively unbounded instances, every one graded by code, none touched by a human worldview.** That is the size and richness of the layer — and the reason it's the foundation rather than a footnote.
