"""Minimal SFT entrypoint for the frozen LegalLM family-4 student pilot."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from legal_lm.student.prepare_dataset import load_jsonl

DEFAULT_MODEL_NAME = "Qwen/Qwen3-4B-Instruct-2507"
DEFAULT_TRAINING_STACK_MODULES = (
    "torch",
    "transformers",
    "datasets",
    "peft",
    "trl",
    "bitsandbytes",
)


def probe_training_stack(module_names: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    modules_to_check = module_names or DEFAULT_TRAINING_STACK_MODULES
    available_modules: list[str] = []
    missing_modules: list[str] = []
    for module_name in modules_to_check:
        if importlib.util.find_spec(module_name) is None:
            missing_modules.append(module_name)
        else:
            available_modules.append(module_name)
    return {
        "ready": not missing_modules,
        "available_modules": available_modules,
        "missing_modules": missing_modules,
    }


def load_message_rows(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    for row in rows:
        example_id = str(row.get("id", "<missing-id>"))
        messages = row.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError(f"{example_id} must contain a non-empty messages list")
        final_message = messages[-1]
        if not isinstance(final_message, dict) or final_message.get("role") != "assistant":
            raise ValueError(f"{example_id} must end with a final assistant turn")
        for index, message in enumerate(messages, start=1):
            if not isinstance(message, dict):
                raise ValueError(f"{example_id} message {index} must be a JSON object")
            if not isinstance(message.get("role"), str) or not message["role"].strip():
                raise ValueError(f"{example_id} message {index} must have a non-empty role")
            if not isinstance(message.get("content"), str) or not message["content"].strip():
                raise ValueError(f"{example_id} message {index} must have non-empty content")
    return rows


def build_peft_config_kwargs(
    *,
    r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    bias: str = "none",
    target_modules: str = "all-linear",
) -> dict[str, Any]:
    return {
        "task_type": "CAUSAL_LM",
        "r": r,
        "lora_alpha": lora_alpha,
        "lora_dropout": lora_dropout,
        "bias": bias,
        "target_modules": target_modules,
    }


def build_sft_config_kwargs(
    *,
    output_dir: str,
    per_device_train_batch_size: int = 4,
    per_device_eval_batch_size: int = 4,
    gradient_accumulation_steps: int = 1,
    learning_rate: float = 2e-4,
    num_train_epochs: float = 3.0,
    max_length: int = 512,
    warmup_ratio: float = 0.1,
    seed: int = 17,
) -> dict[str, Any]:
    return {
        "output_dir": output_dir,
        "per_device_train_batch_size": per_device_train_batch_size,
        "per_device_eval_batch_size": per_device_eval_batch_size,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "learning_rate": learning_rate,
        "num_train_epochs": num_train_epochs,
        "max_length": max_length,
        "warmup_ratio": warmup_ratio,
        "weight_decay": 0.0,
        "eval_strategy": "epoch",
        "save_strategy": "epoch",
        "save_total_limit": 1,
        "load_best_model_at_end": True,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
        "logging_steps": 1,
        "report_to": "none",
        "seed": seed,
        "dataset_text_field": "text",
        "packing": False,
        "gradient_checkpointing": True,
        "remove_unused_columns": False,
    }


def _fallback_render_messages(messages: list[dict[str, str]]) -> str:
    rendered_parts = []
    for message in messages:
        role = message["role"].strip().capitalize()
        content = message["content"].strip()
        rendered_parts.append(f"{role}: {content}")
    return "\n\n".join(rendered_parts)


def render_messages_as_text(messages: list[dict[str, str]], tokenizer: Any) -> str:
    apply_chat_template = getattr(tokenizer, "apply_chat_template", None)
    if callable(apply_chat_template):
        try:
            rendered = apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            if isinstance(rendered, str) and rendered.strip():
                return rendered
        except Exception:
            pass
    return _fallback_render_messages(messages)


def message_rows_to_text_records(
    message_rows: list[dict[str, Any]], tokenizer: Any
) -> list[dict[str, Any]]:
    return [
        {
            "id": row["id"],
            "task_family": row["task_family"],
            "text": render_messages_as_text(row["messages"], tokenizer),
        }
        for row in message_rows
    ]


def _build_quantization_config(
    torch_module: Any,
    transformers_module: Any,
    *,
    load_in_4bit: bool,
):
    if not load_in_4bit:
        return None
    compute_dtype = (
        torch_module.bfloat16 if torch_module.cuda.is_available() else torch_module.float32
    )
    return transformers_module.BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )


def train_sft(
    *,
    train_messages_path: Path,
    eval_messages_path: Path,
    output_dir: Path,
    model_name_or_path: str = DEFAULT_MODEL_NAME,
    max_length: int = 512,
    learning_rate: float = 2e-4,
    num_train_epochs: float = 3.0,
    seed: int = 17,
    load_in_4bit: bool = True,
    trust_remote_code: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    train_rows = load_message_rows(train_messages_path)
    eval_rows = load_message_rows(eval_messages_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    stack_readiness = probe_training_stack()
    summary: dict[str, Any] = {
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "model_name_or_path": model_name_or_path,
        "output_dir": str(output_dir),
        "training_stack": stack_readiness,
        "sft_config": build_sft_config_kwargs(
            output_dir=str(output_dir),
            learning_rate=learning_rate,
            num_train_epochs=num_train_epochs,
            max_length=max_length,
            seed=seed,
        ),
        "peft_config": build_peft_config_kwargs(),
        "load_in_4bit": load_in_4bit,
        "trust_remote_code": trust_remote_code,
        "dry_run": dry_run,
    }

    if dry_run:
        if not stack_readiness["ready"]:
            missing_modules = ", ".join(stack_readiness["missing_modules"])
            raise ValueError(f"Training stack missing required modules: {missing_modules}")
        return summary

    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    tokenizer = AutoTokenizer.from_pretrained(
        model_name_or_path,
        trust_remote_code=trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token

    train_dataset = Dataset.from_list(message_rows_to_text_records(train_rows, tokenizer))
    eval_dataset = Dataset.from_list(message_rows_to_text_records(eval_rows, tokenizer))

    quantization_config = _build_quantization_config(
        torch,
        type("TransformersProxy", (), {"BitsAndBytesConfig": BitsAndBytesConfig}),
        load_in_4bit=load_in_4bit,
    )
    device_map = "auto" if torch.cuda.is_available() else None
    torch_dtype = torch.bfloat16 if torch.cuda.is_available() else None

    model = AutoModelForCausalLM.from_pretrained(
        model_name_or_path,
        trust_remote_code=trust_remote_code,
        device_map=device_map,
        torch_dtype=torch_dtype,
        quantization_config=quantization_config,
    )
    model.config.use_cache = False

    sft_kwargs = build_sft_config_kwargs(
        output_dir=str(output_dir),
        learning_rate=learning_rate,
        num_train_epochs=num_train_epochs,
        max_length=max_length,
        seed=seed,
    )
    if torch.cuda.is_available():
        sft_kwargs["bf16"] = True
    else:
        sft_kwargs["use_cpu"] = True
    training_args = SFTConfig(**sft_kwargs)

    peft_kwargs = build_peft_config_kwargs()
    task_type_name = peft_kwargs.pop("task_type")
    peft_config = LoraConfig(task_type=getattr(TaskType, task_type_name), **peft_kwargs)

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    train_result = trainer.train()
    adapter_output_dir = output_dir / "adapter"
    trainer.save_model(str(adapter_output_dir))
    tokenizer.save_pretrained(str(adapter_output_dir))

    summary.update(
        {
            "train_metrics": train_result.metrics,
            "best_model_checkpoint": trainer.state.best_model_checkpoint,
            "adapter_output_dir": str(adapter_output_dir),
            "cuda_is_available": torch.cuda.is_available(),
            "device_name": (torch.cuda.get_device_name(0) if torch.cuda.is_available() else None),
        }
    )
    summary_path = output_dir / "train_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("train_messages_path", type=Path)
    parser.add_argument("eval_messages_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--model-name-or-path", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--num-train-epochs", type=float, default=3.0)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--no-load-in-4bit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = train_sft(
        train_messages_path=args.train_messages_path,
        eval_messages_path=args.eval_messages_path,
        output_dir=args.output_dir,
        model_name_or_path=args.model_name_or_path,
        max_length=args.max_length,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        seed=args.seed,
        load_in_4bit=not args.no_load_in_4bit,
        trust_remote_code=args.trust_remote_code,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
