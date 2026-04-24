from legal_lm.student.eval_student import (
    annotate_prediction_rows,
    build_rule_review_markdown,
    extract_answer_line,
    score_prediction_rows,
    score_rule_guardrails,
)


def make_prediction(
    example_id: str,
    *,
    task_family: str,
    reference_answer: str,
    generated_text: str,
):
    return {
        "id": example_id,
        "task_family": task_family,
        "doctrine": "Synthetic Doctrine",
        "user_prompt": f"Prompt for {example_id}?",
        "reference_answer": reference_answer,
        "reference_reasoning_short": f"Reasoning for {example_id}.",
        "reference_rubric_points": ["State the rule", "Reach the right conclusion"],
        "generated_text": generated_text,
    }


def test_extract_answer_line_finds_first_answer_line_and_strips_whitespace():
    generated = "Preamble\nAnswer:   Required   \nReasoning: The rule uses shall.\nAnswer: Wrong"

    assert extract_answer_line(generated) == "Required"


def test_score_prediction_rows_tracks_closed_label_accuracy_and_format_failures():
    prediction_rows = [
        make_prediction(
            "def-1",
            task_family="definition_classification",
            reference_answer="Yes",
            generated_text="Answer: Yes\nReasoning: It defines a legal term.",
        ),
        make_prediction(
            "policy-1",
            task_family="policy_regulatory_qa",
            reference_answer="Required",
            generated_text="Answer: Permitted\nReasoning: It uses may.",
        ),
        make_prediction(
            "sara-1",
            task_family="sara_entailment",
            reference_answer="Entailment",
            generated_text="Reasoning only with no answer prefix.",
        ),
        make_prediction(
            "def-2",
            task_family="definition_classification",
            reference_answer="No",
            generated_text="Answer: Maybe\nReasoning: Unsure.",
        ),
        make_prediction(
            "rule-1",
            task_family="rule_reasoning",
            reference_answer="A rule answer.",
            generated_text="Answer: A rule answer.\nReasoning: It names the rule.",
        ),
    ]

    annotated = annotate_prediction_rows(prediction_rows)
    summary = score_prediction_rows(prediction_rows)

    by_id = {row["id"]: row for row in annotated}
    assert by_id["def-1"]["parsed_answer"] == "Yes"
    assert by_id["policy-1"]["is_correct"] is False
    assert by_id["sara-1"]["missing_answer_line"] is True
    assert by_id["def-2"]["invalid_label"] is True
    assert by_id["rule-1"]["is_closed_label_family"] is False

    assert summary["closed_label_row_count"] == 4
    assert summary["closed_label_correct_count"] == 1
    assert summary["closed_label_accuracy"] == 0.25
    assert summary["output_hygiene"] == {
        "missing_answer_line_count": 1,
        "empty_answer_count": 0,
        "invalid_label_count": 1,
    }
    assert summary["per_family"]["definition_classification"] == {
        "total_rows": 2,
        "closed_label_rows": 2,
        "correct_count": 1,
        "accuracy": 0.5,
    }
    assert summary["per_family"]["rule_reasoning"] == {
        "total_rows": 1,
        "closed_label_rows": 0,
        "correct_count": 0,
        "accuracy": None,
    }


def test_score_rule_guardrails_flags_meta_reasoning_and_known_rule_gaps():
    prediction_rows = [
        make_prediction(
            "rule-eval-002",
            task_family="rule_reasoning",
            reference_answer=(
                "A plaintiff generally must show a likelihood of success on the merits, "
                "a likelihood of irreparable harm without preliminary relief, that the balance "
                "of equities favors relief, and that an injunction is in the public interest."
            ),
            generated_text=(
                "Answer: A preliminary injunction requires likelihood of success and "
                "irreparable harm.\n"
                "Reasoning: The answer should identify the usual preliminary-injunction "
                "factors."
            ),
        ),
        make_prediction(
            "rule-eval-004",
            task_family="rule_reasoning",
            reference_answer=(
                "For legislative rules, the APA generally requires notice of proposed "
                "rulemaking, an opportunity to comment, and a final rule with a concise "
                "general statement of basis and purpose."
            ),
            generated_text=(
                "Answer: The APA requires a notice of proposed rulemaking, comments, "
                "and a final rule.\n"
                "Reasoning: The agency must allow notice and comment before finalizing."
            ),
        ),
        make_prediction(
            "rule-eval-003",
            task_family="rule_reasoning",
            reference_answer="Compelling interest and narrow tailoring.",
            generated_text=(
                "Answer: Strict scrutiny requires a compelling governmental interest and "
                "narrow tailoring.\nReasoning: Strict scrutiny demands both elements."
            ),
        ),
    ]

    guardrails = score_rule_guardrails(prediction_rows)

    assert guardrails["passed"] is False
    assert guardrails["rule_reasoning_row_count"] == 3
    assert guardrails["meta_reasoning_count"] == 1
    assert guardrails["known_gap_count"] == 2
    issues_by_id = {
        row["id"]: {issue["key"] for issue in row["issues"]} for row in guardrails["row_issues"]
    }
    assert issues_by_id == {
        "rule-eval-002": {"meta_rubric_reasoning", "missing_public_interest"},
        "rule-eval-004": {"missing_basis_and_purpose"},
    }


def test_build_rule_review_markdown_compares_base_and_fine_tuned_outputs():
    base_rows = [
        make_prediction(
            "rule-1",
            task_family="rule_reasoning",
            reference_answer="Hearsay is an out-of-court statement offered for its truth.",
            generated_text=(
                "Answer: Hearsay is an out-of-court statement.\nReasoning: Partial answer."
            ),
        )
    ]
    fine_tuned_rows = [
        make_prediction(
            "rule-1",
            task_family="rule_reasoning",
            reference_answer="Hearsay is an out-of-court statement offered for its truth.",
            generated_text=(
                "Answer: Hearsay is an out-of-court statement offered to prove the truth "
                "of the matter asserted.\nReasoning: It includes both core elements."
            ),
        )
    ]

    markdown = build_rule_review_markdown(
        base_rows=base_rows,
        fine_tuned_rows=fine_tuned_rows,
    )

    assert "# Rule reasoning review" in markdown
    assert "## rule-1" in markdown
    assert "Synthetic Doctrine" in markdown
    assert "Base output" in markdown
    assert "Fine-tuned output" in markdown
    assert "State the rule" in markdown
    assert "Reach the right conclusion" in markdown
