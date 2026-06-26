"""FROZEN harness core: DB connection, instance type, gold-validation gate, run loop.

Mirrors autoresearch/prepare.py's discipline: raw psycopg2 against the same Postgres,
one connection per run, gold computed by trusted SQL. The run loop, the gold-validation
gate, and the grading dispatch are the frozen core — not edited to make a task pass.

The connection is opened only for the load phase (precompute + fingerprint + generate);
solvers and graders touch no DB in v1, so it is closed before the solve/grade/write loop.
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2

from lab.graders import REFUSAL, grade
from lab.precompute import precompute
from lab.trace import (
    RunContext,
    build_record,
    content_hash,
    dataset_fingerprint,
    grading_contract_hash,
    write_trace,
)

DEFAULT_DB_URL = "postgresql+asyncpg://legis:legis_dev@localhost:5432/legis"
RUNS_DIR = Path("lab/runs")


def get_db_url() -> str:
    """Same DATABASE_URL the app uses, with the asyncpg dialect stripped for psycopg2."""
    return re.sub(r"\+asyncpg", "", os.environ.get("DATABASE_URL", DEFAULT_DB_URL))


def get_connection():
    return psycopg2.connect(get_db_url())


@dataclass
class Instance:
    instance_id: str  # "{template_id}:{seed}:{key}"
    template_id: str
    tier: str  # cleanliness tier (Family 1 = "C")
    params: dict  # structured params the solver/agent answers over
    prompt: str  # NL question (for the trace / the future live agent)
    gold: Any  # the trusted-SQL gold answer, or REFUSAL
    grader: str  # "exact" | "refusal_correct"
    is_refusal: bool  # True => this is a "not in the data" instance
    refusal_reason: str | None = None  # e.g. "person_not_in_data" (refusal instances only)


def validate_gold(inst: Instance, valid_options: set[str]) -> None:
    """Gold-validation gate: no answerable instance may carry empty/undefined gold,
    and a refusal instance's gold must be exactly REFUSAL (never a numeric/option)."""
    if inst.is_refusal:
        if inst.gold != REFUSAL:
            raise ValueError(
                f"refusal instance {inst.instance_id} has non-refusal gold {inst.gold!r}"
            )
        return
    if inst.gold is None or inst.gold == "" or inst.gold == REFUSAL:
        raise ValueError(
            f"answerable instance {inst.instance_id} has empty/invalid gold {inst.gold!r}"
        )
    if inst.template_id.endswith("vote_lookup") and inst.gold not in valid_options:
        raise ValueError(
            f"{inst.instance_id}: gold {inst.gold!r} not in canonical options {valid_options}"
        )
    # Composite gold gate: a dict gold must be non-empty with every value a non-None int/str
    # (an empty {} would grade as a vacuous pass; a None field would silently mis-grade).
    if inst.grader == "fields":
        if not isinstance(inst.gold, dict) or not inst.gold:
            raise ValueError(f"{inst.instance_id}: 'fields' gold must be a non-empty dict")
        for key, val in inst.gold.items():
            if val is None or isinstance(val, bool) or not isinstance(val, int | str):
                raise ValueError(
                    f"{inst.instance_id}: 'fields' gold[{key!r}]={val!r} must be a non-None int/str"
                )
    # Set gold gate: must be a collection; the EMPTY set is valid (e.g. zero defectors).
    if inst.grader == "set_match" and not isinstance(inst.gold, set | list | tuple):
        raise ValueError(f"{inst.instance_id}: 'set_match' gold must be a set/list/tuple")
    # Scalar-int gold gate (e.g. a defection count; 0 is valid). bool is NOT an int here.
    if inst.grader == "exact_int" and (
        isinstance(inst.gold, bool) or not isinstance(inst.gold, int)
    ):
        raise ValueError(f"{inst.instance_id}: 'exact_int' gold must be an int, got {inst.gold!r}")


def run(template, solvers, n: int, seed: int, valid_options: set[str]) -> dict:
    """Generate instances for one template, run each solver, grade to a Verdict, and log a
    validated JSONL trace via the single write_trace chokepoint.

    Returns per-solver results: {solver_name: [(instance_id, is_refusal, verdict), ...]}.
    """
    conn = get_connection()
    try:
        pre = precompute(conn)
        ctx = RunContext(
            grading_contract_hash=grading_contract_hash(),
            content_hash=content_hash(),
            dataset_fingerprint=dataset_fingerprint(conn, pre),
        )
        instances = template.generate(conn, n, seed, pre)
    finally:
        conn.close()  # load-phase only; solvers/graders touch no DB in v1

    if not instances:
        raise RuntimeError(
            f"no instances generated (empty/short DB?); fingerprint={ctx.dataset_fingerprint}"
        )
    for inst in instances:
        validate_gold(inst, valid_options)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_path = RUNS_DIR / f"{ts}.jsonl"

    results: dict[str, list[tuple[str, bool, Any]]] = {s.name: [] for s in solvers}
    with open(out_path, "a", encoding="utf-8") as fh:
        for solver in solvers:
            for inst in instances:
                answer = solver.solve(inst)
                verdict = grade(inst.grader, inst.gold, answer, is_refusal=inst.is_refusal)
                write_trace(build_record(inst, solver, answer, verdict, ctx, seed), fh)
                results[solver.name].append((inst.instance_id, inst.is_refusal, verdict))
    return results
