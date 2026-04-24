"""Build non-destructive cleaned-reasoning student-pilot artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from legal_lm.student.prepare_dataset import (
    eval_row_to_prompt_record,
    load_jsonl,
    teacher_row_to_message_record,
    write_jsonl,
)

DEFAULT_INPUT_DIR = Path("legal_lm/data/student_pilot/family4_floor10_v1")
DEFAULT_OUTPUT_DIR = Path("legal_lm/data/student_pilot/family4_floor10_v1_reasoning_clean_v2")

REASONING_OVERRIDES = {
    "rule-seed-001": (
        "The rule turns on both where the statement was made and the purpose for which"
        "it is offered."
    ),
    "rule-seed-002": (
        "Rule 401 is a low threshold that asks whether the evidence affects the"
        "probability of a consequential fact."
    ),
    "rule-seed-003": (
        "Rule 403 uses a balancing standard: probative value must be substantially"
        "outweighed by specified risks such as unfair prejudice, confusion, delay, or"
        "cumulative proof."
    ),
    "rule-seed-004": (
        "The constitutional concern is admitting testimonial statements without live"
        "testimony unless unavailability and prior cross-examination protect"
        "confrontation."
    ),
    "rule-seed-007": (
        "At the pleading stage, well-pleaded facts are accepted as true, but legal"
        "conclusions must still support a plausible claim."
    ),
    "rule-seed-013": (
        "The doctrine protects state sovereign autonomy by preventing Congress from"
        "conscripting state governments into carrying out federal regulation."
    ),
    "rule-seed-018": (
        "The clause targets retroactive criminal legislation that worsens the legal"
        "consequences of conduct after the fact."
    ),
    "rule-seed-021": (
        "Preliminary relief depends on merits likelihood, irreparable harm, the balance"
        "of equities, and the public interest."
    ),
    "rule-seed-025": (
        "Strict scrutiny is satisfied only when the government interest is compelling"
        "and the means fit that interest very closely."
    ),
    "rule-seed-026": (
        "Rule 403 requires more than ordinary prejudice; exclusion depends on probative"
        "value being substantially outweighed by the listed trial-management dangers."
    ),
    "rule-seed-028": (
        "The rule protects the final integrated writing from contradiction or variation"
        "by prior or contemporaneous extrinsic terms."
    ),
    "rule-seed-030": (
        "Section 553 procedure moves from public notice to comments and culminates in a"
        "final rule explaining the agency basis and purpose."
    ),
    "sara-src-001": (
        "A court entered a separate-maintenance decree, so Section 7703(a)(2) treats"
        "Morgan as unmarried for the tax year."
    ),
    "sara-src-002": (
        "Morgan never obtained a legal-separation or separate-maintenance decree, so"
        "the rule does not treat Morgan as unmarried."
    ),
    "sara-src-003": (
        "Avery stayed below the domestic-service remuneration threshold, so the wages"
        "remain excluded under Section 3306(c)(2)."
    ),
    "sara-src-004": (
        "Avery paid more than the remuneration threshold, so the domestic-service"
        "exclusion does not apply."
    ),
    "sara-src-006": (
        "Lee missed the 60-day redeposit deadline, so the claimed rollover treatment"
        "contradicts Section 408(d)(3)."
    ),
    "sara-src-008": (
        "Riley lacked adequate records for time, place, amount, and business purpose,"
        "so the substantiation rule is not satisfied."
    ),
    "sara-src-011": (
        "Dana was insolvent by more than the canceled debt amount, so Section"
        "108(a)(1)(B) can exclude the canceled debt."
    ),
    "sara-src-014": (
        "Casey received a retirement distribution before age 59 and one-half and no"
        "exception is stated, so the additional tax applies."
    ),
    "sara-src-015": (
        "Jordan redeposited the distribution into an eligible retirement plan within 60"
        "days, so the rollover exclusion condition is satisfied."
    ),
    "sara-src-016": (
        "Jordan redeposited after the 60-day window expired, so the transfer is not a"
        "timely rollover."
    ),
    "sara-src-019": (
        "Harper already used the credit in four prior taxable years, so the fifth-year"
        "claim contradicts Section 25A(b)(2)(A)."
    ),
    "sara-src-020": (
        "Robin received damages for a broken leg, a personal physical injury, so"
        "Section 104(a)(2) excludes the settlement damages."
    ),
}


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _family_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    families = sorted({str(row.get("task_family")) for row in rows})
    return {
        family: sum(1 for row in rows if str(row.get("task_family")) == family)
        for family in families
    }


def clean_teacher_reasoning_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(row)
    override = REASONING_OVERRIDES.get(str(row.get("id")))
    if override is not None and "teacher_reasoning_short" in cleaned:
        cleaned["teacher_reasoning_short"] = override
    return cleaned


def build_cleaned_dataset(*, input_dir: Path, output_dir: Path) -> dict[str, Any]:
    train_rows = [clean_teacher_reasoning_row(row) for row in load_jsonl(input_dir / "train.jsonl")]
    dev_rows = [clean_teacher_reasoning_row(row) for row in load_jsonl(input_dir / "dev.jsonl")]
    test_rows = load_jsonl(input_dir / "test.jsonl")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_paths = {
        "train": write_jsonl(output_dir / "train.jsonl", train_rows),
        "dev": write_jsonl(output_dir / "dev.jsonl", dev_rows),
        "test": write_jsonl(output_dir / "test.jsonl", test_rows),
    }
    message_paths = {
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
    overrides_path = output_dir / "reasoning_overrides.json"
    overrides_path.write_text(json.dumps(REASONING_OVERRIDES, indent=2, sort_keys=True) + "\n")

    original_by_id = {
        str(row["id"]): row
        for row in [*load_jsonl(input_dir / "train.jsonl"), *load_jsonl(input_dir / "dev.jsonl")]
    }
    cleaned_by_id = {str(row["id"]): row for row in [*train_rows, *dev_rows]}
    changed_ids = sorted(
        example_id
        for example_id, original_row in original_by_id.items()
        if cleaned_by_id[example_id].get("teacher_reasoning_short")
        != original_row.get("teacher_reasoning_short")
    )
    manifest = {
        "base_dataset": str(input_dir),
        "purpose": (
            "Non-destructive cleaned teacher-reasoning target dataset: replaces "
            "rubric/meta or generic teacher_reasoning_short rows while preserving prompts, "
            "answers, labels, and held-out test prompts."
        ),
        "changed_ids": changed_ids,
        "split_counts": {"train": len(train_rows), "dev": len(dev_rows), "test": len(test_rows)},
        "family_counts": {
            "train": _family_counts(train_rows),
            "dev": _family_counts(dev_rows),
            "test": _family_counts(test_rows),
        },
        "artifact_hashes": {
            **{name: _sha256_path(path) for name, path in raw_paths.items()},
            **{name: _sha256_path(path) for name, path in message_paths.items()},
            "reasoning_overrides": _sha256_path(overrides_path),
        },
        "source_artifact_hashes": {
            name: _sha256_path(input_dir / f"{name}.jsonl") for name in ("train", "dev", "test")
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    manifest = build_cleaned_dataset(input_dir=args.input_dir, output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "status": "built",
                "output_dir": str(args.output_dir),
                "changed_count": len(manifest["changed_ids"]),
                "split_counts": manifest["split_counts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
