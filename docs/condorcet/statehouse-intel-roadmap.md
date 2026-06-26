# Roadmap — statehouse-intel / Legislative Advocacy Benchmark

> **How to read this.** Phases are ordered by dependency, not calendar. The point of the ordering is *build-with-the-end-in-mind*: each phase plants seeds the next one needs, so the trust-floor work you do now is shaped by where it's going. Three things make this roadmap different from a task list:
> - **Keep in view** — the decisions in this phase that are load-bearing for a *later* phase. Get these right now and you don't repaint later.
> - **Parallel threads** (bottom) — long-lead-time work (mostly human/relationship) that *gates* Phases 3–4, so it must **start in Phase 1**, not wait its turn.
> - **The override rule** — within any phase, build one narrow vertical slice *end to end* before widening. Don't build wide on paper ahead of your inputs.

---

## The shape at a glance

| Phase | Core | Gated by | Unlocks |
|---|---|---|---|
| **0** | Trace schema + observability | — | everything (training-ready data) |
| **1** | Factual trust floor: Family 1 + 10 | Phase 0 | a tool people can trust |
| **2** | Factual substance: Families 2–7 + registry stood up | Phase 1 | computable advocacy intelligence |
| **3** | Leverage: Family 8 + retrodiction (9) | registry **blessed**, bitemporal | the differentiated product |
| **4** | Methodological layer + GEPA harness tuning | expert partners, Phase 3 | the moat layer + training data |
| **5** | Co-designed specialist (model) | benchmark at scale, cheap rungs plateaued | cost/latency/governance edge |

---

## Phase 0 — Foundations that compound

**Goal.** The plumbing that everything else logs into. Do this under/before the harness, not after.

**Build.** Trace schema → OpenTelemetry (OpenLLMetry/OpenInference) → self-hosted Langfuse.

**Keep in view.**
- Design the trace schema **training-ready now** — token-level where available, each run coupled to a verifiable outcome and an elicited rationale. It must serve *both* GEPA (Phase 4) and model training (Phase 5). Retrofitting this later loses Tier-3 moat data permanently.
- Self-host from day one (per-org enclaves + sensitive-data root forbid vendor SaaS).

**Done when.** Every harness run lands as a structured, training-ready trace with provenance.

---

## Phase 1 — The factual trust floor (Family 1 + 10) ← you are here

**Goal.** An agent that answers roll-call/integrity questions against the LA database, never fabricates, and knows what it doesn't know. This is what makes you a *product* rather than a demo.

**Build.**
- Family 10 (integrity / provenance / refusal) **and** Family 1 (roll-call retrieval & aggregation), together.
- Bounded query substrate (SQL path) + structured-core access via the crosswalk.
- Borrow grading wholesale: TrustSQL (penalty scoring), TriageSQL (refusal classification), EHRSQL (answerability flags).

**Keep in view (this is the part you asked for).**
- *Toward the methodological layer:* the **provenance/citation discipline** you build here (every fact carries a record ID) is the precondition for grading method later — you can't grade "is the reasoning sound" over facts you can't verify. And Family 10's "not in the data" / refusal tasks are the *seed* of the methodological standard "did the analysis caveat where the MRP is thin." Build the refusal tasks with that caveating standard already in mind.
- *Toward the registry:* you will hit tasks that *look* clean but smuggle a definition (e.g., "members who crossed party" needs a definition of party-line). **Don't hardcode these — log them as future registry entries.** You're practicing registry discipline before you formally need it.
- *Toward the moat:* every Family 1/10 run is Tier-3 trace data if Phase 0 is done right. Treat the trust floor as your first training corpus, not just an eval.

**Done when.** Code-graded accuracy on roll-call/integrity questions over LA; zero fabrication; correct "not in the data"; record-ID citation on every fact.

**Start-now, pays-off-later:** the Parallel threads below. Especially the expert/relationship pipeline and the bitemporal data design — both gate Phase 3 and have long lead times.

---

## Phase 2 — The computable substance + the registry seam

**Goal.** The rest of the clean factual layer, and the registry stood up so leverage becomes possible.

**Build.**
- Factual Families 2–7 (sponsorship, bill status, committee, bio, ideal-point, district).
- The **definition registry** (schema → first draft entries) — *before* any Family 8 task.
- Bitemporal layer (design started in Phase 1; built here).

**Keep in view.**
- *Toward the methodological layer:* the registry entries you draft here **are** the methodological layer's first work items. Draft each with `contested_parameters` flagged and a sensitivity-analysis hook, so your experts get something concrete to react to (not "is 0.15 right?" but "here's how the leverage ranking moves as it varies").
- *Toward Phase 3:* Family 9 (retrodiction) needs bitemporal. Building temporality is painful to retrofit — finish it here.
- *Toward the model:* run-version everything (ideal-point, MRP). A specialist trained on un-pinned estimates learns noise.

**Done when.** Clean factual families run; registry has draft entries with contested params flagged; bitemporal layer live.

---

## Phase 3 — The leverage thesis (Family 8 + retrodiction)

**Goal.** The thing no competitor does, computed and validated: per-member leverage, and a check that the method tracks reality.

