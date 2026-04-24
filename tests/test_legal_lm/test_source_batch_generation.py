import json
import re
import subprocess
import sys
from pathlib import Path

from legal_lm.eval.teacher_batch_audit import audit_examples
from legal_lm.teacher_loop import (
    build_teacher_example_from_source,
    generate_batch_from_sources,
    run_student_smoke_eval,
)

DEFINITION_YES_PROMPT = (
    "Clause: 'Personal data means information linked to an individual.' Is this a definition?"
)
DEFINITION_NO_PROMPT = (
    "Clause: 'The agency may issue penalties after notice.' Is this a definition?"
)


def make_source_row(example_id: str, **overrides):
    row = {
        "id": example_id,
        "source": "curated_rule_seed",
        "task_family": "rule_reasoning",
        "user_prompt": f"Question for {example_id}?",
        "reference_answer": f"Answer for {example_id}",
        "reference_reasoning_short": f"Reasoning for {example_id}",
        "reference_rubric_points": ["Name the rule", "State the conclusion"],
        "doctrine": "Evidence",
    }
    row.update(overrides)
    return row


def prompt_token_set(prompt: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", prompt.lower()))


def max_prompt_jaccard(eval_prompt: str, source_rows: list[dict[str, str]]) -> float:
    eval_tokens = prompt_token_set(eval_prompt)
    return max(
        len(eval_tokens & prompt_token_set(row["user_prompt"]))
        / len(eval_tokens | prompt_token_set(row["user_prompt"]))
        for row in source_rows
    )


def best_overlap_source_id(eval_prompt: str, source_rows: list[dict[str, str]]) -> str:
    eval_tokens = prompt_token_set(eval_prompt)
    return max(
        source_rows,
        key=lambda row: len(eval_tokens & prompt_token_set(row["user_prompt"])),
    )["id"]


def test_build_teacher_example_from_source_maps_reference_fields():
    example = build_teacher_example_from_source(make_source_row("src-1"))

    assert example["id"] == "src-1"
    assert example["source"] == "curated_rule_seed"
    assert example["task_family"] == "rule_reasoning"
    assert example["teacher_answer"] == "Answer for src-1"
    assert example["teacher_reasoning_short"] == "Reasoning for src-1"
    assert example["teacher_rubric_points"] == ["Name the rule", "State the conclusion"]
    assert example["teacher_confidence"] == "high"
    assert example["split"] == "train"
    assert example["doctrine"] == "Evidence"


def test_generate_batch_from_sources_is_deterministic_and_without_replacement():
    source_rows = [make_source_row(f"src-{index}") for index in range(5)]

    batch_one = generate_batch_from_sources(source_rows, batch_size=3, seed=7)
    batch_two = generate_batch_from_sources(source_rows, batch_size=3, seed=7)

    assert [row["id"] for row in batch_one] == [row["id"] for row in batch_two]
    assert len(batch_one) == 3
    assert len({row["id"] for row in batch_one}) == 3


def test_generate_batch_from_sources_filters_task_family():
    source_rows = [
        make_source_row("rule-1", task_family="rule_reasoning"),
        make_source_row("def-1", task_family="definition_classification"),
    ]

    batch = generate_batch_from_sources(
        source_rows,
        batch_size=5,
        seed=11,
        task_family="rule_reasoning",
    )

    assert [row["id"] for row in batch] == ["rule-1"]


def test_generate_batch_from_sources_rejects_empty_selection():
    source_rows = [make_source_row("def-1", task_family="definition_classification")]

    try:
        generate_batch_from_sources(
            source_rows,
            batch_size=2,
            seed=5,
            task_family="rule_reasoning",
        )
    except ValueError as exc:
        assert "No eligible source rows" in str(exc)
    else:
        raise AssertionError("Expected generate_batch_from_sources to reject an empty selection")


def test_generate_batch_from_sources_validates_all_eligible_rows_before_sampling():
    source_rows = [
        make_source_row("good-1"),
        make_source_row("bad-1", reference_answer=""),
        make_source_row("good-2"),
    ]

    try:
        generate_batch_from_sources(source_rows, batch_size=1, seed=1, task_family="rule_reasoning")
    except ValueError as exc:
        assert "reference_answer" in str(exc)
    else:
        raise AssertionError(
            "Expected generate_batch_from_sources to reject malformed eligible rows"
        )


def test_generate_batch_cli_writes_batch_jsonl(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    source_path = tmp_path / "source.jsonl"
    output_path = tmp_path / "batch.jsonl"
    source_path.write_text(
        "\n".join([json.dumps(make_source_row("src-1")), json.dumps(make_source_row("src-2"))])
        + "\n"
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "generate-batch",
            str(source_path),
            str(output_path),
            "--batch-size",
            "2",
            "--seed",
            "3",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["status"] == "generated"
    assert payload["num_examples"] == 2

    lines = output_path.read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["teacher_confidence"] == "high"
    assert first["split"] == "train"


def test_generate_batch_cli_rejects_invalid_confidence_and_same_path(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    source_path = tmp_path / "source.jsonl"
    source_path.write_text(json.dumps(make_source_row("src-1")) + "\n")

    invalid_confidence = subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "generate-batch",
            str(source_path),
            str(tmp_path / "batch.jsonl"),
            "--confidence",
            "certain",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert invalid_confidence.returncode != 0

    same_path = subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "generate-batch",
            str(source_path),
            str(source_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert same_path.returncode == 1
    payload = json.loads(same_path.stdout)
    assert payload["status"] == "crash"
    assert "must differ" in payload["error"]


def test_generate_batch_cli_reports_missing_source_path_as_structured_crash(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    missing_source = tmp_path / "missing.jsonl"
    output_path = tmp_path / "batch.jsonl"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "generate-batch",
            str(missing_source),
            str(output_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "crash"
    assert "No such file" in payload["error"] or "missing.jsonl" in payload["error"]


def test_audit_batch_cli_uses_smoke_eval_metric(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    source_path = tmp_path / "definition_source.jsonl"
    batch_path = tmp_path / "definition_batch.jsonl"
    eval_path = tmp_path / "definition_eval.jsonl"
    results_path = tmp_path / "results.tsv"

    source_rows = [
        make_source_row(
            "def-train-1",
            task_family="definition_classification",
            user_prompt=DEFINITION_YES_PROMPT,
            reference_answer="Yes",
            doctrine="Privacy",
        ),
        make_source_row(
            "def-train-2",
            task_family="definition_classification",
            user_prompt=DEFINITION_NO_PROMPT,
            reference_answer="No",
            doctrine="Administrative Law",
        ),
    ]
    eval_rows = [
        make_source_row(
            "def-eval-1",
            task_family="definition_classification",
            user_prompt=DEFINITION_YES_PROMPT,
            reference_answer="Yes",
            doctrine="Privacy",
        ),
        make_source_row(
            "def-eval-2",
            task_family="definition_classification",
            user_prompt=DEFINITION_NO_PROMPT,
            reference_answer="No",
            doctrine="Administrative Law",
        ),
    ]
    source_path.write_text("\n".join(json.dumps(row) for row in source_rows) + "\n")
    eval_path.write_text("\n".join(json.dumps(row) for row in eval_rows) + "\n")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "init-results",
            str(results_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "generate-batch",
            str(source_path),
            str(batch_path),
            "--task-family",
            "definition_classification",
            "--batch-size",
            "2",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

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
            "definition smoke eval",
            "--smoke-eval-path",
            str(eval_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["student_metric"] == 1.0
    assert payload["status"] == "keep"


def test_audit_batch_cli_skips_smoke_eval_for_invalid_teacher_batch(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    batch_path = tmp_path / "invalid_batch.jsonl"
    eval_path = tmp_path / "definition_eval.jsonl"
    results_path = tmp_path / "results.tsv"
    batch_path.write_text(json.dumps("not an object") + "\n")
    eval_path.write_text(
        json.dumps(
            make_source_row(
                "def-eval",
                task_family="definition_classification",
                user_prompt=DEFINITION_YES_PROMPT,
                reference_answer="Yes",
                doctrine="Privacy",
            )
        )
        + "\n"
    )

    subprocess.run(
        [sys.executable, "-m", "legal_lm.teacher_loop", "init-results", str(results_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "audit-batch",
            str(batch_path),
            str(results_path),
            "run-1",
            "batch-invalid",
            "invalid batch",
            "--smoke-eval-path",
            str(eval_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["status"] == "discard"
    assert payload["student_metric"] is None


def test_init_results_cli_reports_bad_results_path_as_structured_crash(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    bad_results_path = tmp_path / "results_dir"
    bad_results_path.mkdir()

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "init-results",
            str(bad_results_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "crash"


def test_audit_batch_cli_reports_bad_results_path_as_structured_crash(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    batch_path = tmp_path / "batch.jsonl"
    bad_results_path = tmp_path / "results_dir"
    bad_results_path.mkdir()
    batch_path.write_text(json.dumps(make_source_row("src-1")) + "\n")

    generated_path = tmp_path / "generated.jsonl"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "generate-batch",
            str(batch_path),
            str(generated_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "legal_lm.teacher_loop",
            "audit-batch",
            str(generated_path),
            str(bad_results_path),
            "run-1",
            "batch-1",
            "bad results path",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "crash"


def test_checked_in_seed_batch_matches_curated_source_and_audits_clean():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/rule_reasoning_source.jsonl"
    batch_path = repo_root / "legal_lm/data/teacher_data/seed/rule_reasoning_batch1.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]
    batch_rows = [json.loads(line) for line in batch_path.read_text().splitlines() if line.strip()]

    assert len(source_rows) == 30
    assert len(batch_rows) == 30
    assert {row["id"] for row in source_rows} == {row["id"] for row in batch_rows}

    report = audit_examples(batch_rows)
    assert report["valid"] is True
    assert report["score"] == 100.0


def test_checked_in_rule_reasoning_seed_batch_matches_curated_source_and_smoke_eval():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/rule_reasoning_source.jsonl"
    batch_path = repo_root / "legal_lm/data/teacher_data/seed/rule_reasoning_batch1.jsonl"
    eval_path = repo_root / "legal_lm/data/eval/rule_reasoning_smoke_eval.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]
    batch_rows = [json.loads(line) for line in batch_path.read_text().splitlines() if line.strip()]
    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    assert len(source_rows) == 30
    assert len(batch_rows) == 30
    assert len(eval_rows) == 6
    assert {row["id"] for row in source_rows} == {row["id"] for row in batch_rows}

    report = audit_examples(batch_rows)
    assert report["valid"] is True
    assert report["score"] == 100.0

    smoke_eval = run_student_smoke_eval(batch_rows, eval_rows)
    reversed_smoke_eval = run_student_smoke_eval(list(reversed(batch_rows)), eval_rows)
    assert smoke_eval["metric_name"] == "accuracy"
    assert smoke_eval["metric_value"] == 1.0
    assert reversed_smoke_eval["metric_value"] == smoke_eval["metric_value"]


def test_checked_in_rule_reasoning_smoke_eval_is_not_paraphrase_close_to_source_rows():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/rule_reasoning_source.jsonl"
    eval_path = repo_root / "legal_lm/data/eval/rule_reasoning_smoke_eval.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]
    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    max_overlap = max(max_prompt_jaccard(row["user_prompt"], source_rows) for row in eval_rows)
    assert max_overlap < 0.7


def test_checked_in_definition_seed_batch_matches_curated_source_and_smoke_eval():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/definition_classification_source.jsonl"
    batch_path = (
        repo_root / "legal_lm/data/teacher_data/seed/definition_classification_batch1.jsonl"
    )
    eval_path = repo_root / "legal_lm/data/eval/definition_classification_smoke_eval.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]
    batch_rows = [json.loads(line) for line in batch_path.read_text().splitlines() if line.strip()]
    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    assert len(source_rows) == 20
    assert len(batch_rows) == 20
    assert len(eval_rows) == 6
    assert {row["id"] for row in source_rows} == {row["id"] for row in batch_rows}

    report = audit_examples(batch_rows)
    assert report["valid"] is True
    assert report["score"] == 100.0

    smoke_eval = run_student_smoke_eval(batch_rows, eval_rows)
    assert smoke_eval["metric_name"] == "accuracy"
    assert smoke_eval["metric_value"] == 0.833333


def test_checked_in_policy_regulatory_qa_seed_batch_matches_curated_source_and_smoke_eval():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/policy_regulatory_qa_source.jsonl"
    batch_path = repo_root / "legal_lm/data/teacher_data/seed/policy_regulatory_qa_batch1.jsonl"
    eval_path = repo_root / "legal_lm/data/eval/policy_regulatory_qa_smoke_eval.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]
    batch_rows = [json.loads(line) for line in batch_path.read_text().splitlines() if line.strip()]
    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    assert len(source_rows) == 30
    assert len(batch_rows) == 30
    assert len(eval_rows) == 6
    assert {row["id"] for row in source_rows} == {row["id"] for row in batch_rows}

    report = audit_examples(batch_rows)
    assert report["valid"] is True
    assert report["score"] == 100.0

    smoke_eval = run_student_smoke_eval(batch_rows, eval_rows)
    reversed_smoke_eval = run_student_smoke_eval(list(reversed(batch_rows)), eval_rows)
    assert smoke_eval["metric_name"] == "accuracy"
    assert smoke_eval["metric_value"] == 1.0
    assert reversed_smoke_eval["metric_value"] == smoke_eval["metric_value"]


def test_checked_in_policy_regulatory_qa_smoke_eval_is_not_paraphrase_close_to_source_rows():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/policy_regulatory_qa_source.jsonl"
    eval_path = repo_root / "legal_lm/data/eval/policy_regulatory_qa_smoke_eval.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]
    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    max_overlap = max(max_prompt_jaccard(row["user_prompt"], source_rows) for row in eval_rows)
    assert max_overlap < 0.75


def test_checked_in_policy_regulatory_qa_smoke_eval_targets_intended_source_rows_under_matcher():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/policy_regulatory_qa_source.jsonl"
    eval_path = repo_root / "legal_lm/data/eval/policy_regulatory_qa_smoke_eval.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]
    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    expected_matches = {
        "policy-qa-eval-001": "policy-qa-src-021",
        "policy-qa-eval-002": "policy-qa-src-022",
        "policy-qa-eval-003": "policy-qa-src-023",
        "policy-qa-eval-004": "policy-qa-src-024",
        "policy-qa-eval-005": "policy-qa-src-029",
        "policy-qa-eval-006": "policy-qa-src-030",
    }
    observed_matches = {
        row["id"]: best_overlap_source_id(row["user_prompt"], source_rows) for row in eval_rows
    }

    assert observed_matches == expected_matches


def test_checked_in_sara_entailment_seed_batch_matches_curated_source_and_smoke_eval():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/sara_entailment_source.jsonl"
    batch_path = repo_root / "legal_lm/data/teacher_data/seed/sara_entailment_batch1.jsonl"
    eval_path = repo_root / "legal_lm/data/eval/sara_entailment_smoke_eval.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]
    batch_rows = [json.loads(line) for line in batch_path.read_text().splitlines() if line.strip()]
    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    assert len(source_rows) == 20
    assert len(batch_rows) == 20
    assert len(eval_rows) == 6
    assert {row["id"] for row in source_rows} == {row["id"] for row in batch_rows}

    report = audit_examples(batch_rows)
    assert report["valid"] is True
    assert report["score"] == 100.0

    smoke_eval = run_student_smoke_eval(batch_rows, eval_rows)
    reversed_smoke_eval = run_student_smoke_eval(list(reversed(batch_rows)), eval_rows)
    assert smoke_eval["metric_name"] == "accuracy"
    assert smoke_eval["metric_value"] == 1.0
    assert reversed_smoke_eval["metric_value"] == smoke_eval["metric_value"]


def test_checked_in_sara_entailment_smoke_eval_is_not_paraphrase_close_to_source_rows():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/sara_entailment_source.jsonl"
    eval_path = repo_root / "legal_lm/data/eval/sara_entailment_smoke_eval.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]
    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    max_overlap = max(max_prompt_jaccard(row["user_prompt"], source_rows) for row in eval_rows)
    assert max_overlap < 0.72


def test_checked_in_sara_entailment_smoke_eval_targets_intended_source_rows_under_matcher():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/sara_entailment_source.jsonl"
    eval_path = repo_root / "legal_lm/data/eval/sara_entailment_smoke_eval.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]
    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    expected_matches = {
        "sara-eval-001": "sara-src-001",
        "sara-eval-002": "sara-src-004",
        "sara-eval-003": "sara-src-015",
        "sara-eval-004": "sara-src-008",
        "sara-eval-005": "sara-src-010",
        "sara-eval-006": "sara-src-011",
    }
    observed_matches = {
        row["id"]: best_overlap_source_id(row["user_prompt"], source_rows) for row in eval_rows
    }

    assert observed_matches == expected_matches


def test_core_mixed_sources_include_all_four_families():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/core_mixed_sources.jsonl"

    source_rows = [
        json.loads(line) for line in source_path.read_text().splitlines() if line.strip()
    ]

    families = [row["task_family"] for row in source_rows]
    assert len(source_rows) == 100
    assert set(families) == {
        "rule_reasoning",
        "definition_classification",
        "policy_regulatory_qa",
        "sara_entailment",
    }
    assert families.count("rule_reasoning") == 30
    assert families.count("definition_classification") == 20
    assert families.count("policy_regulatory_qa") == 30
    assert families.count("sara_entailment") == 20


def test_core_mixed_sources_frontload_all_families_for_head_sampling():
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "legal_lm/data/sources/core_mixed_sources.jsonl"

    first_twelve_rows = [
        json.loads(line) for line in source_path.read_text().splitlines()[:12] if line.strip()
    ]

    assert [row["task_family"] for row in first_twelve_rows] == [
        "rule_reasoning",
        "definition_classification",
        "policy_regulatory_qa",
        "sara_entailment",
        "rule_reasoning",
        "definition_classification",
        "policy_regulatory_qa",
        "sara_entailment",
        "rule_reasoning",
        "definition_classification",
        "policy_regulatory_qa",
        "sara_entailment",
    ]


def test_core_mixed_smoke_eval_covers_all_four_families_evenly():
    repo_root = Path(__file__).resolve().parents[2]
    eval_path = (
        repo_root
        / "legal_lm/results/teacher_runs/core_mixed_family4_sara_v1/core_mixed_smoke_eval.jsonl"
    )

    eval_rows = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]

    assert len(eval_rows) == 24
    families = [row["task_family"] for row in eval_rows]
    assert set(families) == {
        "rule_reasoning",
        "definition_classification",
        "policy_regulatory_qa",
        "sara_entailment",
    }
    assert families.count("rule_reasoning") == 6
    assert families.count("definition_classification") == 6
    assert families.count("policy_regulatory_qa") == 6
    assert families.count("sara_entailment") == 6


def test_core_mixed_family4_floor10_search_artifacts_enforce_exact_balancing():
    repo_root = Path(__file__).resolve().parents[2]
    run_dir = repo_root / "legal_lm/results/teacher_runs/core_mixed_family4_sara_floor10_v1"
    summary_path = run_dir / "family4_floor10_summary.json"
    results_path = run_dir / "family4_floor10_results.jsonl"

    summary = json.loads(summary_path.read_text())
    result_rows = [
        json.loads(line) for line in results_path.read_text().splitlines() if line.strip()
    ]

    assert summary["iterations_completed"] == 12000
    assert summary["best_overall"]["batch_size"] == 40
    assert summary["best_overall"]["family_balancing"] == "equal"
    assert summary["best_overall"]["family_counts"] == {
        "rule_reasoning": 10,
        "definition_classification": 10,
        "policy_regulatory_qa": 10,
        "sara_entailment": 10,
    }

    assert result_rows
    assert all(row["batch_size"] == 40 for row in result_rows)
    assert all(row["family_balancing"] == "equal" for row in result_rows)
    assert all(
        row["family_counts"]
        == {
            "rule_reasoning": 10,
            "definition_classification": 10,
            "policy_regulatory_qa": 10,
            "sara_entailment": 10,
        }
        for row in result_rows
    )
