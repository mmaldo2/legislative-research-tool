# Handoff — Track A (Claude Code)
## Build the agent-eval harness + Family 1 & Family 10 on the existing federal data

> **Repo:** `legislative-research-tool` (System 1). **Suggested branch:** `feat/lab-track-a`.
> **Mode:** plan first, then loop. **§0 tells you how.** Obey the **Hard rules (§5)** without exception.

---

## 0. How to use this handoff

You will run in two modes:

1. **Plan (do this first, then stop for human review).** Read this doc and the canonical context (§2). Read the named files in the repo to confirm reality (do not assume schemas). Then produce a concrete plan: file layout, the template list you intend to build, the grading approach, and the run command. **Surface the plan and wait for the human to confirm before looping.**
2. **Loop (after the plan is approved).** Execute the build/improve cycle in §4 autonomously, logging every run, until the acceptance criteria (§6) are met — stopping to surface whenever a §8 condition fires.

Do not start writing code in plan mode. Do not weaken the grading contract in loop mode. Those two rules protect the whole exercise.

---

## 1. Goal (one paragraph)

Generalize the existing `autoresearch/` eval scaffold from *bill-outcome prediction* into an **engine-agnostic agent-eval harness**, and use it to build the **factual trust floor**: **Family 1** (roll-call retrieval/aggregation) and **Family 10** (integrity / provenance / refusal), graded by code against gold answers the harness computes itself from the database. The agent-under-test is the repo's existing `qa_agent` / LLM harness. Capture every run as a training-ready trace. This is the first runnable slice of the Lab, on data that is already ingested — no Louisiana, no crosswalk, no registry definitions required yet.

---

## 2. Read first

**Canonical context (the design):**
- `condorcet-ecosystem-map.md` — the front door: System 1 / System 2 / crosswalk / Lab, built-vs-spec, the two-track path. You are building **Track A, steps 1–2**.
- `CLAUDE.md` (the cross-cutting brief) — the **Hard rules** are non-negotiable.
- `lab-factual-layer-task-suite.md` — the factual-layer task families and grading approach.
- `statehouse-intel-platform-spec.md` — environment + guardrails. `definition-registry-schema.md` — for the registry scaffold only (no definitions needed for Family 1/10).

