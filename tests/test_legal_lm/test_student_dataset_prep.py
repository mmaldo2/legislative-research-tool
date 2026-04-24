import json
from collections import Counter
from pathlib import Path

from legal_lm.student.prepare_dataset import (
    build_pilot_artifacts,
    load_jsonl,
    select_balanced_dev_source_rows,
)
from legal_lm.student.prompting import DEFAULT_SYSTEM_PROMPT, format_assistant_response

FAMILY_ANSWERS = {
    "rule_reasoning": "A correct rule answer.",
    "definition_classification": "Yes",
    "policy_regulatory_qa": "Required",
    "sara_entailment": "Entailment",
}


def make_source_row(
    example_id: str,
    *,
    task_family: str,
    doctrine: str,
    reference_answer: str | None = None,
):
    return {
        "id": example_id,
        "source": "synthetic_source",
        "task_family": task_family,
        "user_prompt": f"Prompt for {example_id}?",
        "reference_answer": reference_answer or FAMILY_ANSWERS[task_family],
        "reference_reasoning_short": f"Reasoning for {example_id}.",
        "reference_rubric_points": ["State the right answer", "Keep it concise"],
        "doctrine": doctrine,
    }


def make_teacher_row(
    example_id: str,
    *,
    task_family: str,
    doctrine: str,
    teacher_answer: str | None = None,
):
    return {
        "id": example_id,
        "source": "synthetic_teacher_batch",
        "task_family": task_family,
        "user_prompt": f"Prompt for {example_id}?",
        "teacher_answer": teacher_answer or FAMILY_ANSWERS[task_family],
        "teacher_reasoning_short": f"Reasoning for {example_id}.",
        "teacher_rubric_points": ["State the right answer", "Keep it concise"],
        "teacher_confidence": "high",
        "split": "train",
        "doctrine": doctrine,
    }


def test_format_assistant_response_uses_exact_two_line_schema():
    rendered = format_assistant_response("Yes", "The sentence defines a legal term.")

    assert rendered == "Answer: Yes\nReasoning: The sentence defines a legal term."


def test_select_balanced_dev_source_rows_prefers_distinct_closed_labels_when_available():
    source_rows = [
        make_source_row(
            "def-yes-1",
            task_family="definition_classification",
            doctrine="Privacy",
            reference_answer="Yes",
        ),
        make_source_row(
            "def-yes-2",
            task_family="definition_classification",
            doctrine="Employment",
            reference_answer="Yes",
        ),
        make_source_row(
            "def-no-1",
            task_family="definition_classification",
            doctrine="Contracts",
            reference_answer="No",
        ),
        make_source_row(
            "policy-required-1",
            task_family="policy_regulatory_qa",
            doctrine="Telecom",
            reference_answer="Required",
        ),
        make_source_row(
            "policy-prohibited-1",
            task_family="policy_regulatory_qa",
            doctrine="Privacy",
            reference_answer="Prohibited",
        ),
        make_source_row(
            "rule-1",
            task_family="rule_reasoning",
            doctrine="Evidence",
        ),
        make_source_row(
            "rule-2",
            task_family="rule_reasoning",
            doctrine="Civil Procedure",
        ),
        make_source_row(
            "sara-entailment-1",
            task_family="sara_entailment",
            doctrine="Filing Status",
            reference_answer="Entailment",
        ),
        make_source_row(
            "sara-contradiction-1",
            task_family="sara_entailment",
            doctrine="Child Tax Credit",
            reference_answer="Contradiction",
        ),
    ]

    selected = select_balanced_dev_source_rows(
        source_rows,
        excluded_ids=set(),
        per_family=2,
    )

    selected_by_family = {}
    for row in selected:
        selected_by_family.setdefault(row["task_family"], []).append(row)

    assert {row["reference_answer"] for row in selected_by_family["definition_classification"]} == {
        "Yes",
        "No",
    }
    assert {row["reference_answer"] for row in selected_by_family["policy_regulatory_qa"]} == {
        "Required",
        "Prohibited",
    }
    assert {row["reference_answer"] for row in selected_by_family["sara_entailment"]} == {
        "Entailment",
        "Contradiction",
    }


