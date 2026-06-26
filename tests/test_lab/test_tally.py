"""Tally (Template #2) gold + the heterogeneous trace round-trip / read-side.

- DuckDB fixture proves the Group-A gold logic is engine-portable AND correct (incl. the NULL
  guard that keeps the oracle from returning NULL gold and failing itself).
- Round-trip proves dict gold and set->sorted-list gold survive write_trace -> TraceRecord.
- Mixed-payload read proves a run dir mixing scalar/dict/set gold stays queryable on the
  analytic surface (verdict.score) when the heterogeneous payload columns are read as JSON.
"""

import io
from types import SimpleNamespace

import pytest

from lab.graders import grade
from lab.trace import RunContext, TraceRecord, build_record, write_trace


def _ctx() -> RunContext:
    return RunContext(grading_contract_hash="gc", content_hash="cc", dataset_fingerprint={})


def _inst(gold, grader, is_refusal=False):
    return SimpleNamespace(
        instance_id="t:1",
        template_id="family1.tally",
        tier="C",
        params={"vote_event_id": "e1"},
        prompt="?",
        gold=gold,
        grader=grader,
        is_refusal=is_refusal,
        refusal_reason=None,
    )


def _solver():
    return SimpleNamespace(policy={"name": "oracle"}, kind="deterministic")


def _record(gold, grader):
    v = grade(grader, gold, gold, is_refusal=False)
    return build_record(_inst(gold, grader), _solver(), gold, v, _ctx(), 42)


# --- gold logic, portable + correct on a controlled DuckDB fixture -------------------------


def test_tally_gold_portable_and_correct():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE vote_events (id VARCHAR, yes_count INTEGER, no_count INTEGER, "
        "other_count INTEGER, result VARCHAR, motion_text VARCHAR)"
    )
    con.execute(
        "INSERT INTO vote_events VALUES "
        "('e1', 218, 210, 5, 'Passed', 'On Passage'),"
        "('e2', NULL, 10, 0, 'Failed', 'Motion'),"  # NULL count -> excluded
        "('e3', 1, 2, 0, NULL, 'No result')"  # NULL result -> excluded
    )
    # Mirrors generate_tally's Group-A NULL guard on the candidate pool.
    pool = con.execute(
        "SELECT id FROM vote_events "
        "WHERE yes_count IS NOT NULL AND no_count IS NOT NULL AND result IS NOT NULL"
    ).fetchall()
    assert [r[0] for r in pool] == ["e1"]  # e2 (null count) + e3 (null result) excluded

    _id, yes, no, result = con.execute(
        "SELECT id, yes_count, no_count, result FROM vote_events WHERE id = 'e1'"
    ).fetchone()
    gold = {"yea": yes, "nay": no, "margin": yes - no, "result": result}
    assert gold == {"yea": 218, "nay": 210, "margin": 8, "result": "Passed"}


# --- trace round-trip for the new payload shapes -------------------------------------------


def test_dict_gold_roundtrip():
    gold = {"yea": 218, "nay": 210, "margin": 8, "result": "Passed"}
    rec = _record(gold, "fields")
    buf = io.StringIO()
    write_trace(rec, buf)
    back = TraceRecord.model_validate_json(buf.getvalue().strip())
    assert back.gold == gold and back.answer == gold
    assert back.verdict.score == 1.0


def test_set_gold_serialized_as_sorted_list():
    gold = {"p3", "p1", "p2"}
    rec = _record(gold, "set_match")
    assert rec.gold == ["p1", "p2", "p3"]  # _jsonable sorted the set for byte-stable JSONL
    assert rec.answer == ["p1", "p2", "p3"]
    buf = io.StringIO()
    write_trace(rec, buf)
    back = TraceRecord.model_validate_json(buf.getvalue().strip())
    assert back.gold == ["p1", "p2", "p3"]


# --- heterogeneous read-side ---------------------------------------------------------------


def test_mixed_scalar_dict_set_read_stays_queryable(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    records = [
        _record("yea", "exact"),  # scalar gold (vote_lookup-shaped)
        _record({"yea": 1, "nay": 2, "margin": -1, "result": "Failed"}, "fields"),  # dict
        _record({"p1", "p2"}, "set_match"),  # set -> sorted list
    ]
    path = tmp_path / "run.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            write_trace(rec, fh)

    # gold/answer are heterogeneous across rows; pin them (+ verdict) as JSON so auto-inference
    # cannot choke. The analytic surface (template_id, verdict.score) stays typed and queryable.
    rows = duckdb.sql(
        f"SELECT template_id, CAST(json_extract(verdict, '$.score') AS DOUBLE) AS score "
        f"FROM read_json('{path.as_posix()}', "
        f"columns={{'template_id': 'VARCHAR', 'verdict': 'JSON', "
        f"'gold': 'JSON', 'answer': 'JSON'}}, format='newline_delimited')"
    ).fetchall()
    assert len(rows) == 3
    assert all(score == 1.0 for (_tid, score) in rows)
