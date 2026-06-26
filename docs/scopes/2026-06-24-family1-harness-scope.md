---
date: 2026-06-24
topic: Family 1 graded-task foundation (Condorcet Lab roll-call benchmark)
scope-mode: selective-expand
status: approved
---

# Scope: Family 1 Graded-Task Foundation

## Problem
The Condorcet Lab's factual trust floor — **Family 1** (roll-call retrieval/aggregation) — needs auto-gradable benchmark tasks. The vote data now exists (13,848 events / 5.4M records, Congress 110–119, both chambers), but there's no harness to turn it into graded tasks. Build the **graded-task foundation** (generators + gold-by-SQL + code-graders + traces), validated *without* the live agent — the durable "author once, grade forever" moat asset.

## In Scope
- New **agent-eval harness module** that borrows `autoresearch/`'s discipline (frozen core, gold-by-trusted-SQL, auto-logged runs) but is *task-eval-shaped* (NL question → answer → code-graded pass/fail), not ML-prediction-shaped.
- **Family 1 generators** (≥6 templates): vote lookup; tally (yea/nay/margin/pass-fail); party/chamber breakdown; party-line vs. defection count; members who crossed party (set); per-member vote summary over a window; pairwise agreement; closest votes by margin.
- **Gold computed by trusted, engine-portable SQL** over `vote_events`/`vote_records`/`people`/`bills` (no hand-written answer keys; no Postgres-only syntax → DuckDB-ready).
- **Code-graders**: `exact` / `set_match` (+ margin/count comparisons), with the frozen-core anti-cheat discipline.
- **Trace schema v0**: training-ready record `{task, template_id, instance, gold, answer, pass/fail, provenance, …}`.
- **Validation without the live agent**: a SQL-oracle solver (returns gold → graders pass) + a deliberately-wrong baseline (graders catch failures). One run command → per-template pass-rate summary.

## Out of Scope
- The **live chat/MCP agent run** (next slice; backend = `claude-sdk`/subscription) and free-text answer extraction.
- The **`get_bill_votes` / roll-call agent tools** (part of the agent slice — the agent can't reach votes today).
- Family 10 (integrity/refusal) and Families 2–9; the definition registry with real definitions (Family 1 is clean `C`, needs none).
- Point-in-time / leakage tasks (later stretch).

## Key Constraints (Condorcet hard rules)
- Gold never hand-authored — trusted SQL only; engine-portable. Never weaken a grader or simplify gold to pass.
- Frozen core (gold SQL + graders) is the immutable boundary (mirror `prepare.py`'s "don't modify" rule).
- Never fabricate; every returned fact carries a source record ID; point-in-time discipline.

## Codebase Context
- Borrow `autoresearch/prepare.py` discipline (frozen DB-backed gold, `experiments/` + `summary.jsonl` logging, lean `get_data()`-style interface) — verified at `prepare.py:33-302`. Build NEW files, don't extend the ML scaffold.
- Vote schema: `vote_records.option ∈ {yea,nay,present,not_voting}`, `people.id`=bioguide + `party`, `vote_events`(yes/no/other_count, result, vote_date, chamber).
- Live-agent entry (next slice): `run_agentic_chat()` `src/services/chat_service.py:87`.

## Open Questions (for /ce:plan)
- Module location: new top-level `lab/` (handoff's suggestion) vs. `autoresearch/lab/`.
- Harness DB driver: psycopg2 (mirror `prepare.py`, sync) vs. async SQLAlchemy.
- Trace storage for v1: `experiments/`-style JSONL (simplest, no live model yet) vs. extend `ai_analyses` (matters more for the agent slice).
- Final template list + per-template grading mode; an empty-DuckDB engine-portability smoke test.