**Build.**
- Family 8 leverage joins, computed against **frozen** registry definitions (`C-def`).
- Family 9 retrodiction over the historical record (bitemporal + outcomes).

**Keep in view.**
- *The first hard handoff:* Family 8 is only as good as the frozen definitions, so this phase is **gated on the methodological layer having blessed a v1 registry release** (divergence_threshold, district_preference, etc.). This is where factual and methodological first depend on each other — which is why the relationship pipeline had to start in Phase 1.
- *Toward outcome-coupling:* retrodiction is your free validation oracle — design it to test whether your *process* rubrics actually predict *real* outcomes, not just to score the agent.
- *Toward perception:* the first leverage outputs are the first thing a skeptic will challenge for bias. Have the symmetric-task-selection and open-definition discipline already in place.

**Done when.** `leverage_score` computed and ranked for the LA House under a blessed registry release; retrodiction shows the method tracks historical outcomes.

---

## Phase 4 — The methodological layer + harness optimization

**Goal.** Formalize the differentiation and tune the harness — the moat layer, and the source of clean training data.

**Build.**
- Expert rubrics (academic + liberty-movement partners; workshops), LLM-judge grading, all-pass metric (Harvey LAB pattern).
- GEPA/DSPy prompt-and-scaffold optimization over logged traces.
- Experts set the registry's contested parameters → freeze a registry release.

**Keep in view.**
- *Toward the model:* rubric-*passing* traces are your SFT corpus. Design the methodological grading so a "pass" is clean training signal, not just a score.
- *Toward bias/perception:* symmetric task selection across partisan valence, tracked inter-rater agreement, and either cross-ideological reviewers or open rubrics — the bias may be controllable, but the *perception* is a separate cost you pay regardless.
- *Toward cost:* GEPA + the advisor pattern + Skills are the cheap rungs. Measure whether they've **plateaued** — that's the gate for whether Phase 5 is even worth it.

**Done when.** Methodological rubrics blessed and graded; registry frozen by experts; harness optimized; you can see whether the cheap rungs have topped out.

---

## Phase 5 — The co-designed specialist (model)

**Goal.** A small, cheap, fast, domain-specialized model — a **cost/latency/governance** play, not the moat.

**Build.** SFT on rubric-passing traces → on-policy / multi-teacher distillation → RFT against the benchmark (harness as the RL environment). Served as **per-org LoRA on a shared base**.

**Keep in view.**
- *Enter only when gated:* benchmark exists at scale **and** Phase 4 showed the cheap rungs plateaued. Earn rung 5.
- *The model is not the moat* — it depreciates every base-model generation. The moat is the benchmark + outcome data + relationships. Frame and resource accordingly.
- *Watch:* reward hacking (gets worse as the model improves), Chinese-base optics for a liberty institution (have a deliberate provenance stance), and the re-specialization cost of model churn.

**Done when.** A specialist that beats general frontier *in-domain* on cost/latency; served per-org behind the privilege boundary.

---

## Parallel threads — start in Phase 1, pay off in Phase 3–4

These don't fit one phase; they're disciplines that run throughout, and the human ones have **long lead times** that gate later phases — so begin them now.

1. **Expert / relationship pipeline.** Academic + liberty-movement partners for the methodological layer (the conference/workshop network you flagged); the Erspamer/Pelican conversation once the concept is privately refined. These *gate Phase 3–4* and can't be rushed — seed them during Phase 1.
2. **Bitemporal data design.** Gates Phase 3 retrodiction; painful to retrofit. Design in Phase 1, build in Phase 2.
3. **Trace schema discipline.** Already Phase 0, but never relax it — a run not logged training-ready is moat lost.
4. **Governance / commons.** Settle what data may be pooled across orgs vs. siloed *before* any cross-org pooling (Phase 5 LoRA enclaves depend on it).
5. **Moat discipline.** Continuously: the benchmark, the outcome-coupled data, and the relationships are the moat. The harness and the model are table stakes you ride/refresh. Resource the moat, not the depreciating parts.

---

## Decision gates (the explicit handoffs)

- **Phase 2 → 3:** no Family 8 task until the registry has a blessed v1 release. (Factual depends on methodological here.)
- **Phase 4 → 5:** no model training until the benchmark exists at scale *and* the cheap rungs have measurably plateaued.
- **Any phase:** narrow slice end-to-end before widening. One blessed definition + one running factual slice beats ten specs.

---

## The override rule (re-stated because it's the one that gets violated)

You have more design on paper than inputs in hand. The next real move is not another document — it's **one vertical slice, end to end**: one definition (`divergence_threshold`) actually blessed by a real political scientist against real LA data, and Family 1 + 10 actually running against your database. Prove the narrow thing works before building the wide thing. Every phase above is "do the slice, then widen."

---

## Beyond the build (situating the later horizon)

The litigation-intelligence arc — *"Condorcet does not litigate; Condorcet makes litigation smarter"* — sits downstream of this roadmap and of law school (fall 2027). It reuses the same machine (benchmark + registry + traces + specialist), pointed at a new domain. Nothing here forecloses it; the platform is built to generalize. But it's a *later* expression of the same moat, not a parallel build — don't split focus toward it until the legislative slice is real.