**Ground truth in *this* repo (read before writing any query — confirm columns, don't assume):**
- `autoresearch/prepare.py` and `autoresearch/program.md` — the frozen-harness / iterated-solver pattern you are generalizing.
- `src/models/` — the real SQLAlchemy schema (`bills`, `bill_actions`, `people`, `sponsorships`, `vote_events`, `vote_records`, `jurisdictions`, `sessions`, …).
- `src/agents/qa_agent.py`, `src/llm/harness.py`, `src/mcp/server.py` — the agent-under-test and its tools.
- The repo's own `CLAUDE.md` — commands and conventions (async SQLAlchemy, ruff, conventional commits).

---

## 3. What to build

### 3a. Engine-agnostic task harness (generalize `prepare.py`)
A **frozen** harness that, for each task template:
1. takes a **SQL connection from config** (psycopg2 → Postgres now; swappable to DuckDB later — keep it ANSI-ish, no Postgres-only syntax in task SQL);
2. **generates instances** by sampling the DB;
3. **computes the gold answer by trusted SQL** (never hand-written answer keys — this is what makes it auto-gradable and infinitely instanceable, exactly as `prepare.py` computes its target from the DB);
4. **runs the agent-under-test** (`qa_agent`) on the natural-language task;
5. **code-grades** the agent answer against gold;
6. **logs** the result (§3d).

Mirror `prepare.py`'s discipline: **the gold computation and the grading logic are the frozen core. They live in files the loop does not modify to make tasks pass.**

### 3b. Family 1 — roll-call (clean `C`; `exact` / `set_match` grading)
Templates (illustrative — propose the full list in your plan), gold via SQL over `vote_events` / `vote_records` / `people` / `sponsorships` / `bills`:
- How did `{member}` vote on `{vote_event}`? → exact (yea/nay/absent).
- How many `{party}` members voted yea on `{vote_event}`? → exact integer.
- Which members crossed party on `{vote_event}`? → set of `person_id`s.
- What was the margin / did it pass? → exact.
- Who were the (co)sponsors of `{bill}`? → set; count → exact.

### 3c. Family 10 — integrity / provenance / refusal (`refusal-correct` + `provenance-present`)
The trust floor. Templates:
- **Refusal:** ask about a member / bill / vote that does **not** exist, or a fact the DB cannot support → the **required** answer is "not in the data." Gold = refusal; grade whether the agent refused when it should *and* did not over-refuse on answerable Family 1 items.
- **Provenance:** every returned fact must carry a source record ID (`vote_record` id, `bill` id). Grade `provenance-present`.
- **Point-in-time (stretch):** ask a "status as of date T" question and check the agent does not use post-T information. **Concrete exemplar already in the repo:** `autoresearch/train.py` reports ~0.99 AUROC because `prepare.py`'s features (`action_count`, `days_active`, `last_action_date`) accrue *after* committee passage — textbook post-outcome leakage. A good Family 10 task asserts an agent answering "would this bill have been predicted to pass *as of its introduction*" must not read post-introduction features. (Optional quick win: add a leakage-free feature variant in a *copy*, never by editing the frozen `prepare.py`.)

### 3d. Trace schema v0
Each run persisted as a **training-ready** record: `{task, template_id, gold, agent_answer, pass/fail, agent_reasoning/trace, provenance, model, prompt_version, cost}`. Extend what exists — `cost_tracker`, the append-only prompt-versioned `ai_analyses` table, and the `autoresearch/experiments/` logging pattern — rather than inventing a parallel system. This is the Tier-3 capture; a run not logged is moat data lost.

### 3e. Registry scaffold (structure only)
Stand up the `definition-registry-schema.md` Pydantic model + a loader + a YAML directory + freeze-rule validation. **Empty of real definitions** — Family 1/10 are `C`/refusal, not `C-def`, so they need none. This just makes the structure exist and enforce its rules, ready for Family 8 later.

---

## 4. Working agreement (the loop)

| Frozen — never modify to make tasks pass | Iterated — this is the work |
|---|---|
| gold computation (the trusted SQL) | task templates & coverage |
| grading logic & thresholds | the `qa_agent`'s prompts / tools / scaffold (to raise pass rate) |
| the Hard rules (§5) | the trace/logging detail |

**The metric:** per-family pass rate (watch **Family 10** hardest — refusal and provenance are the brand-protective floor). **The cycle:** build a template + its gold → run the agent → inspect failures → either improve the agent (prompts/tools) *or* add/repair coverage → re-run → log. **The anti-cheat rule (carry it from `autoresearch`'s "do not modify prepare.py"): you may not weaken a grader, loosen a tolerance, or simplify gold to inflate the score.** If a task is failing because the *task* is wrong (ambiguous gold, bad SQL), fix the task; if it's failing because the *agent* is wrong, fix the agent.

---

## 5. Hard rules (from `CLAUDE.md` — non-negotiable)

- **Never fabricate** a vote, member, bill, or count. Every fact carries a source record ID or is not returned.
- **"Not in the data" is valid and required.** Refusal is graded; do not guess to seem helpful.
- **SQL-first; keep task SQL engine-portable** (no Postgres-only constructs) so it runs against DuckDB later unchanged.
- **Point-in-time discipline.** Never let an answer read post-dated information; watch for leakage.
- **Do not weaken graders or gold** to pass. Do not touch the frozen core to inflate the metric.
- **If a task needs a definition that isn't in the registry, stop and surface it** — never invent a threshold/mapping inline. (Family 1/10 should not need any; this guards Family 8 later.)
- **Confirm the schema by reading `src/models/` and `prepare.py`** before writing queries — do not assume column names.

---

## 6. Acceptance criteria (self-checkable — the loop is done when all hold)

- [ ] Harness generates ≥ 20 instances per template, computes gold by SQL, runs the agent, grades, and logs — via **one command**.
- [ ] Connection is config-driven and the task SQL is engine-portable (a smoke test against an empty DuckDB file proves no Postgres-only syntax).
- [ ] **Family 1:** ≥ 6 templates implemented; `qa_agent` run and graded; pass rate reported per template.
- [ ] **Family 10:** refusal tasks (nonexistent entities) graded — agent answers "not in the data" and does **not** over-refuse answerable items; provenance graded — every returned fact carries a record ID.
- [ ] **Trace v0:** every run persisted as a structured training-ready record.
- [ ] **Registry scaffold:** validates a sample entry and rejects a malformed/freeze-violating one.
- [ ] Results land in an `experiments/`-style log; a short run summary prints pass rates by family.

---

## 7. Setup / first commands

From the repo's `CLAUDE.md`: `docker compose up -d db` → `alembic upgrade head`. **Confirm the federal data is actually present** before building tasks: count rows in `bills`, `vote_events`, `vote_records`, `people`, `sponsorships` (if low/empty, the historical backfill must run first — see `scripts/backfill_historical.py`; surface this to the human). Run the existing `autoresearch` baseline once (`cd autoresearch && python train.py`) to see the frozen-harness/iterated-solver pattern you are generalizing.

---

## 8. When to stop and ask (don't thrash)

- Gold is ambiguous or a template is underdetermined → fix or drop the template; never fudge the grader.
- A task would need a registry definition that doesn't exist → stop, surface.
- Real schema disagrees with your assumptions → stop, re-read `src/models/`, re-plan.
- The federal tables are empty/sparse → stop; backfill is a prerequisite.
- You feel tempted to weaken a grader/tolerance/gold to pass → that is the signal to surface, not to proceed.

---

## 9. A starting plan to react to (refine this in plan mode)

1. Scaffold `lab/` (or extend `autoresearch/`): `harness.py` (frozen: connection, instance gen, grading, logging), `families/family1_rollcall.py`, `families/family10_integrity.py`, `traces.py`, `registry/` (scaffold).
2. Implement the harness + one Family 1 template end-to-end (generate → gold-by-SQL → run `qa_agent` → grade → log). Prove the loop on one template before widening.
3. Fill out Family 1 templates; report pass rates.
4. Add Family 10 refusal + provenance; this is where agent improvement (prompting the `qa_agent` to refuse and cite) earns its keep.
5. Trace v0 + registry scaffold.
6. Summary run; hand pass-rate table back to the human.

Build one narrow template end-to-end before widening — prove the slice, then widen.
