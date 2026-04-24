"""Autoresearch-style keep/discard loop utilities for legal teacher batches."""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from legal_lm.eval.teacher_batch_audit import audit_examples

RESULTS_HEADER = "run_id\tbatch_id\tteacher_batch_score\tstudent_metric\tstatus\tdescription\n"


class JSONLParseError(ValueError):
    """Raised when a JSONL batch contains syntactically invalid JSON."""

    def __init__(self, line_number: int, message: str):
        super().__init__(message)
        self.line_number = line_number


_SOURCE_REQUIRED_STRING_FIELDS = (
    "id",
    "source",
    "task_family",
    "user_prompt",
    "reference_answer",
    "reference_reasoning_short",
    "doctrine",
)
_ALLOWED_BATCH_CONFIDENCE = ("low", "medium", "high")
_ALLOWED_OUTPUT_SPLITS = ("train", "validation")
_ALLOWED_SAMPLING_STRATEGIES = ("random", "head")
_ALLOWED_FAMILY_BALANCING = ("none", "equal")
_ALLOWED_RUBRIC_VARIANTS = ("verbatim", "checklist", "concise")


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_source_row(source_row: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for field in _SOURCE_REQUIRED_STRING_FIELDS:
        if field not in source_row or not _is_non_empty_string(source_row.get(field)):
            errors.append(f"{field} must be a non-empty string")

    rubric_points = source_row.get("reference_rubric_points")
    if not isinstance(rubric_points, list) or not rubric_points:
        errors.append("reference_rubric_points must be a non-empty list")
    elif any(not _is_non_empty_string(point) for point in rubric_points):
        errors.append("reference_rubric_points must contain only non-empty strings")

    return errors


def build_teacher_example_from_source(
    source_row: dict[str, Any], *, split: str = "train", confidence: str = "high"
) -> dict[str, Any]:
    """Map a curated source row into the teacher-example schema."""

    errors = _validate_source_row(source_row)
    if errors:
        raise ValueError("; ".join(errors))

    return {
        "id": source_row["id"],
        "source": source_row["source"],
        "task_family": source_row["task_family"],
        "user_prompt": source_row["user_prompt"],
        "teacher_answer": source_row["reference_answer"],
        "teacher_reasoning_short": source_row["reference_reasoning_short"],
        "teacher_rubric_points": list(source_row["reference_rubric_points"]),
        "teacher_confidence": confidence,
        "split": split,
        "doctrine": source_row["doctrine"],
    }


def _apply_rubric_variant(rubric_points: list[str], variant: str) -> list[str]:
    if variant == "verbatim":
        return list(rubric_points)
    if variant == "checklist":
        return [f"Check: {point}" for point in rubric_points]
    if variant == "concise":
        concise_points: list[str] = []
        for point in rubric_points:
            trimmed = point.split(",", 1)[0].strip()
            concise_points.append(trimmed or point)
        return concise_points
    raise ValueError(f"rubric_variant must be one of: {', '.join(_ALLOWED_RUBRIC_VARIANTS)}")


def _weighted_sample_without_replacement(
    rows: list[dict[str, Any]],
    *,
    sample_size: int,
    generator: random.Random,
    doctrine_weights: dict[str, float] | None,
    sampling_strategy: str,
) -> list[dict[str, Any]]:
    if sampling_strategy == "head":
        return rows[:sample_size]

    pool = list(rows)
    selected: list[dict[str, Any]] = []
    while pool and len(selected) < sample_size:
        weights = [
            max(float((doctrine_weights or {}).get(str(row.get("doctrine")), 1.0)), 0.0)
            for row in pool
        ]
        if sum(weights) <= 0:
            weights = [1.0] * len(pool)
        chosen_index = generator.choices(range(len(pool)), weights=weights, k=1)[0]
        selected.append(pool.pop(chosen_index))
    return selected


def _subsample_rows(
    rows: list[dict[str, Any]],
    *,
    subsample_ratio: float,
    sampling_strategy: str,
    doctrine_weights: dict[str, float] | None,
    generator: random.Random,
) -> list[dict[str, Any]]:
    if subsample_ratio <= 0 or subsample_ratio > 1:
        raise ValueError("subsample_ratio must be greater than 0 and at most 1")
    if subsample_ratio == 1.0 or len(rows) <= 1:
        return list(rows)

    sample_size = max(1, math.floor(len(rows) * subsample_ratio))
    return _weighted_sample_without_replacement(
        list(rows),
        sample_size=sample_size,
        generator=generator,
        doctrine_weights=doctrine_weights,
        sampling_strategy=sampling_strategy,
    )


def _balanced_family_sample(
    rows: list[dict[str, Any]],
    *,
    batch_size: int,
    generator: random.Random,
    doctrine_weights: dict[str, float] | None,
    sampling_strategy: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("task_family")), []).append(row)

    families = sorted(grouped)
    allocations = {family: 0 for family in families}
    while sum(allocations.values()) < min(batch_size, len(rows)):
        progressed = False
        for family in families:
            if allocations[family] < len(grouped[family]):
                allocations[family] += 1
                progressed = True
                if sum(allocations.values()) >= min(batch_size, len(rows)):
                    break
        if not progressed:
            break

    selected: list[dict[str, Any]] = []
    for family in families:
        selected.extend(
            _weighted_sample_without_replacement(
                grouped[family],
                sample_size=allocations[family],
                generator=generator,
                doctrine_weights=doctrine_weights,
                sampling_strategy=sampling_strategy,
            )
        )
    return selected


