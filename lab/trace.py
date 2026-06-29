"""FROZEN trace plumbing: the v1 TraceRecord, the single write_trace chokepoint, and the
once-per-run audit stamps (split content/contract hashes + dataset fingerprint).

JSONL is the source of truth (append-only, git-diffable, ships straight to a training
pipeline); DuckDB is the OLAP read-side on demand:
    duckdb.sql("SELECT * FROM read_json_auto('lab/runs/*.jsonl')")
NB: `gold`/`answer` are heterogeneous across templates (scalar option, dict, set->sorted-list),
so for a MIXED run dir pin those payload columns as JSON to keep auto-inference from choking,
e.g. read_json('lab/runs/*.jsonl', columns={'gold':'JSON','answer':'JSON', ...}). The analytic
surface (verdict.score, subscores, template_id, solver_kind) is monotyped regardless.

The record shape is forward-compatible for the live agent (policy/trajectory/raw + token/
cost sentinels) so perishable rollouts never need a schema migration to be captured.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from lab.scoring import Verdict
from src.ingestion.vote_parsers import (
    CHAMBER_HOUSE,
    CHAMBER_SENATE,
    OPTION_BUCKETS,
    VOTE_OPTION_MAP,
)

_LAB_DIR = Path(__file__).resolve().parent

# Files whose change is a GRADING-CONTRACT red flag (anti-cheat) vs files that grow with content.
_CONTRACT_FILES = ("scoring.py", "graders.py")
_CONTENT_FILES = ("templates.py", "generate.py", "precompute.py")


def grading_contract_hash() -> str:
    """sha256 over the grading rules + the resolved vocab VALUES. A change here means someone
    touched how answers are scored — a review red flag, not legitimate content growth."""
    h = hashlib.sha256()
    for name in _CONTRACT_FILES:
        h.update((_LAB_DIR / name).read_bytes())
    vocab = {
        "OPTION_BUCKETS": list(OPTION_BUCKETS),
        "VOTE_OPTION_MAP": VOTE_OPTION_MAP,
        "CHAMBER_HOUSE": CHAMBER_HOUSE,
        "CHAMBER_SENATE": CHAMBER_SENATE,
    }
    h.update(json.dumps(vocab, sort_keys=True).encode())
    return h.hexdigest()


def content_hash() -> str:
    """sha256 over the gold-producing content (templates/sampler/precompute). Grows
    legitimately each phase as templates are added."""
    h = hashlib.sha256()
    for name in _CONTENT_FILES:
        h.update((_LAB_DIR / name).read_bytes())
    return h.hexdigest()


def dataset_fingerprint(conn, pre) -> dict:
    """Per-run DRIFT-DETECTION stamp (NOT reproduction — gold is computed against a mutating
    live DB). Engine-portable SQL. NB: vote_events/vote_records have no updated_at, so in-place
    count/option edits are invisible here. The vote_records count is reused from the precompute
    aggregate (`pre.total_vote_records`) to avoid a second full scan of the 5.4M-row table."""
    cur = conn.cursor()

    def scalar(sql: str) -> Any:
        cur.execute(sql)
        return cur.fetchone()[0]

    return {
        "vote_events": scalar("SELECT COUNT(*) FROM vote_events"),
        "vote_records": pre.total_vote_records,
        "people": scalar("SELECT COUNT(*) FROM people"),
        "sessions": scalar("SELECT COUNT(*) FROM sessions"),
        "bills": scalar("SELECT COUNT(*) FROM bills"),
        "completed_congresses": len(pre.completed_congresses),
        "max_vote_date": str(scalar("SELECT MAX(vote_date) FROM vote_events")),
        "max_people_updated_at": str(scalar("SELECT MAX(updated_at) FROM people")),
    }


@dataclass(frozen=True)
class RunContext:
    grading_contract_hash: str
    content_hash: str
    dataset_fingerprint: dict


class VerdictModel(BaseModel):
    passed: bool
    score: float
    feedback: str
    subscores: dict[str, float | None]


class TraceRecord(BaseModel):
    trace_schema_version: str = "v1"
    instance_id: str
    template_id: str
    tier: str
    params: dict
    prompt: str
    gold: Any
    grader: str
    is_refusal: bool
    refusal_reason: str | None = None
    policy: dict  # what GEPA optimizes; {"name": ...} for deterministic solvers
    solver_kind: Literal["deterministic", "agent"]
    answer: Any
    trajectory: list[dict] = []
    raw: str  # non-destructive full final text (str(answer) for deterministic solvers)
    verdict: VerdictModel
    seed: int
    engine: str = "postgres"
    grading_contract_hash: str
    content_hash: str
    dataset_fingerprint: dict
    # forward-compat sentinels the live-agent slice fills:
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None  # cost is NOT a subscore — a top-level field only
    # SDK stop reason ("success" | budget/turn truncation | error). Lets the lift analysis EXCLUDE
    # non-success rollouts post-hoc from the jsonl (a truncation is a protocol miss, not a wrong
    # answer). Agent-sdk only; None for messages-api / deterministic solvers.
    result_subtype: str | None = None


def _jsonable(value: Any) -> Any:
    """Coerce set-valued gold/answer to a SORTED list so the JSONL is byte-stable across seeded
    re-runs (a Python set serializes with nondeterministic element order). Dicts/scalars pass
    through unchanged (Pydantic preserves dict insertion order)."""
    if isinstance(value, set | frozenset):
        return sorted(value)
    return value


def build_record(
    inst,
    solver,
    answer: Any,
    verdict: Verdict,
    ctx: RunContext,
    seed: int,
    extras: dict | None = None,
) -> TraceRecord:
    """Project an Instance + solver + Verdict into the validated trace record (Pydantic
    validates on construction).

    `extras` is the ADDITIVE agent-telemetry channel (a live solver publishes it via
    `solver.trace_extras`): `trajectory` (tool calls), `raw` (final prose), `latency_ms`, and the
    token/cost sentinels. Deterministic solvers pass `extras=None` and keep the original defaults
    (`trajectory=[]`, `raw=str(answer)`, all sentinels None) — so their records are unchanged."""
    answer = _jsonable(answer)
    extras = extras or {}
    return TraceRecord(
        instance_id=inst.instance_id,
        template_id=inst.template_id,
        tier=inst.tier,
        params=inst.params,
        prompt=inst.prompt,
        gold=_jsonable(inst.gold),
        grader=inst.grader,
        is_refusal=inst.is_refusal,
        refusal_reason=inst.refusal_reason,
        policy=solver.policy,
        solver_kind=solver.kind,
        answer=answer,
        trajectory=extras.get("trajectory", []),
        raw=extras.get("raw", str(answer)),
        verdict=VerdictModel(
            passed=verdict.passed,
            score=verdict.score,
            feedback=verdict.feedback,
            subscores=dict(verdict.subscores),
        ),
        seed=seed,
        grading_contract_hash=ctx.grading_contract_hash,
        content_hash=ctx.content_hash,
        dataset_fingerprint=ctx.dataset_fingerprint,
        latency_ms=extras.get("latency_ms"),
        input_tokens=extras.get("input_tokens"),
        output_tokens=extras.get("output_tokens"),
        cost=extras.get("cost"),
        result_subtype=extras.get("result_subtype"),
    )


def write_trace(record: TraceRecord, fh) -> None:
    """The ONLY writer. The record was already validated at construction (build_record);
    here we serialize exactly one JSON line and append."""
    fh.write(record.model_dump_json() + "\n")
