import importlib.util
import json
from pathlib import Path

from legal_lm.student.train_sft import (
    build_peft_config_kwargs,
    build_sft_config_kwargs,
    load_message_rows,
    probe_training_stack,
    train_sft,
)


def make_message_row(example_id: str):
    return {
        "id": example_id,
        "task_family": "definition_classification",
        "messages": [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": f"Prompt for {example_id}?"},
            {
                "role": "assistant",
                "content": "Answer: Yes\nReasoning: It defines a legal term.",
            },
        ],
    }


def test_load_message_rows_rejects_rows_without_final_assistant_turn(tmp_path: Path):
    path = tmp_path / "messages.jsonl"
    rows = [
        make_message_row("good-1"),
        {
            "id": "bad-1",
            "task_family": "definition_classification",
            "messages": [
                {"role": "system", "content": "System prompt."},
                {"role": "user", "content": "Prompt?"},
            ],
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    try:
        load_message_rows(path)
    except ValueError as exc:
        assert "final assistant turn" in str(exc)
        assert "bad-1" in str(exc)
    else:
        raise AssertionError(
            "Expected load_message_rows to reject rows without a final assistant turn"
        )


def test_build_sft_config_uses_pilot_defaults(tmp_path: Path):
    config_kwargs = build_sft_config_kwargs(output_dir=str(tmp_path / "out"))

    assert config_kwargs["per_device_train_batch_size"] == 4
    assert config_kwargs["per_device_eval_batch_size"] == 4
    assert config_kwargs["gradient_accumulation_steps"] == 1
    assert config_kwargs["learning_rate"] == 2e-4
    assert config_kwargs["num_train_epochs"] == 3.0
    assert config_kwargs["max_length"] == 512
    assert config_kwargs["warmup_ratio"] == 0.1
    assert config_kwargs["eval_strategy"] == "epoch"
    assert config_kwargs["save_strategy"] == "epoch"
    assert config_kwargs["seed"] == 17


def test_build_peft_config_uses_expected_lora_parameters():
    config_kwargs = build_peft_config_kwargs()

    assert config_kwargs["task_type"] == "CAUSAL_LM"
    assert config_kwargs["r"] == 16
    assert config_kwargs["lora_alpha"] == 32
    assert config_kwargs["lora_dropout"] == 0.05
    assert config_kwargs["bias"] == "none"


def test_train_sft_dry_run_uses_requested_seed(tmp_path: Path, monkeypatch):
    train_path = tmp_path / "train_messages.jsonl"
    eval_path = tmp_path / "dev_messages.jsonl"
    train_path.write_text(json.dumps(make_message_row("train-1")) + "\n")
    eval_path.write_text(json.dumps(make_message_row("dev-1")) + "\n")
    monkeypatch.setattr(
        "legal_lm.student.train_sft.probe_training_stack",
        lambda module_names=None: {
            "ready": True,
            "available_modules": [
                "torch",
                "transformers",
                "datasets",
                "peft",
                "trl",
                "bitsandbytes",
            ],
            "missing_modules": [],
        },
    )

    summary = train_sft(
        train_messages_path=train_path,
        eval_messages_path=eval_path,
        output_dir=tmp_path / "out",
        model_name_or_path="test-model",
        seed=23,
        dry_run=True,
    )

    assert summary["sft_config"]["seed"] == 23


def test_probe_training_stack_reports_missing_core_packages(monkeypatch):
    original_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str):
        if name == "peft":
            return None
        return original_find_spec(name)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    readiness = probe_training_stack(["json", "pathlib", "peft"])

    assert readiness["ready"] is False
    assert readiness["available_modules"] == ["json", "pathlib"]
    assert readiness["missing_modules"] == ["peft"]
