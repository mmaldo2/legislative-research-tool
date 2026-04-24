import json
import subprocess
import sys
from pathlib import Path

from legal_lm.eval.teacher_batch_audit import audit_examples
from legal_lm.teacher_loop import evaluate_and_log_batch, init_results_tsv, load_best_score


def make_example(example_id: str, **overrides):
    example = {
        "id": example_id,
        "source": "synthetic_rule_qa",
        "task_family": "rule_reasoning",
        "user_prompt": f"Question for {example_id}?",
        "teacher_answer": f"Answer for {example_id}",
        "teacher_reasoning_short": f"Reasoning for {example_id}",
        "teacher_rubric_points": ["Names the controlling rule", "States the conclusion clearly"],
        "teacher_confidence": "high",
        "split": "train",
    }
    example.update(overrides)
    return example


def test_audit_examples_flags_duplicates_missing_fields_and_test_leakage():
    examples = [
        make_example("ex-1", user_prompt="What is hearsay?"),
        make_example("ex-2", user_prompt="What is hearsay?", teacher_answer=""),
        make_example("ex-3", split="test"),
    ]

    report = audit_examples(examples)

    assert report["valid"] is False
    assert report["summary"]["duplicate_prompt_count"] == 1
    assert report["summary"]["invalid_example_count"] == 2
    assert any("duplicate user_prompt" in error for error in report["batch_errors"])
    assert any("test split" in error for error in report["batch_errors"])
    assert "row-2:ex-2" in report["example_errors"]
    assert any("teacher_answer" in error for error in report["example_errors"]["row-2:ex-2"])


def test_audit_examples_rejects_non_object_rows_without_crashing():
    report = audit_examples([make_example("ex-1"), "not an object"])

    assert report["valid"] is False
    assert report["summary"]["invalid_example_count"] == 1
    assert "row-2:non-object" in report["example_errors"]
    assert any("JSON object" in error for error in report["example_errors"]["row-2:non-object"])


def test_audit_examples_rejects_duplicate_ids_without_under_counting_invalid_rows():
    examples = [
        make_example("dup-id", teacher_answer=""),
        make_example("dup-id", teacher_answer="", user_prompt="A different prompt?"),
    ]

    report = audit_examples(examples)

    assert report["valid"] is False
    assert report["summary"]["duplicate_id_count"] == 1
    assert report["summary"]["invalid_example_count"] == 2
    assert any("duplicate id" in error for error in report["batch_errors"])
    assert {"row-1:dup-id", "row-2:dup-id"}.issubset(report["example_errors"].keys())


def test_audit_examples_uses_row_keys_to_avoid_error_key_collisions():
    examples = [
        make_example("dup#2", teacher_answer=""),
        make_example("dup", teacher_answer="", user_prompt="Second prompt?"),
        make_example("dup", teacher_answer="", user_prompt="Third prompt?"),
        "not an object",
    ]

    report = audit_examples(examples)

    assert report["summary"]["invalid_example_count"] == 4
    assert report["summary"]["duplicate_id_count"] == 1
    assert {
        "row-1:dup#2",
        "row-2:dup",
        "row-3:dup",
        "row-4:non-object",
    }.issubset(report["example_errors"].keys())


def test_audit_examples_rejects_empty_batch():
    report = audit_examples([])

    assert report["valid"] is False
    assert report["score"] == 0.0
    assert report["summary"]["total_examples"] == 0
    assert any("at least one example" in error for error in report["batch_errors"])


def test_audit_examples_scores_clean_batch_highly():
    examples = [make_example("ex-1"), make_example("ex-2")]

    report = audit_examples(examples)

    assert report["valid"] is True
    assert report["score"] == 100.0
    assert report["summary"]["valid_example_count"] == 2
    assert report["batch_errors"] == []
    assert report["example_errors"] == {}


def test_teacher_loop_keeps_first_batch_and_discards_worse_batch(tmp_path: Path):
    results_path = tmp_path / "results.tsv"
    init_results_tsv(results_path)

    first_report = audit_examples([make_example("ex-1"), make_example("ex-2")])
    first_result = evaluate_and_log_batch(
        results_path=results_path,
        run_id="run-1",
        batch_id="batch-1",
        description="baseline batch",
        audit_report=first_report,
        student_metric=0.42,
    )

    assert first_result["status"] == "keep"
    assert load_best_score(results_path) == 100.0

    worse_report = audit_examples(
        [make_example("ex-3"), make_example("ex-4", teacher_confidence="medium", teacher_answer="")]
    )
    worse_result = evaluate_and_log_batch(
        results_path=results_path,
        run_id="run-1",
        batch_id="batch-2",
        description="worse batch",
        audit_report=worse_report,
        student_metric=0.40,
    )

    assert worse_result["status"] == "discard"

    rows = results_path.read_text().strip().splitlines()
    assert rows[0] == "run_id\tbatch_id\tteacher_batch_score\tstudent_metric\tstatus\tdescription"
    assert len(rows) == 3
    assert rows[1].endswith("\tkeep\tbaseline batch")
    assert rows[2].endswith("\tdiscard\tworse batch")


