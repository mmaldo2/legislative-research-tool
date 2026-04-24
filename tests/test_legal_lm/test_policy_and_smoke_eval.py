from legal_lm.teacher_loop import generate_batch_from_sources, run_student_smoke_eval

DEFINITION_YES_PROMPT = (
    "Clause: 'Personal data means information linked to an individual.' Is this a definition?"
)
DEFINITION_NO_PROMPT = (
    "Clause: 'The agency may issue penalties after notice.' Is this a definition?"
)


def make_source_row(example_id: str, **overrides):
    row = {
        "id": example_id,
        "source": "curated_mixed_seed",
        "task_family": "rule_reasoning",
        "user_prompt": f"Question for {example_id}?",
        "reference_answer": f"Answer for {example_id}",
        "reference_reasoning_short": f"Reasoning for {example_id}",
        "reference_rubric_points": ["Name the rule", "State the conclusion"],
        "doctrine": "Evidence",
    }
    row.update(overrides)
    return row


def test_generate_batch_from_sources_supports_doctrine_weighting_and_family_balancing():
    source_rows = [
        make_source_row("rule-evidence-1", task_family="rule_reasoning", doctrine="Evidence"),
        make_source_row("rule-evidence-2", task_family="rule_reasoning", doctrine="Evidence"),
        make_source_row("rule-contracts-1", task_family="rule_reasoning", doctrine="Contracts"),
        make_source_row(
            "def-privacy-1",
            task_family="definition_classification",
            doctrine="Privacy",
            reference_answer="Yes",
        ),
        make_source_row(
            "def-privacy-2",
            task_family="definition_classification",
            doctrine="Privacy",
            reference_answer="No",
        ),
        make_source_row(
            "def-securities-1",
            task_family="definition_classification",
            doctrine="Securities",
            reference_answer="No",
        ),
    ]

    batch = generate_batch_from_sources(
        source_rows,
        batch_size=4,
        seed=3,
        doctrine_weights={"Evidence": 50.0, "Contracts": 0.0, "Privacy": 20.0, "Securities": 0.0},
        family_balancing="equal",
    )

    families = [row["task_family"] for row in batch]
    doctrines = [row["doctrine"] for row in batch]
    assert families.count("rule_reasoning") == 2
    assert families.count("definition_classification") == 2
    assert "Contracts" not in doctrines
    assert "Securities" not in doctrines


def test_generate_batch_from_sources_supports_confidence_defaults_and_rubric_variants():
    source_rows = [
        make_source_row(
            "row-1",
            task_family="rule_reasoning",
            reference_rubric_points=["First point.", "Second point."],
        ),
        make_source_row(
            "row-2",
            task_family="definition_classification",
            reference_answer="Yes",
            reference_rubric_points=["Definition present.", "Label correctly."],
        ),
        make_source_row("row-3", task_family="rule_reasoning"),
        make_source_row("row-4", task_family="definition_classification", reference_answer="No"),
    ]

    batch = generate_batch_from_sources(
        source_rows,
        batch_size=2,
        seed=9,
        sampling_strategy="head",
        subsample_ratio=0.5,
        confidence_by_family={"definition_classification": "medium"},
        rubric_variant="checklist",
    )

    assert [row["id"] for row in batch] == ["row-1", "row-2"]
    assert batch[0]["teacher_confidence"] == "high"
    assert batch[1]["teacher_confidence"] == "medium"
    assert batch[0]["teacher_rubric_points"] == ["Check: First point.", "Check: Second point."]


def test_run_student_smoke_eval_returns_accuracy_for_definition_classification():
    teacher_batch = generate_batch_from_sources(
        [
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
        ],
        batch_size=2,
        seed=2,
    )

    eval_rows = [
        {
            "id": "def-eval-1",
            "source": "definition_eval",
            "task_family": "definition_classification",
            "user_prompt": DEFINITION_YES_PROMPT,
            "reference_answer": "Yes",
            "reference_reasoning_short": "Contains a direct definitional formula.",
            "reference_rubric_points": ["Classify the sentence correctly"],
            "doctrine": "Privacy",
        },
        {
            "id": "def-eval-2",
            "source": "definition_eval",
            "task_family": "definition_classification",
            "user_prompt": DEFINITION_NO_PROMPT,
            "reference_answer": "No",
            "reference_reasoning_short": "Describes authority, not a definition.",
            "reference_rubric_points": ["Classify the sentence correctly"],
            "doctrine": "Administrative Law",
        },
    ]

    report = run_student_smoke_eval(teacher_batch, eval_rows)

    assert report["metric_name"] == "accuracy"
    assert report["metric_value"] == 1.0
    assert report["n_eval_examples"] == 2
