import json
from pathlib import Path

from legal_lm.student.clean_reasoning_targets import (
    REASONING_OVERRIDES,
    build_cleaned_dataset,
    clean_teacher_reasoning_row,
)


def write_jsonl(path: Path, rows: list[dict]):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_clean_teacher_reasoning_row_replaces_known_meta_target():
    row = {
        "id": "rule-seed-021",
        "task_family": "rule_reasoning",
        "teacher_reasoning_short": (
            "A complete answer should identify the standard four preliminary-injunction factors."
        ),
    }

    cleaned = clean_teacher_reasoning_row(row)

    assert cleaned["teacher_reasoning_short"] == REASONING_OVERRIDES["rule-seed-021"]
    assert cleaned["teacher_reasoning_short"] != row["teacher_reasoning_short"]
    assert row["teacher_reasoning_short"].startswith("A complete answer should")


def test_build_cleaned_dataset_writes_non_destructive_student_artifacts(tmp_path: Path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    train_rows = [
        {
            "id": "rule-seed-021",
            "source": "curated_rule_seed_v2",
            "task_family": "rule_reasoning",
            "user_prompt": (
                "What four factors must a plaintiff ordinarily establish to win a "
                "preliminary injunction in federal court?"
            ),
            "teacher_answer": (
                "A plaintiff generally must show a likelihood of success, irreparable "
                "harm, equities, and public interest."
            ),
            "teacher_reasoning_short": (
                "A complete answer should identify the standard four "
                "preliminary-injunction factors."
            ),
            "teacher_rubric_points": ["Lists the core factors"],
            "teacher_confidence": "high",
            "split": "train",
            "doctrine": "Civil Procedure",
        }
    ]
    dev_rows = [
        {
            "id": "sara-src-003",
            "source": "curated_sara_entailment_seed_v1",
            "task_family": "sara_entailment",
            "user_prompt": (
                "Domestic-service wages stay excluded below the threshold. Avery paid "
                "Sam $600. The wages are excluded."
            ),
            "teacher_answer": "Entailment",
            "teacher_reasoning_short": (
                "The claim is entailment after applying Section 3306(c)(2) to the specific facts."
            ),
            "teacher_rubric_points": ["Apply the rule"],
            "teacher_confidence": "high",
            "split": "validation",
            "doctrine": "Household Employment Tax",
        }
    ]
    test_rows = [
        {
            "id": "rule-eval-002",
            "source": "rule_reasoning_smoke_eval_v1",
            "task_family": "rule_reasoning",
            "user_prompt": "What showing is needed for a preliminary injunction in federal court?",
            "reference_answer": (
                "Likelihood of success, irreparable harm, equities, and public interest."
            ),
            "reference_reasoning_short": "A complete answer should identify the four factors.",
            "reference_rubric_points": ["Lists factors"],
            "doctrine": "Civil Procedure",
        }
    ]
    write_jsonl(input_dir / "train.jsonl", train_rows)
    write_jsonl(input_dir / "dev.jsonl", dev_rows)
    write_jsonl(input_dir / "test.jsonl", test_rows)

    manifest = build_cleaned_dataset(input_dir=input_dir, output_dir=output_dir)

    assert manifest["changed_ids"] == ["rule-seed-021", "sara-src-003"]
    assert (output_dir / "train.jsonl").exists()
    assert (output_dir / "dev.jsonl").exists()
    assert (output_dir / "test_prompts.jsonl").exists()
    train_message = json.loads((output_dir / "train_messages.jsonl").read_text().splitlines()[0])
    assert train_message["messages"][-1]["content"].endswith(REASONING_OVERRIDES["rule-seed-021"])
    assert json.loads((input_dir / "train.jsonl").read_text())[
        "teacher_reasoning_short"
    ].startswith("A complete answer should")