def test_build_pilot_artifacts_creates_balanced_dev_and_message_files(tmp_path: Path):
    train_rows = [
        make_teacher_row(
            "rule-train-1",
            task_family="rule_reasoning",
            doctrine="Evidence",
        ),
        make_teacher_row(
            "def-train-1",
            task_family="definition_classification",
            doctrine="Privacy",
            teacher_answer="Yes",
        ),
        make_teacher_row(
            "policy-train-1",
            task_family="policy_regulatory_qa",
            doctrine="Telecom",
            teacher_answer="Required",
        ),
        make_teacher_row(
            "sara-train-1",
            task_family="sara_entailment",
            doctrine="Filing Status",
            teacher_answer="Entailment",
        ),
    ]
    source_rows = [
        make_source_row(
            "rule-train-1",
            task_family="rule_reasoning",
            doctrine="Evidence",
        ),
        make_source_row(
            "def-train-1",
            task_family="definition_classification",
            doctrine="Privacy",
            reference_answer="Yes",
        ),
        make_source_row(
            "policy-train-1",
            task_family="policy_regulatory_qa",
            doctrine="Telecom",
            reference_answer="Required",
        ),
        make_source_row(
            "sara-train-1",
            task_family="sara_entailment",
            doctrine="Filing Status",
            reference_answer="Entailment",
        ),
        make_source_row(
            "rule-dev-1",
            task_family="rule_reasoning",
            doctrine="Civil Procedure",
        ),
        make_source_row(
            "rule-dev-2",
            task_family="rule_reasoning",
            doctrine="Contracts",
        ),
        make_source_row(
            "def-dev-1",
            task_family="definition_classification",
            doctrine="Bankruptcy",
            reference_answer="No",
        ),
        make_source_row(
            "def-dev-2",
            task_family="definition_classification",
            doctrine="Employment",
            reference_answer="Yes",
        ),
        make_source_row(
            "policy-dev-1",
            task_family="policy_regulatory_qa",
            doctrine="Utilities",
            reference_answer="Conditional",
        ),
        make_source_row(
            "policy-dev-2",
            task_family="policy_regulatory_qa",
            doctrine="Transportation",
            reference_answer="Permitted",
        ),
        make_source_row(
            "sara-dev-1",
            task_family="sara_entailment",
            doctrine="Retirement Rollovers",
            reference_answer="Contradiction",
        ),
        make_source_row(
            "sara-dev-2",
            task_family="sara_entailment",
            doctrine="Child Tax Credit",
            reference_answer="Entailment",
        ),
    ]
    test_rows = [
        make_source_row(
            "rule-test-1",
            task_family="rule_reasoning",
            doctrine="Evidence",
        ),
        make_source_row(
            "def-test-1",
            task_family="definition_classification",
            doctrine="Privacy",
            reference_answer="Yes",
        ),
        make_source_row(
            "policy-test-1",
            task_family="policy_regulatory_qa",
            doctrine="Telecom",
            reference_answer="Required",
        ),
        make_source_row(
            "sara-test-1",
            task_family="sara_entailment",
            doctrine="Filing Status",
            reference_answer="Entailment",
        ),
    ]

    manifest = build_pilot_artifacts(
        train_rows=train_rows,
        source_rows=source_rows,
        test_rows=test_rows,
        output_dir=tmp_path,
        dev_per_family=1,
    )

    train_written = load_jsonl(tmp_path / "train.jsonl")
    dev_written = load_jsonl(tmp_path / "dev.jsonl")
    test_written = load_jsonl(tmp_path / "test.jsonl")
    train_messages = load_jsonl(tmp_path / "train_messages.jsonl")
    dev_messages = load_jsonl(tmp_path / "dev_messages.jsonl")
    test_prompts = load_jsonl(tmp_path / "test_prompts.jsonl")

    assert len(train_written) == 4
    assert len(dev_written) == 4
    assert all(row["split"] == "validation" for row in dev_written)
    assert len(test_written) == 4
    assert Counter(row["task_family"] for row in dev_written) == {
        "rule_reasoning": 1,
        "definition_classification": 1,
        "policy_regulatory_qa": 1,
        "sara_entailment": 1,
    }

    split_ids = [
        {row["id"] for row in train_written},
        {row["id"] for row in dev_written},
        {row["id"] for row in test_written},
    ]
    assert split_ids[0].isdisjoint(split_ids[1])
    assert split_ids[0].isdisjoint(split_ids[2])
    assert split_ids[1].isdisjoint(split_ids[2])

    assert len(train_messages) == 4
    assert train_messages[0]["messages"][0]["content"] == DEFAULT_SYSTEM_PROMPT
    assert train_messages[0]["messages"][2]["content"] == format_assistant_response(
        train_written[0]["teacher_answer"],
        train_written[0]["teacher_reasoning_short"],
    )

    assert len(dev_messages) == 4
    assert all(len(row["messages"]) == 3 for row in dev_messages)

    assert len(test_prompts) == 4
    assert all(len(row["messages"]) == 2 for row in test_prompts)
    assert test_prompts[0]["messages"][0]["content"] == DEFAULT_SYSTEM_PROMPT
    assert test_prompts[0]["reference_answer"] == test_written[0]["reference_answer"]

    assert manifest["split_counts"] == {"train": 4, "dev": 4, "test": 4}
    assert manifest["family_counts"]["dev"] == {
        "rule_reasoning": 1,
        "definition_classification": 1,
        "policy_regulatory_qa": 1,
        "sara_entailment": 1,
    }