def _normalize_answer_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _tokenize_prompt(prompt: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", prompt.lower()))


def run_student_smoke_eval(
    teacher_batch: list[dict[str, Any]], eval_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    if not eval_rows:
        raise ValueError("eval_rows must contain at least one example")

    comparisons = []
    for eval_row in eval_rows:
        errors = _validate_source_row(eval_row)
        if errors:
            raise ValueError("; ".join(errors))
        prompt_tokens = _tokenize_prompt(eval_row["user_prompt"])
        best_example = max(
            teacher_batch,
            key=lambda row: len(prompt_tokens & _tokenize_prompt(row["user_prompt"])),
        )
        predicted = _normalize_answer_label(best_example["teacher_answer"])
        expected = _normalize_answer_label(eval_row["reference_answer"])
        comparisons.append(predicted == expected)

    accuracy = sum(comparisons) / len(comparisons)
    task_families = sorted({str(row.get("task_family")) for row in eval_rows})
    return {
        "metric_name": "accuracy",
        "metric_value": round(accuracy, 6),
        "n_eval_examples": len(eval_rows),
        "task_families": task_families,
    }


def generate_batch_from_sources(
    source_rows: list[dict[str, Any]],
    *,
    batch_size: int,
    seed: int,
    task_family: str | None = None,
    split: str = "train",
    confidence: str = "high",
    doctrine_weights: dict[str, float] | None = None,
    family_balancing: str = "none",
    confidence_by_family: dict[str, str] | None = None,
    rubric_variant: str = "verbatim",
    sampling_strategy: str = "random",
    subsample_ratio: float = 1.0,
) -> list[dict[str, Any]]:
    """Sample curated source rows into teacher examples using batch-policy knobs."""

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if confidence not in _ALLOWED_BATCH_CONFIDENCE:
        raise ValueError(
            f"confidence must be one of: {', '.join(_ALLOWED_BATCH_CONFIDENCE)}"
        )
    if split not in _ALLOWED_OUTPUT_SPLITS:
        raise ValueError(f"split must be one of: {', '.join(_ALLOWED_OUTPUT_SPLITS)}")
    if family_balancing not in _ALLOWED_FAMILY_BALANCING:
        raise ValueError(
            f"family_balancing must be one of: {', '.join(_ALLOWED_FAMILY_BALANCING)}"
        )
    if sampling_strategy not in _ALLOWED_SAMPLING_STRATEGIES:
        raise ValueError(
            f"sampling_strategy must be one of: {', '.join(_ALLOWED_SAMPLING_STRATEGIES)}"
        )
    if rubric_variant not in _ALLOWED_RUBRIC_VARIANTS:
        raise ValueError(
            f"rubric_variant must be one of: {', '.join(_ALLOWED_RUBRIC_VARIANTS)}"
        )
    for family, configured_confidence in (confidence_by_family or {}).items():
        if configured_confidence not in _ALLOWED_BATCH_CONFIDENCE:
            raise ValueError(
                f"confidence override for {family} must be one of: "
                f"{', '.join(_ALLOWED_BATCH_CONFIDENCE)}"
            )

    filtered_rows = [
        row for row in source_rows if task_family is None or row.get("task_family") == task_family
    ]
    if not filtered_rows:
        raise ValueError("No eligible source rows matched the requested selection")

    validation_errors = [
        (str(row.get("id") or "<missing-id>"), _validate_source_row(row))
        for row in filtered_rows
    ]
    invalid_rows = [(row_id, errors) for row_id, errors in validation_errors if errors]
    if invalid_rows:
        row_id, errors = invalid_rows[0]
        raise ValueError(f"invalid source row {row_id}: {'; '.join(errors)}")

    generator = random.Random(seed)
    candidate_rows = _subsample_rows(
        filtered_rows,
        subsample_ratio=subsample_ratio,
        sampling_strategy=sampling_strategy,
        doctrine_weights=doctrine_weights,
        generator=generator,
    )
    sample_size = min(batch_size, len(candidate_rows))

    if family_balancing == "equal":
        sampled_rows = _balanced_family_sample(
            candidate_rows,
            batch_size=sample_size,
            generator=generator,
            doctrine_weights=doctrine_weights,
            sampling_strategy=sampling_strategy,
        )
    else:
        sampled_rows = _weighted_sample_without_replacement(
            candidate_rows,
            sample_size=sample_size,
            generator=generator,
            doctrine_weights=doctrine_weights,
            sampling_strategy=sampling_strategy,
        )

    teacher_examples: list[dict[str, Any]] = []
    for row in sampled_rows:
        row_confidence = (confidence_by_family or {}).get(str(row.get("task_family")), confidence)
        teacher_example = build_teacher_example_from_source(
            row,
            split=split,
            confidence=row_confidence,
        )
        teacher_example["teacher_rubric_points"] = _apply_rubric_variant(
            teacher_example["teacher_rubric_points"],
            rubric_variant,
        )
        teacher_examples.append(teacher_example)
    return teacher_examples


def init_results_tsv(results_path: Path) -> Path:
    """Create the results TSV with the expected header if it does not already exist."""

    results_path.parent.mkdir(parents=True, exist_ok=True)
    if not results_path.exists() or not results_path.read_text().strip():
        results_path.write_text(RESULTS_HEADER)
    return results_path


def load_best_score(results_path: Path) -> float | None:
    """Return the best kept teacher-batch score from the results TSV."""

    if not results_path.exists():
        return None

    best_score: float | None = None
    rows = results_path.read_text().splitlines()
    if rows and rows[0] == RESULTS_HEADER.strip():
        rows = rows[1:]
    for row in rows:
        if not row.strip():
            continue

        parts = row.split("\t", 5)
        if len(parts) != 6:
            continue

        _, _, score_text, _, status, _ = parts
        if status != "keep":
            continue

        try:
            score = float(score_text)
        except ValueError:
            continue

        if not math.isfinite(score):
            continue

        if best_score is None or score > best_score:
            best_score = score
    return best_score


def load_best_student_metric(results_path: Path) -> float | None:
    """Return the best finite kept student metric from the results TSV."""

    best_metric, _ = load_best_student_metric_record(results_path)
    return best_metric


def load_best_student_metric_record(results_path: Path) -> tuple[float | None, float | None]:
    """Return the best kept student metric and its paired batch score."""

    if not results_path.exists():
        return None, None

    best_metric: float | None = None
    best_score: float | None = None
    rows = results_path.read_text().splitlines()
    if rows and rows[0] == RESULTS_HEADER.strip():
        rows = rows[1:]
    for row in rows:
        if not row.strip():
            continue

        parts = row.split("\t", 5)
        if len(parts) != 6:
            continue

        _, _, score_text, metric_text, status, _ = parts
        if status != "keep" or not metric_text:
            continue

        try:
            metric = float(metric_text)
            score = float(score_text)
        except ValueError:
            continue

        if not math.isfinite(metric) or not math.isfinite(score):
            continue

        if best_metric is None or metric > best_metric:
            best_metric = metric
            best_score = score
            continue
        if math.isclose(metric, best_metric) and (best_score is None or score > best_score):
            best_score = score
    return best_metric, best_score


def _format_student_metric(student_metric: float | None) -> str:
    return "" if student_metric is None else f"{student_metric:.6f}"


def _sanitize_field(value: str) -> str:
    normalized_chars: list[str] = []
    for character in str(value):
        if character in {"\t", "\n", "\r"}:
            normalized_chars.append(" ")
        elif character.isprintable():
            normalized_chars.append(character)
        else:
            normalized_chars.append(" ")
    return " ".join("".join(normalized_chars).split())


def decide_status(
    audit_report: dict[str, Any],
    best_score: float | None,
    *,
    student_metric: float | None = None,
    best_student_metric: float | None = None,
) -> str:
    """Keep valid batches that improve the tracked objective."""

    if not audit_report["valid"]:
        return "discard"
    if student_metric is not None:
        if best_student_metric is None:
            return "keep"
        if student_metric > best_student_metric:
            return "keep"
        if (
            math.isclose(student_metric, best_student_metric)
            and best_score is not None
            and audit_report["score"] > best_score
        ):
            return "keep"
        return "discard"
    if best_score is None:
        return "keep"
    if audit_report["score"] > best_score:
        return "keep"
    return "discard"


def evaluate_and_log_batch(
    *,
    results_path: Path,
    run_id: str,
    batch_id: str,
    description: str,
    audit_report: dict[str, Any],
    student_metric: float | None = None,
) -> dict[str, Any]:
    """Evaluate a batch against the current best score and append a log row."""

    init_results_tsv(results_path)
    best_score = load_best_score(results_path)
    best_student_metric, best_student_score = load_best_student_metric_record(results_path)
    status = decide_status(
        audit_report,
        best_student_score if student_metric is not None else best_score,
        student_metric=student_metric,
        best_student_metric=best_student_metric,
    )

    sanitized_fields = [
        _sanitize_field(run_id),
        _sanitize_field(batch_id),
        f"{audit_report['score']:.1f}",
        _format_student_metric(student_metric),
        status,
        _sanitize_field(description),
    ]

    with results_path.open("a") as handle:
        existing_text = results_path.read_text()
        if existing_text and not existing_text.endswith("\n"):
            handle.write("\n")
        handle.write("\t".join(sanitized_fields))
        handle.write("\n")

    return {
        "run_id": run_id,
        "batch_id": batch_id,
        "teacher_batch_score": audit_report["score"],
        "student_metric": student_metric,
        "status": status,
        "description": description,
        "batch_errors": audit_report["batch_errors"],
        "example_errors": audit_report["example_errors"],
        "summary": audit_report["summary"],
    }


def _load_jsonl(batch_path: Path) -> list[Any]:
    examples: list[Any] = []
    with batch_path.open() as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                examples.append(json.loads(line))
            except JSONDecodeError as exc:
                message = f"Invalid JSON on line {line_number}: {exc.msg}"
                raise JSONLParseError(line_number, message) from exc
    return examples


def _write_jsonl(output_path: Path, rows: list[dict[str, Any]]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            handle.write("\n")
    return output_path


def _parse_json_object_arg(raw_value: str | None, *, field_name: str) -> dict[str, Any] | None:
    if raw_value in (None, ""):
        return None
    try:
        parsed = json.loads(raw_value)
    except JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must decode to a JSON object")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-results", help="Create the results TSV header")
    init_parser.add_argument("results_path", type=Path)

    audit_parser = subparsers.add_parser(
        "audit-batch", help="Audit a JSONL batch and append a keep/discard result"
    )
    audit_parser.add_argument("batch_path", type=Path)
    audit_parser.add_argument("results_path", type=Path)
    audit_parser.add_argument("run_id")
    audit_parser.add_argument("batch_id")
    audit_parser.add_argument("description")
    audit_parser.add_argument("--student-metric", type=float, default=None)
    audit_parser.add_argument("--smoke-eval-path", type=Path, default=None)

    generate_parser = subparsers.add_parser(
        "generate-batch", help="Generate a teacher batch from curated source rows"
    )
    generate_parser.add_argument("source_path", type=Path)
    generate_parser.add_argument("output_path", type=Path)
    generate_parser.add_argument("--batch-size", type=int, default=20)
    generate_parser.add_argument("--seed", type=int, default=0)
    generate_parser.add_argument("--task-family", default=None)
    generate_parser.add_argument("--output-split", choices=_ALLOWED_OUTPUT_SPLITS, default="train")
    generate_parser.add_argument("--confidence", choices=_ALLOWED_BATCH_CONFIDENCE, default="high")
    generate_parser.add_argument(
        "--family-balancing",
        choices=_ALLOWED_FAMILY_BALANCING,
        default="none",
    )
    generate_parser.add_argument(
        "--rubric-variant",
        choices=_ALLOWED_RUBRIC_VARIANTS,
        default="verbatim",
    )
    generate_parser.add_argument(
        "--sampling-strategy",
        choices=_ALLOWED_SAMPLING_STRATEGIES,
        default="random",
    )
    generate_parser.add_argument("--subsample-ratio", type=float, default=1.0)
    generate_parser.add_argument("--doctrine-weights-json", default=None)
    generate_parser.add_argument("--confidence-by-family-json", default=None)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "init-results":
        try:
            init_results_tsv(args.results_path)
        except OSError as exc:
            print(json.dumps({"status": "crash", "error": str(exc)}))
            return 1
        print(json.dumps({"results_path": str(args.results_path), "status": "initialized"}))
        return 0

    try:
        if args.command == "generate-batch":
            if args.source_path.resolve() == args.output_path.resolve():
                print(
                    json.dumps(
                        {
                            "status": "crash",
                            "error": "source_path and output_path must differ",
                        }
                    )
                )
                return 1

            source_rows = _load_jsonl(args.source_path)
            non_object_rows = [
                index
                for index, row in enumerate(source_rows, start=1)
                if not isinstance(row, dict)
            ]
            if non_object_rows:
                print(
                    json.dumps(
                        {
                            "status": "crash",
                            "error": "Source rows must all be JSON objects",
                            "row_numbers": non_object_rows,
                        }
                    )
                )
                return 1

            try:
                doctrine_weights = _parse_json_object_arg(
                    args.doctrine_weights_json,
                    field_name="doctrine_weights_json",
                )
                confidence_by_family = _parse_json_object_arg(
                    args.confidence_by_family_json,
                    field_name="confidence_by_family_json",
                )
                batch_rows = generate_batch_from_sources(
                    source_rows,
                    batch_size=args.batch_size,
                    seed=args.seed,
                    task_family=args.task_family,
                    split=args.output_split,
                    confidence=args.confidence,
                    doctrine_weights=doctrine_weights,
                    family_balancing=args.family_balancing,
                    confidence_by_family=confidence_by_family,
                    rubric_variant=args.rubric_variant,
                    sampling_strategy=args.sampling_strategy,
                    subsample_ratio=args.subsample_ratio,
                )
            except ValueError as exc:
                print(json.dumps({"status": "crash", "error": str(exc)}))
                return 1
            _write_jsonl(args.output_path, batch_rows)
            print(
                json.dumps(
                    {
                        "status": "generated",
                        "source_path": str(args.source_path),
                        "output_path": str(args.output_path),
                        "num_examples": len(batch_rows),
                        "task_family": args.task_family,
                        "seed": args.seed,
                    }
                )
            )
            return 0

        examples = _load_jsonl(args.batch_path)
    except JSONLParseError as exc:
        print(
            json.dumps(
                {
                    "status": "crash",
                    "error": str(exc),
                    "line_number": exc.line_number,
                }
            )
        )
        return 1
    except OSError as exc:
        print(json.dumps({"status": "crash", "error": str(exc)}))
        return 1

    student_metric = args.student_metric
    try:
        audit_report = audit_examples(examples)
        if args.smoke_eval_path is not None and audit_report["valid"]:
            eval_rows = _load_jsonl(args.smoke_eval_path)
            non_object_rows = [
                index for index, row in enumerate(eval_rows, start=1) if not isinstance(row, dict)
            ]
            if non_object_rows:
                print(
                    json.dumps(
                        {
                            "status": "crash",
                            "error": "Smoke-eval rows must all be JSON objects",
                            "row_numbers": non_object_rows,
                        }
                    )
                )
                return 1
            smoke_eval_report = run_student_smoke_eval(examples, eval_rows)  # type: ignore[arg-type]
            student_metric = smoke_eval_report["metric_value"]
        result = evaluate_and_log_batch(
            results_path=args.results_path,
            run_id=args.run_id,
            batch_id=args.batch_id,
            description=args.description,
            audit_report=audit_report,
            student_metric=student_metric,
        )
    except OSError as exc:
        print(json.dumps({"status": "crash", "error": str(exc)}))
        return 1
    except ValueError as exc:
        print(json.dumps({"status": "crash", "error": str(exc)}))
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
