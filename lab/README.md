# Condorcet Lab — Family 1 harness (`lab/`)

A frozen, training-grade benchmark harness. It generates roll-call retrieval/aggregation
tasks, computes gold by **trusted, engine-portable SQL** over the live federal Postgres,
grades answers into a `Verdict`, and appends a JSONL trace per `(solver, instance)`.

The traces are the point: every live-agent rollout is a perishable, point-in-time artifact
that cannot be re-run, so the record shape (`lab/trace.py`, `trace_schema_version`) is frozen
to serve the live agent + GEPA + RL/SFT from day one. The deterministic solvers
(oracle / wrong-baseline / over-refuse) exist to validate the graders and exercise the trace
shape — they are **not** training data (`solver_kind="deterministic"`; filter them out).

## Run

```bash
uv run python -m lab.run --n 20 --seed 42      # live harness (needs Docker Postgres)
uv run python -m pytest tests/test_lab/        # hermetic tests (no DB)
```

Reproducibility key is `(seed, dataset_fingerprint)`, never seed alone — gold is computed
against a mutating live DB. Read traces with DuckDB:

```python
duckdb.sql("SELECT * FROM read_json_auto('lab/runs/*.jsonl')")
```

## Frozen core & the anti-cheat hashes

The frozen core (`scoring.py`, `graders.py`, `harness.py` run loop, the gold SQL) must never
be weakened to inflate a pass rate. Freezing is **convention + hash-attestation**, not a hard
runtime gate — every trace records two hashes:

- **`grading_contract_hash`** — `scoring.py` + `graders.py` + resolved vocab values. **A change
  here is a PR red flag**: it means someone altered *how answers are scored*. Justify it.
- **`content_hash`** — `templates.py` + `generate.py` + `precompute.py`. Grows legitimately as
  templates are added each phase; a change here is expected content growth, not a red flag.

`dataset_fingerprint` is **drift-detection, not reproduction** (`vote_events`/`vote_records`
have no `updated_at`, so in-place edits are invisible).

## Schema versioning

`trace_schema_version` is `"v1"`. Forward strategy: **readers tolerate older versions** — never
delete-on-bump for post-freeze data. Activating the reserved `grounded` subscore is a v2 bump
that re-baselines the invariants; v1 `score`/`passed` are not comparable across that boundary.

## Hard rules (non-negotiable)

Never fabricate a vote/count; gold only by trusted SQL (never hand-authored — test fixture
literals are expectations, not gold); "not in the data" is a valid, graded answer; engine-portable
SQL (DuckDB-ready); point-in-time discipline; a missing registry definition is a STOP-and-surface.