def test_checked_in_family4_floor10_student_pilot_artifacts_are_balanced_and_disjoint():
    repo_root = Path(__file__).resolve().parents[2]
    artifact_dir = repo_root / "legal_lm/data/student_pilot/family4_floor10_v1"

    train_rows = load_jsonl(artifact_dir / "train.jsonl")
    dev_rows = load_jsonl(artifact_dir / "dev.jsonl")
    test_rows = load_jsonl(artifact_dir / "test.jsonl")
    train_messages = load_jsonl(artifact_dir / "train_messages.jsonl")
    dev_messages = load_jsonl(artifact_dir / "dev_messages.jsonl")
    test_prompts = load_jsonl(artifact_dir / "test_prompts.jsonl")
    manifest = json.loads((artifact_dir / "manifest.json").read_text())

    assert len(train_rows) == 40
    assert len(dev_rows) == 8
    assert all(row["split"] == "validation" for row in dev_rows)
    assert len(test_rows) == 24
    assert len(train_messages) == 40
    assert len(dev_messages) == 8
    assert len(test_prompts) == 24

    assert Counter(row["task_family"] for row in train_rows) == {
        "rule_reasoning": 10,
        "definition_classification": 10,
        "policy_regulatory_qa": 10,
        "sara_entailment": 10,
    }
    assert Counter(row["task_family"] for row in dev_rows) == {
        "rule_reasoning": 2,
        "definition_classification": 2,
        "policy_regulatory_qa": 2,
        "sara_entailment": 2,
    }
    assert Counter(row["task_family"] for row in test_rows) == {
        "rule_reasoning": 6,
        "definition_classification": 6,
        "policy_regulatory_qa": 6,
        "sara_entailment": 6,
    }
    assert {
        row["teacher_answer"]
        for row in dev_rows
        if row["task_family"] == "definition_classification"
    } == {"Yes", "No"}
    assert {
        row["teacher_answer"] for row in dev_rows if row["task_family"] == "sara_entailment"
    } == {"Entailment", "Contradiction"}
    assert (
        len(
            {
                row["teacher_answer"]
                for row in dev_rows
                if row["task_family"] == "policy_regulatory_qa"
            }
        )
        == 2
    )

    split_ids = [
        {row["id"] for row in train_rows},
        {row["id"] for row in dev_rows},
        {row["id"] for row in test_rows},
    ]
    assert split_ids[0].isdisjoint(split_ids[1])
    assert split_ids[0].isdisjoint(split_ids[2])
    assert split_ids[1].isdisjoint(split_ids[2])

    assert manifest["split_counts"] == {"train": 40, "dev": 8, "test": 24}
    assert manifest["dev_selection_policy"]["selection"] == (
        "prefer distinct closed-label answers when available; otherwise source-order head"
    )
    assert manifest["family_counts"]["dev"] == {
        "rule_reasoning": 2,
        "definition_classification": 2,
        "policy_regulatory_qa": 2,
        "sara_entailment": 2,
    }
