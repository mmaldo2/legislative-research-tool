"""FROZEN harness core: DB connection, instance type, gold-validation gate, run loop, JSONL trace.

Mirrors autoresearch/prepare.py's discipline: raw psycopg2 against the same Postgres,
one connection per run, gold computed by trusted SQL. The run loop, the gold-validation
gate, and the grading dispatch are the frozen core — not edited to make a task pass.
"""

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2

from lab.graders import REFUSAL, grade

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


def run(template, solvers, n: int, seed: int, valid_options: set[str]) -> dict:
    """Generate instances for one template, run each solver, grade, and log a JSONL trace.

    Returns per-solver results: {solver_name: [(instance_id, is_refusal, passed), ...]}.
    """
    conn = get_connection()
    try:
        instances = template.generate(conn, n, seed)
    finally:
        conn.close()  # load-phase only; solvers/graders touch no DB in v1

    for inst in instances:
        validate_gold(inst, valid_options)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_path = RUNS_DIR / f"{ts}.jsonl"

    results: dict[str, list[tuple[str, bool, bool]]] = {s.name: [] for s in solvers}
    with open(out_path, "a", encoding="utf-8") as f:
        for solver in solvers:
            for inst in instances:
                answer = solver.solve(inst)
                passed = grade(inst.grader, inst.gold, answer)
                results[solver.name].append((inst.instance_id, inst.is_refusal, passed))
                f.write(
                    json.dumps(
                        {
                            **asdict(inst),
                            "solver": solver.name,
                            "answer": answer,
                            "pass": passed,
                            "seed": seed,
                            "engine": "postgres",
                            "model": solver.name,  # sentinel until the live-agent slice
                            "prompt_version": None,
                            "cost": None,
                        }
                    )
                    + "\n"
                )
    return results
