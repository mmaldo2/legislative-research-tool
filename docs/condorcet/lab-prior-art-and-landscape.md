# Prior Art & Landscape — Legislative Advocacy Benchmark

*Did this already get built? What do we borrow, what do we build, and where is the moat actually safe? — Condorcet*

---

## The one-line answer

**The factual/computational legislative benchmark we're proposing does not exist.** No one — academic or commercial — has published a graded, agentic benchmark of factual/computational correctness over a legislative database. But three things in adjacent territory *do* exist, and the discipline that protects us is knowing exactly which to **consume**, which to **transplant**, and which is **genuinely ours to build**:

- **Datasets** → consume (they're our raw material, not a competitor).
- **Generic structured-QA grading methodology** → transplant (don't reinvent the grader).
- **The legislative schema + advocacy task content + outcome-coupled framing** → build (this is the only part that's defensible, and the only part nobody else is positioned to make).

A second finding matters as much as the first: the factual layer is **academically obvious enough to be replicable**, so it is *table stakes, not moat*. The moat lives one layer up, in the parts the existing players structurally won't touch — state-level, outcome-coupled, proprietary-data-backed, representation-gap framing.

---

## The four buckets of adjacent work

### Bucket 1 — Academic LLM-political-science (overlaps the *judgment* layer, not the factual one)

An active field, but aimed at **prediction and simulation**, not factual grading.

| Work | What it is | Relation to us |
|---|---|---|
| **Political Actor Agent (PAA)** | LLM "legislator agents" predicting roll-call votes; evaluated on accuracy / F1 against 117th–118th House records | Our **judgment layer** (the one we're deprioritizing). Not a factual benchmark. |
| **CongressRA** | LLM agent for *studying* the U.S. Congress — tools for web search, API access, SQL querying, vector DB; retrieves bill details, legislative history, demographics | **Closest prior art for the retrieval substrate.** But: a research *tool*, not a graded benchmark; federal-only; built for academic replication, not advocacy. |

**Takeaway:** the closest relative (CongressRA) solved the *agent-over-legislative-data plumbing*, not the benchmark. Read it before building the substrate. Because it's academic and open (`congressRA/sample-agent` on GitHub), it's a plausible **collaboration**, not a competitor — and a conversation worth having before reinventing its data plumbing.

**Risk this bucket surfaces:** a *generic* legislative-agent benchmark is an obvious next paper for this community. The agent already exists; the benchmark is the natural follow-on. So we should assume someone could publish "benchmark an agent over Congressional data" — which means the *generic* factual layer is not where our defensibility can live.

### Bucket 2 — The datasets (our raw material, not our benchmark)

The field is thick here, and **all of it is input to our platform, not a test of it.**

| Resource | Type | Use to us |
|---|---|---|
| **BillSum** | Bill summarization corpus (US Congress + California test set) | Text corpus; summarization is not our task |
| **GovTrack / Party Matters / Korn-Newman** | Roll-call + bill-text corpora for vote prediction | Vote data; prediction is the judgment layer |
| **CoCoHD** | Congress committee hearing dataset | Hearing/transcript corpus |
| **GELATO** | Legislative NER dataset | Entity extraction component |
| **LobbyLens** | Bill-to-company mapping | Adjacent; lobbying/interest mapping |
| **Shor-McCarty / DW-NOMINATE (VoteView)** | Ideal points + roll calls | Core inputs (already in our stack) |
| **Open States / LegiScan / Congress.gov APIs** | Structured legislative data feeds | Core data sources (already in our stack) |

**Takeaway:** consume these; do not recreate them. None grades an agent's factual correctness over a relational schema — they are the substrate our benchmark *runs on*.

### Bucket 3 — Generic structured-QA methodology (transplant wholesale)

Our factual layer is, formally, **domain-specific text-to-SQL-plus-compute with answerability and penalty scoring.** That genre has mature, transplantable methodology. We are not inventing the grader; we're porting it onto a legislative schema.

| Benchmark | What to steal | Maps to our family |
|---|---|---|
| **BEAVER** | Difficulty design for *real analytical queries* — multiple joins, nested subqueries, CTEs, window functions | Family 8 (leverage joins); difficulty tiers 3–4 |
| **EHRSQL / BiomedSQL** | Answerability / uncertainty flags; domain reasoning (e.g., threshold logic) in a safety-critical setting | Family 10 (integrity / "not in the data") |
| **TrustSQL** | Penalty-based scoring — a wrong answer costs more than an abstention | The **trust-floor scoring scheme** across the whole suite |
| **TriageSQL** | Question-intention classification: answerable vs. ambiguous vs. improper | Family 10 (refusal calibration) |

**Takeaway:** transplanting these probably removes ~a third of the task-suite build, and — just as valuable — makes our grading **defensible by citation** when a skeptic asks "how do you know your benchmark is sound." The honest framing for a technical reviewer: *"Our factual layer is legislative-domain text-to-SQL with EHRSQL-style answerability and TrustSQL-style penalty scoring; the novelty is the schema, the task content, and the outcome coupling — not the grading method."*

### Bucket 4 — Commercial incumbents (the competitors — and they don't do this)

FiscalNote/PolicyNote, Quorum, Plural, LegiStorm, BGov.

**What they are:** bill trackers + summarizers + semantic search + NL chat + drafting + CRM + alerts. The AI is largely bolted on — by Quorum's own competitive comparison, its AI Bill Tracking "was added on to their legacy platform and is not built in," providing summaries and semantic search. The advertised NL query is "summarize this bill" / "find 5 recent AI bills" — discovery and summarization, **not factual computation over the vote/sponsor graph.**

**What they are not:**
- **No public benchmark** — there's no eval we'd be duplicating.
- **No representation-gap analysis** — no evidence any of them surfaces *legislators holding positions against their districts' demonstrated preferences*. They track what bills exist and who to contact; they do not compute **per-member leverage**. That is precisely our thesis, and it is unoccupied.

**Market context:** FiscalNote — the incumbent most likely to have built something sophisticated — is contracting (stock down ~97%, CEO transition, divestitures), not investing. Quorum is the ascendant generalist tracker. Neither is aiming where we are.

**Takeaway:** the competitive product space is "trackers and summarizers." Our differentiator (the empirical representation gap, per-member leverage) is not on anyone's roadmap that's visible. We don't beat them at bill tracking; we do a *different thing* they don't do.

---

## Borrow vs. build — the consolidated table

| Component | Verdict | Source / Action |
|---|---|---|
| Legislative data (votes, bills, sponsors, ideal points, districts) | **Borrow / consume** | Open States, LegiScan, VoteView, Shor-McCarty, Bonica DIME — already in stack |
| Retrieval-substrate plumbing (agent-over-legislative-data) | **Study, possibly borrow** | Read CongressRA (`congressRA/sample-agent`); consider collaboration |
| Grading: answerability / "not in the data" | **Transplant** | EHRSQL / BiomedSQL design |
| Grading: penalty-based trust-floor scoring | **Transplant** | TrustSQL |
| Grading: analytical-query difficulty tiers | **Transplant** | BEAVER |
| Grading: refusal / question-intention classification | **Transplant** | TriageSQL |
| **The legislative schema + task content** | **Build** | Our ~100-template factual suite |
| **Outcome coupling (retrodiction, public outcomes)** | **Build** | The part no academic dataset has |
| **State-level coverage** | **Build** | The academics are federal-only |
| **Representation-gap / per-member-leverage framing** | **Build** | The part no competitor has |

---

## Where the moat actually is (confirmed by the dig)

The landscape scan corroborates the earlier conclusion rather than softening it:

1. **The factual layer is table stakes, not moat.** It's replicable methodology over consumable data, and an academically obvious next step. Build it fast, borrow the grader, don't over-invest in it as IP.
2. **The moat is the layer the existing players structurally won't build:** state-level coverage (academics are federal), outcome-coupling to public legislative results (academics are research-neutral, incumbents do summarization), proprietary platform data (ours), and the representation-gap framing (no competitor does it).
3. **The clock is real.** A generic legislative-agent benchmark could appear from the active LLM-political-science community. Our insurance is to not depend on "we built a legislative QA benchmark" as the story — the story is the advocacy-outcome-coupled, state-level, proprietary-data product, with the factual benchmark as its trustworthy foundation rather than its differentiator.

---

## Immediate actions this implies

1. **Read CongressRA's implementation** before building the retrieval substrate; reach out — academic, open, plausibly collaborative.
2. **Lift the four grading schemes** (BEAVER tiers, EHRSQL answerability, TrustSQL penalty scoring, TriageSQL refusal) into the task-suite spec, replacing roughly a third of from-scratch grader design.
3. **Frame the factual layer publicly as transplanted-methodology-on-a-novel-schema**, not as novel science — it's more credible to skeptics and it keeps the "novelty" claim where it's actually defensible.
4. **Concentrate net-new effort** on retrodiction (outcome coupling), state-level data, and the representation-gap computations — the moat-relevant build.
