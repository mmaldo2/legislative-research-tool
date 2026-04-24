"""Prepare frozen student-pilot artifacts from the chosen LegalLM family-4 batch."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from legal_lm.student.prompting import (
    CLOSED_LABELS_BY_FAMILY,
    build_inference_messages,
    build_training_messages,
)
from legal_lm.teacher_loop import build_teacher_example_from_source

DEFAULT_TRAIN_BATCH_PATH = Path(
    "legal_lm/results/teacher_runs/core_mixed_family4_sara_floor10_v1/best_floor10_batch.jsonl"
)
DEFAULT_SOURCE_POOL_PATH = Path("legal_lm/data/sources/core_mixed_sources.jsonl")
DEFAULT_TEST_EVAL_PATH = Path(
    "legal_lm/results/teacher_runs/core_mixed_family4_sara_floor10_v1/core_mixed_smoke_eval.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("legal_lm/data/student_pilot/family4_floor10_v1")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path} line {line_number} must contain a JSON object")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            handle.write("\n")
    return path


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _family_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("task_family")) for row in rows))


def _ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["id"]) for row in rows]


def _ensure_disjoint_splits(splits: dict[str, list[dict[str, Any]]]) -> None:
    seen: dict[str, str] = {}
    for split_name, rows in splits.items():
        for row in rows:
            example_id = str(row["id"])
            prior_split = seen.get(example_id)
            if prior_split is not None:
                raise ValueError(
                    f"Split overlap detected for id {example_id}: {prior_split} and {split_name}"
                )
            seen[example_id] = split_name


def select_balanced_dev_source_rows(
    source_rows: list[dict[str, Any]],
    *,
    excluded_ids: set[str],
    per_family: int,
) -> list[dict[str, Any]]:
    if per_family <= 0:
        raise ValueError("per_family must be positive")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        example_id = str(row["id"])
        if example_id in excluded_ids:
            continue
        grouped[str(row["task_family"])].append(row)

    if not grouped:
        raise ValueError("No leftover source rows available for dev split selection")

    selected: list[dict[str, Any]] = []
    for family in sorted(grouped):
        family_rows = grouped[family]
        if len(family_rows) < per_family:
            raise ValueError(
                "Not enough leftover rows for family "
                f"{family}: need {per_family}, found {len(family_rows)}"
            )

        if family not in CLOSED_LABELS_BY_FAMILY:
            selected.extend(family_rows[:per_family])
            continue

        selected_for_family: list[dict[str, Any]] = []
        seen_labels: set[str] = set()
        fallback_rows: list[dict[str, Any]] = []
        for row in family_rows:
            label = str(row.get("reference_answer"))
            if label not in seen_labels and len(selected_for_family) < per_family:
                selected_for_family.append(row)
                seen_labels.add(label)
            else:
                fallback_rows.append(row)

        while len(selected_for_family) < per_family:
            if not fallback_rows:
                break
            selected_for_family.append(fallback_rows.pop(0))

        selected.extend(selected_for_family)
    return selected


def teacher_row_to_message_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_family": row["task_family"],
        "doctrine": row.get("doctrine"),
        "source": row.get("source"),
        "messages": build_training_messages(
            row["user_prompt"],
            row["teacher_answer"],
            row["teacher_reasoning_short"],
        ),
    }


def eval_row_to_prompt_record(row: dict[str, Any]) -> dict[str, Any]:
    prompt_record = dict(row)
    prompt_record["messages"] = build_inference_messages(row["user_prompt"])
    return prompt_record


def build_pilot_artifacts(
    *,
    train_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    output_dir: Path,
    dev_per_family: int = 2,
    train_source_path: Path | None = None,
    source_pool_path: Path | None = None,
    test_source_path: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    train_ids = set(_ids(train_rows))
    dev_source_rows = select_balanced_dev_source_rows(
        source_rows,
        excluded_ids=train_ids,
        per_family=dev_per_family,
    )
    dev_rows = [
        build_teacher_example_from_source(row, split="validation") for row in dev_source_rows
    ]

    splits = {"train": train_rows, "dev": dev_rows, "test": test_rows}
    _ensure_disjoint_splits(splits)

    raw_artifact_paths = {
        "train": write_jsonl(output_dir / "train.jsonl", train_rows),
        "dev": write_jsonl(output_dir / "dev.jsonl", dev_rows),
        "test": write_jsonl(output_dir / "test.jsonl", test_rows),
    }
    message_artifact_paths = {
        "train_messages": write_jsonl(
            output_dir / "train_messages.jsonl",
            [teacher_row_to_message_record(row) for row in train_rows],
        ),
        "dev_messages": write_jsonl(
            output_dir / "dev_messages.jsonl",
            [teacher_row_to_message_record(row) for row in dev_rows],
        ),
        "test_prompts": write_jsonl(
            output_dir / "test_prompts.jsonl",
            [eval_row_to_prompt_record(row) for row in test_rows],
        ),
    }

    manifest = {
        "dev_selection_policy": {
            "source": "leftover curated source rows not present in the blessed train batch",
            "per_family": dev_per_family,
            "selection": (
                "prefer distinct closed-label answers when available; otherwise source-order head"
            ),
        },
        "input_paths": {
            "train_batch": str(train_source_path) if train_source_path else None,
            "source_pool": str(source_pool_path) if source_pool_path else None,
            "test_eval": str(test_source_path) if test_source_path else None,
        },
        "input_hashes": {
            key: _sha256_path(path)
            for key, path in {
                "train_batch": train_source_path,
                "source_pool": source_pool_path,
                "test_eval": test_source_path,
            }.items()
            if path is not None
        },
        "split_counts": {split_name: len(rows) for split_name, rows in splits.items()},
        "family_counts": {split_name: _family_counts(rows) for split_name, rows in splits.items()},
        "split_ids": {split_name: _ids(rows) for split_name, rows in splits.items()},
        "artifact_hashes": {
            **{name: _sha256_path(path) for name, path in raw_artifact_paths.items()},
            **{name: _sha256_path(path) for name, path in message_artifact_paths.items()},
        },
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-batch-path", type=Path, default=DEFAULT_TRAIN_BATCH_PATH)
    parser.add_argument("--source-pool-path", type=Path, default=DEFAULT_SOURCE_POOL_PATH)
    parser.add_argument("--test-eval-path", type=Path, default=DEFAULT_TEST_EVAL_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dev-per-family", type=int, default=2)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    train_rows = load_jsonl(args.train_batch_path)
    source_rows = load_jsonl(args.source_pool_path)
    test_rows = load_jsonl(args.test_eval_path)
    manifest = build_pilot_artifacts(
        train_rows=train_rows,
        source_rows=source_rows,
        test_rows=test_rows,
        output_dir=args.output_dir,
        dev_per_family=args.dev_per_family,
        train_source_path=args.train_batch_path,
        source_pool_path=args.source_pool_path,
        test_source_path=args.test_eval_path,
    )
    print(
        json.dumps(
            {
                "status": "built",
                "output_dir": str(args.output_dir),
                "split_counts": manifest["split_counts"],
                "family_counts": manifest["family_counts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
