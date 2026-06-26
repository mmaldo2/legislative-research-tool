"""Trace round-trip + validation tests for lab/trace.py (no Postgres needed)."""

import pytest
from pydantic import ValidationError

from lab.graders import grade
from lab.harness import Instance
from lab.solvers import SqlOracleSolver
from lab.trace import RunContext, TraceRecord, build_record, write_trace


def _record() -> TraceRecord:
    inst = Instance(
        instance_id="family1.vote_lookup:42:e1:p1",
        template_id="family1.vote_lookup",
        tier="C",
        params={"person_id": "p1", "vote_event_id": "e1"},
        prompt="How did X vote on e1?",
        gold="nay",
        grader="exact",
        is_refusal=False,
    )
    solver = SqlOracleSolver()
    answer = solver.solve(inst)
    verdict = grade(inst.grader, inst.gold, answer, is_refusal=inst.is_refusal)
    ctx = RunContext("contract-hash", "content-hash", {"vote_events": 1})
    return build_record(inst, solver, answer, verdict, ctx, seed=42)


class TestRoundTrip:
    def test_write_then_validate_identical(self, tmp_path):
        rec = _record()
        path = tmp_path / "run.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            write_trace(rec, fh)
        line = path.read_text(encoding="utf-8").strip()
        assert TraceRecord.model_validate_json(line) == rec

    def test_record_shape(self):
        rec = _record()
        assert rec.trace_schema_version == "v1"
        assert rec.solver_kind == "deterministic"
        assert rec.policy == {"name": "oracle"}
        assert rec.raw == "nay"  # non-destructive capture of the final text
        assert rec.verdict.passed is True and rec.verdict.score == 1.0
        # subscores serialize as numbers, never booleans (the training-data-poisoning guard)
        for value in rec.verdict.subscores.values():
            assert value is None or (isinstance(value, float) and not isinstance(value, bool))


class TestValidation:
    def test_malformed_verdict_is_rejected(self):
        # Pydantic validates the verdict PAYLOAD, not just the envelope.
        with pytest.raises(ValidationError):
            TraceRecord(
                instance_id="x",
                template_id="t",
                tier="C",
                params={},
                prompt="q",
                gold="nay",
                grader="exact",
                is_refusal=False,
                policy={"name": "x"},
                solver_kind="deterministic",
                answer="nay",
                raw="nay",
                verdict={"passed": True, "score": "not-a-number", "feedback": "f", "subscores": {}},
                seed=1,
                grading_contract_hash="a",
                content_hash="b",
                dataset_fingerprint={},
            )


class TestDuckDBReadSide:
    def test_read_json_auto(self, tmp_path):
        duckdb = pytest.importorskip("duckdb")
        rec = _record()
        path = tmp_path / "run.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            write_trace(rec, fh)
        rows = duckdb.sql(f"SELECT instance_id FROM read_json_auto('{path.as_posix()}')").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "family1.vote_lookup:42:e1:p1"
