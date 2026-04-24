"""Batch validation and scoring for teacher-generated distillation data."""

from __future__ import annotations

from collections import Counter
from typing import Any

_ALLOWED_CONFIDENCE = {"low", "medium", "high"}
_ALLOWED_SPLITS = {"train", "validation", "test"}
_REQUIRED_STRING_FIELDS = (
    "id",
    "source",
    "task_family",
    "user_prompt",
    "teacher_answer",
    "teacher_reasoning_short",
    "teacher_confidence",
    "split",
)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_example_fields(example: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for field in _REQUIRED_STRING_FIELDS:
        if field not in example:
            errors.append(f"missing required field: {field}")
            continue
        if not _is_non_empty_string(example[field]):
            errors.append(f"{field} must be a non-empty string")

    rubric_points = example.get("teacher_rubric_points")
    if not isinstance(rubric_points, list) or not rubric_points:
        errors.append("teacher_rubric_points must be a non-empty list")
    elif any(not _is_non_empty_string(point) for point in rubric_points):
        errors.append("teacher_rubric_points must contain only non-empty strings")

    confidence = example.get("teacher_confidence")
    if _is_non_empty_string(confidence) and confidence not in _ALLOWED_CONFIDENCE:
        errors.append(
            f"teacher_confidence must be one of: {', '.join(sorted(_ALLOWED_CONFIDENCE))}"
        )

    split = example.get("split")
    if _is_non_empty_string(split) and split not in _ALLOWED_SPLITS:
        errors.append(f"split must be one of: {', '.join(sorted(_ALLOWED_SPLITS))}")

    if split == "test":
        errors.append("test split examples are eval-only and may not enter teacher batches")

    return errors


def compute_batch_score(
    *,
    invalid_example_count: int,
    duplicate_prompt_count: int,
    duplicate_id_count: int,
    test_split_count: int,
) -> float:
    """Return a simple 0-100 batch quality score."""

    score = 100.0
    score -= invalid_example_count * 25.0
    score -= duplicate_prompt_count * 10.0
    score -= duplicate_id_count * 10.0
    score -= test_split_count * 20.0
    return max(0.0, round(score, 1))


def audit_examples(examples: list[Any]) -> dict[str, Any]:
    """Validate a batch of teacher examples and return a deterministic report."""

    dict_examples = [example for example in examples if isinstance(example, dict)]

    prompt_counter = Counter(
        example["user_prompt"].strip()
        for example in dict_examples
        if _is_non_empty_string(example.get("user_prompt"))
    )
    duplicate_prompts = sorted(prompt for prompt, count in prompt_counter.items() if count > 1)

    id_counter = Counter(
        str(example["id"]).strip()
        for example in dict_examples
        if _is_non_empty_string(example.get("id"))
    )
    duplicate_ids = sorted(example_id for example_id, count in id_counter.items() if count > 1)

    batch_errors: list[str] = []
    if duplicate_prompts:
        batch_errors.extend(
            f"duplicate user_prompt detected: {prompt}" for prompt in duplicate_prompts
        )
    if duplicate_ids:
        batch_errors.extend(f"duplicate id detected: {example_id}" for example_id in duplicate_ids)

    if not examples:
        batch_errors.append("batch must contain at least one example")

    example_errors: dict[str, list[str]] = {}
    test_split_count = 0
    valid_example_count = 0
    invalid_example_count = 0

    for index, example in enumerate(examples, start=1):
        if not isinstance(example, dict):
            invalid_example_count += 1
            example_errors[f"row-{index}:non-object"] = ["example must be a JSON object"]
            continue

        base_id = str(example.get("id") or f"example-{index}")
        example_key = f"row-{index}:{base_id}"

        errors = _validate_example_fields(example)
        if errors:
            invalid_example_count += 1
            example_errors[example_key] = errors
            if example.get("split") == "test":
                test_split_count += 1
        else:
            valid_example_count += 1

    if test_split_count:
        batch_errors.append(
            f"test split leakage detected: {test_split_count} example(s) marked as test split"
        )

    score = compute_batch_score(
        invalid_example_count=invalid_example_count,
        duplicate_prompt_count=len(duplicate_prompts),
        duplicate_id_count=len(duplicate_ids),
        test_split_count=test_split_count,
    )
    if not examples:
        score = 0.0

    return {
        "valid": invalid_example_count == 0 and not batch_errors,
        "score": score,
        "batch_errors": batch_errors,
        "example_errors": example_errors,
        "summary": {
            "total_examples": len(examples),
            "valid_example_count": valid_example_count,
            "invalid_example_count": invalid_example_count,
            "duplicate_prompt_count": len(duplicate_prompts),
            "duplicate_id_count": len(duplicate_ids),
            "test_split_count": test_split_count,
        },
    }