def test_evaluate_and_log_batch_prefers_student_metric_when_present(tmp_path: Path):
    results_path = tmp_path / "results.tsv"
    init_results_tsv(results_path)

    base_report = audit_examples([make_example("ex-1"), make_example("ex-2")])
    improved_score_report = audit_examples([make_example("ex-3"), make_example("ex-4")])
    weaker_report = audit_examples([make_example("ex-5"), make_example("ex-6")])

    first = evaluate_and_log_batch(
        results_path=results_path,
        run_id="run-1",
        batch_id="batch-1",
        description="student baseline",
        audit_report=base_report,
        student_metric=0.50,
    )
    second = evaluate_and_log_batch(
        results_path=results_path,
        run_id="run-1",
        batch_id="batch-2",
        description="student improved",
        audit_report=improved_score_report,
        student_metric=0.75,
    )
    third = evaluate_and_log_batch(
        results_path=results_path,
        run_id="run-1",
        batch_id="batch-3",
        description="batch score only improved",
        audit_report=weaker_report,
        student_metric=0.60,
    )

    assert first["status"] == "keep"
    assert second["status"] == "keep"
    assert third["status"] == "discard"


def test_init_results_tsv_repairs_empty_existing_file(tmp_path: Path):
    results_path = tmp_path / "results.tsv"
    results_path.write_text("")

    init_results_tsv(results_path)

    assert (
        results_path.read_text()
        == "run_id\tbatch_id\tteacher_batch_score\tstudent_metric\tstatus\tdescription\n"
    )


def test_load_best_score_handles_headerless_rows_and_ignores_non_finite_scores(tmp_path: Path):
    results_path = tmp_path / "results.tsv"
    results_path.write_text(
        "run-1\tbatch-1\t97.5\t\tkeep\theaderless first row\n"
        "run-2\tbatch-2\tnan\t\tkeep\tbad row\n"
        "run-3\tbatch-3\t95.0\t\tdiscard\tignored discard\n"
    )

    assert load_best_score(results_path) == 97.5


def test_load_best_score_ignores_malformed_rows(tmp_path: Path):
    results_path = tmp_path / "results.tsv"
    results_path.write_text(
        "run_id\tbatch_id\tteacher_batch_score\tstudent_metric\tstatus\tdescription\n"
        "broken-row\n"
        "run-1\tbatch-1\t97.5\t\tkeep\tvalid row\n"
    )

    assert load_best_score(results_path) == 97.5


def test_evaluate_and_log_batch_sanitizes_description_control_characters(tmp_path: Path):
    results_path = tmp_path / "results.tsv"
    init_results_tsv(results_path)

    report = audit_examples([make_example("ex-1"), make_example("ex-2")])
    evaluate_and_log_batch(
        results_path=results_path,
        run_id="run\t1",
        batch_id="batch\n1",
        description="baseline\nwith\ttabs\x1b[31m\x00",
        audit_report=report,
    )

    rows = results_path.read_text().strip().splitlines()
    assert len(rows) == 2
    assert rows[1] == "run 1\tbatch 1\t100.0\t\tkeep\tbaseline with tabs [31m"
    assert "\x1b" not in rows[1]
    assert "\x00" not in rows[1]


def test_evaluate_and_log_batch_repairs_missing_trailing_newline_before_append(tmp_path: Path):
    results_path = tmp_path / "results.tsv"
    results_path.write_text("run-0\tbatch-0\t90.0\t\tkeep\tlegacy row")

    report = audit_examples([make_example("ex-1"), make_example("ex-2")])
    evaluate_and_log_batch(
        results_path=results_path,
        run_id="run-1",
        batch_id="batch-1",
        description="new row",
        audit_report=report,
    )

    rows = results_path.read_text().splitlines()
    assert rows == [
        "run-0\tbatch-0\t90.0\t\tkeep\tlegacy row",
        "run-1\tbatch-1\t100.0\t\tkeep\tnew row",
    ]


def test_audit_batch_cli_reports_invalid_json_without_traceback(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    batch_path = tmp_path / "invalid.jsonl"
    results_path = tmp_path / "results.tsv"
    init_results_tsv(results_path)
    batch_path.write_text('{"id":"ok"}\n{not valid json}\n')

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "audit-batch",
            str(batch_path),
            str(results_path),
            "run-1",
            "batch-1",
            "invalid json batch",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "crash"
    assert payload["line_number"] == 2
    assert "Invalid JSON" in payload["error"]
