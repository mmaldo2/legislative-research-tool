"""Score real student-model predictions on the frozen LegalLM pilot eval artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from legal_lm.student.prepare_dataset import load_jsonl, write_jsonl
from legal_lm.student.prompting import CLOSED_LABELS_BY_FAMILY

ANSWER_LINE_RE = re.compile(r"^\s*answer\s*:\s*(.*)$", re.IGNORECASE)
REASONING_LINE_RE = re.compile(r"^\s*reasoning\s*:\s*(.*)$", re.IGNORECASE)
META_RUBRIC_REASONING_RE = re.compile(
    r"\b("
    r"(?:the|a|an)?\s*(?:correct|complete|good|legal)?\s*answer\s+should"
    r"|should\s+(?:identify|quote|mention|focus|state|include|track)"
    r")\b",
    re.IGNORECASE,
)


def extract_answer_line(generated_text: str) -> str | None:
    for line in generated_text.splitlines():
        match = ANSWER_LINE_RE.match(line)
        if match:
            return match.group(1).strip()
    return None


def extract_reasoning_line(generated_text: str) -> str | None:
    for line in generated_text.splitlines():
        match = REASONING_LINE_RE.match(line)
        if match:
            return match.group(1).strip()
    return None


def is_meta_rubric_reasoning(reasoning_text: str | None) -> bool:
    return bool(reasoning_text and META_RUBRIC_REASONING_RE.search(reasoning_text))


def _normalize_answer(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized.lower()


def _issue(key: str, message: str) -> dict[str, str]:
    return {"key": key, "message": message}


def _contains_any(value: str | None, needles: tuple[str, ...]) -> bool:
    normalized = _normalize_answer(value) or ""
    return any(needle in normalized for needle in needles)


def _has_apa_basis_and_purpose_signal(answer: str | None) -> bool:
    normalized = _normalize_answer(answer) or ""
    if _contains_any(
        normalized,
        (
            "basis and purpose",
            "basis-and-purpose",
            "statement of basis",
            "basis/purpose",
        ),
    ):
        return True
    return _contains_any(normalized, ("explanation", "explains", "explaining")) and _contains_any(
        normalized,
        ("agency", "decision", "rule"),
    )


def _rule_known_gap_issues(example_id: str, answer: str | None) -> list[dict[str, str]]:
    if example_id == "rule-eval-002" and not _contains_any(answer, ("public interest",)):
        return [
            _issue(
                "missing_public_interest",
                "Preliminary-injunction answer should include the public-interest factor.",
            )
        ]
    if example_id == "rule-eval-004" and not _has_apa_basis_and_purpose_signal(answer):
        return [
            _issue(
                "missing_basis_and_purpose",
                (
                    "APA notice-and-comment answer should include a final rule with a "
                    "basis-and-purpose statement or equivalent explanation."
                ),
            )
        ]
    return []


def score_rule_guardrails(prediction_rows: list[dict[str, Any]]) -> dict[str, Any]:
    row_issues: list[dict[str, Any]] = []
    rule_rows = [row for row in prediction_rows if str(row.get("task_family")) == "rule_reasoning"]
    for row in rule_rows:
        generated_text = str(row.get("generated_text", ""))
        answer = row.get("parsed_answer") or extract_answer_line(generated_text)
        reasoning = row.get("reasoning") or extract_reasoning_line(generated_text)
        issues: list[dict[str, str]] = []
        if is_meta_rubric_reasoning(reasoning):
            issues.append(
                _issue(
                    "meta_rubric_reasoning",
                    (
                        "Reasoning line is rubric/meta guidance rather than substantive "
                        "legal reasoning."
                    ),
                )
            )
        issues.extend(_rule_known_gap_issues(str(row.get("id")), answer))
        if issues:
            row_issues.append(
                {
                    "id": row.get("id"),
                    "doctrine": row.get("doctrine"),
                    "prompt": row.get("user_prompt"),
                    "parsed_answer": answer,
                    "reasoning": reasoning,
                    "issues": issues,
                }
            )

    meta_reasoning_count = sum(
        1
        for row in row_issues
        for issue in row["issues"]
        if issue["key"] == "meta_rubric_reasoning"
    )
    known_gap_count = sum(
        1
        for row in row_issues
        for issue in row["issues"]
        if issue["key"] != "meta_rubric_reasoning"
    )
    return {
        "passed": not row_issues,
        "rule_reasoning_row_count": len(rule_rows),
        "issue_count": meta_reasoning_count + known_gap_count,
        "meta_reasoning_count": meta_reasoning_count,
        "known_gap_count": known_gap_count,
        "row_issues": row_issues,
    }


def annotate_prediction_rows(prediction_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated_rows: list[dict[str, Any]] = []
    for row in prediction_rows:
        generated_text = str(row.get("generated_text", ""))
        parsed_answer = extract_answer_line(generated_text)
        normalized_reference = _normalize_answer(str(row.get("reference_answer", "")))
        normalized_parsed = _normalize_answer(parsed_answer)
        task_family = str(row.get("task_family"))
        allowed_labels = tuple(CLOSED_LABELS_BY_FAMILY.get(task_family, ()))
        normalized_allowed_labels = {_normalize_answer(label) for label in allowed_labels}

        missing_answer_line = parsed_answer is None
        empty_answer = parsed_answer is not None and normalized_parsed == ""
        is_closed_label_family = task_family in CLOSED_LABELS_BY_FAMILY
        invalid_label = (
            is_closed_label_family
            and not missing_answer_line
            and not empty_answer
            and normalized_parsed not in normalized_allowed_labels
        )
        is_correct = (
            is_closed_label_family
            and not missing_answer_line
            and not empty_answer
            and not invalid_label
            and normalized_parsed == normalized_reference
        )

        annotated_rows.append(
            {
                **row,
                "parsed_answer": parsed_answer,
                "normalized_reference_answer": normalized_reference,
                "normalized_parsed_answer": normalized_parsed,
                "is_closed_label_family": is_closed_label_family,
                "missing_answer_line": missing_answer_line,
                "empty_answer": empty_answer,
                "invalid_label": invalid_label,
                "is_correct": is_correct,
            }
        )
    return annotated_rows


def score_prediction_rows(prediction_rows: list[dict[str, Any]]) -> dict[str, Any]:
    annotated_rows = annotate_prediction_rows(prediction_rows)
    closed_label_rows = [row for row in annotated_rows if row["is_closed_label_family"]]
    closed_label_correct = [row for row in closed_label_rows if row["is_correct"]]

    per_family: dict[str, dict[str, Any]] = {}
    for family in sorted({str(row.get("task_family")) for row in annotated_rows}):
        family_rows = [row for row in annotated_rows if row["task_family"] == family]
        family_closed_label_rows = [row for row in family_rows if row["is_closed_label_family"]]
        family_correct_rows = [row for row in family_closed_label_rows if row["is_correct"]]
        accuracy = None
        if family_closed_label_rows:
            accuracy = round(len(family_correct_rows) / len(family_closed_label_rows), 6)
        per_family[family] = {
            "total_rows": len(family_rows),
            "closed_label_rows": len(family_closed_label_rows),
            "correct_count": len(family_correct_rows),
            "accuracy": accuracy,
        }

    overall_accuracy = None
    if closed_label_rows:
        overall_accuracy = round(len(closed_label_correct) / len(closed_label_rows), 6)

    return {
        "total_rows": len(annotated_rows),
        "closed_label_row_count": len(closed_label_rows),
        "closed_label_correct_count": len(closed_label_correct),
        "closed_label_accuracy": overall_accuracy,
        "rule_reasoning_row_count": sum(
            1 for row in annotated_rows if row["task_family"] == "rule_reasoning"
        ),
        "output_hygiene": {
            "missing_answer_line_count": sum(
                1 for row in annotated_rows if row["missing_answer_line"]
            ),
            "empty_answer_count": sum(1 for row in annotated_rows if row["empty_answer"]),
            "invalid_label_count": sum(1 for row in annotated_rows if row["invalid_label"]),
        },
        "rule_guardrails": score_rule_guardrails(annotated_rows),
        "per_family": per_family,
    }


def build_rule_review_markdown(
    *,
    base_rows: list[dict[str, Any]] | None = None,
    fine_tuned_rows: list[dict[str, Any]] | None = None,
) -> str:
    if base_rows is None and fine_tuned_rows is None:
        raise ValueError("At least one prediction set is required for rule review")

    def _rule_index(rows: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
        if rows is None:
            return {}
        return {row["id"]: row for row in rows if str(row.get("task_family")) == "rule_reasoning"}

    base_index = _rule_index(base_rows)
    fine_tuned_index = _rule_index(fine_tuned_rows)
    all_ids = sorted(set(base_index) | set(fine_tuned_index))

    lines = ["# Rule reasoning review", ""]
    if not all_ids:
        lines.append("No rule_reasoning rows were provided.")
        return "\n".join(lines) + "\n"

    for example_id in all_ids:
        row = fine_tuned_index.get(example_id) or base_index[example_id]
        lines.extend(
            [
                f"## {example_id}",
                f"- Doctrine: {row.get('doctrine', '')}",
                f"- Prompt: {row.get('user_prompt', '')}",
                f"- Reference answer: {row.get('reference_answer', '')}",
                f"- Reference reasoning: {row.get('reference_reasoning_short', '')}",
                "- Rubric points:",
            ]
        )
        for point in row.get("reference_rubric_points", []):
            lines.append(f"  - {point}")

        if example_id in base_index:
            base_row = base_index[example_id]
            base_parsed_answer = extract_answer_line(str(base_row.get("generated_text", "")))
            lines.extend(
                [
                    "- Base output:",
                    f"```text\n{base_row.get('generated_text', '')}\n```",
                    f"- Base parsed answer: {base_parsed_answer}",
                ]
            )
        if example_id in fine_tuned_index:
            fine_tuned_row = fine_tuned_index[example_id]
            fine_tuned_parsed_answer = extract_answer_line(
                str(fine_tuned_row.get("generated_text", ""))
            )
            lines.extend(
                [
                    "- Fine-tuned output:",
                    f"```text\n{fine_tuned_row.get('generated_text', '')}\n```",
                    f"- Fine-tuned parsed answer: {fine_tuned_parsed_answer}",
                ]
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_parser = subparsers.add_parser("score-predictions")
    score_parser.add_argument("predictions_path", type=Path)
    score_parser.add_argument("summary_output_path", type=Path)
    score_parser.add_argument("--annotated-output-path", type=Path, default=None)

    review_parser = subparsers.add_parser("write-rule-review")
    review_parser.add_argument("output_path", type=Path)
    review_parser.add_argument("--base-predictions-path", type=Path, default=None)
    review_parser.add_argument("--fine-tuned-predictions-path", type=Path, default=None)

    guardrail_parser = subparsers.add_parser("check-rule-guardrails")
    guardrail_parser.add_argument("predictions_path", type=Path)
    guardrail_parser.add_argument("output_path", type=Path)

    return parser


def main() -> int:
    args = _build_parser().parse_args()

    if args.command == "score-predictions":
        prediction_rows = load_jsonl(args.predictions_path)
        summary = score_prediction_rows(prediction_rows)
        args.summary_output_path.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        if args.annotated_output_path is not None:
            write_jsonl(args.annotated_output_path, annotate_prediction_rows(prediction_rows))
        print(
            json.dumps(
                {
                    "status": "scored",
                    "summary_output_path": str(args.summary_output_path),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "check-rule-guardrails":
        prediction_rows = load_jsonl(args.predictions_path)
        guardrails = score_rule_guardrails(annotate_prediction_rows(prediction_rows))
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(json.dumps(guardrails, indent=2, sort_keys=True) + "\n")
        print(
            json.dumps(
                {
                    "status": "checked_rule_guardrails",
                    "passed": guardrails["passed"],
                    "output_path": str(args.output_path),
                },
                indent=2,
            )
        )
        return 0

    if args.base_predictions_path is None and args.fine_tuned_predictions_path is None:
        raise ValueError("At least one predictions path is required for rule review")

    base_rows = load_jsonl(args.base_predictions_path) if args.base_predictions_path else None
    fine_tuned_rows = (
        load_jsonl(args.fine_tuned_predictions_path) if args.fine_tuned_predictions_path else None
    )
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        build_rule_review_markdown(base_rows=base_rows, fine_tuned_rows=fine_tuned_rows)
    )
    print(
        json.dumps(
            {
                "status": "wrote_rule_review",
                "output_path": str(args.output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
