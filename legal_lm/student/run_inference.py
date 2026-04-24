"""Run base or adapter-backed LegalLM student inference on frozen prompt artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from legal_lm.student.prepare_dataset import load_jsonl, write_jsonl

DEFAULT_MODEL_NAME = "Qwen/Qwen3-4B-Instruct-2507"
DEFAULT_INFERENCE_STACK_MODULES = (
    "torch",
    "transformers",
    "peft",
    "bitsandbytes",
)


def probe_inference_stack(
    module_names: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    modules_to_check = module_names or DEFAULT_INFERENCE_STACK_MODULES
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


def load_prompt_rows(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    for row in rows:
        example_id = str(row.get("id", "<missing-id>"))
        messages = row.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError(f"{example_id} must contain a non-empty messages list")
        final_message = messages[-1]
        if not isinstance(final_message, dict) or final_message.get("role") != "user":
            raise ValueError(f"{example_id} must end with a final user turn")
        for index, message in enumerate(messages, start=1):
            if not isinstance(message, dict):
                raise ValueError(f"{example_id} message {index} must be a JSON object")
            if not isinstance(message.get("role"), str) or not message["role"].strip():
                raise ValueError(f"{example_id} message {index} must have a non-empty role")
            if not isinstance(message.get("content"), str) or not message["content"].strip():
                raise ValueError(f"{example_id} message {index} must have non-empty content")
    return rows


def _fallback_render_messages(messages: list[dict[str, str]]) -> str:
    rendered_parts = []
    for message in messages:
        role = message["role"].strip().capitalize()
        content = message["content"].strip()
        rendered_parts.append(f"{role}: {content}")
    rendered_parts.append("Assistant:")
    return "\n\n".join(rendered_parts)


def render_prompt_messages(messages: list[dict[str, str]], tokenizer: Any) -> str:
    apply_chat_template = getattr(tokenizer, "apply_chat_template", None)
    if callable(apply_chat_template):
        try:
            rendered = apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            if isinstance(rendered, str) and rendered.strip():
                return rendered
        except Exception:
            pass
    return _fallback_render_messages(messages)


def prediction_row_from_prompt_row(
    prompt_row: dict[str, Any], generated_text: str
) -> dict[str, Any]:
    return {
        **prompt_row,
        "generated_text": generated_text.strip(),
    }


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


def _model_input_device(model: Any, torch_module: Any):
    try:
        return model.device
    except Exception:
        pass
    try:
        return next(model.parameters()).device
    except Exception:
        return torch_module.device("cuda" if torch_module.cuda.is_available() else "cpu")


def _generate_text_for_prompt(
    *,
    prompt_row: dict[str, Any],
    model: Any,
    tokenizer: Any,
    torch_module: Any,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
) -> str:
    rendered_prompt = render_prompt_messages(prompt_row["messages"], tokenizer)
    encoded = tokenizer(rendered_prompt, return_tensors="pt")
    device = _model_input_device(model, torch_module)
    encoded = {key: value.to(device) for key, value in encoded.items()}
    generation_kwargs: dict[str, Any] = {
        **encoded,
        "max_new_tokens": max_new_tokens,
        "pad_token_id": tokenizer.pad_token_id,
    }
    if temperature > 0:
        generation_kwargs.update(
            {
                "do_sample": True,
                "temperature": temperature,
                "top_p": top_p,
            }
        )
    else:
        generation_kwargs["do_sample"] = False

    with torch_module.no_grad():
        output_ids = model.generate(**generation_kwargs)
    input_length = encoded["input_ids"].shape[1]
    generated_ids = output_ids[0][input_length:]
    return tokenizer.decode(generated_ids, skip_special_tokens=True).strip()


def run_inference(
    *,
    prompts_path: Path,
    output_path: Path,
    model_name_or_path: str = DEFAULT_MODEL_NAME,
    adapter_path: Path | None = None,
    max_new_tokens: int = 128,
    temperature: float = 0.0,
    top_p: float = 1.0,
    load_in_4bit: bool = True,
    trust_remote_code: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    prompt_rows = load_prompt_rows(prompts_path)
    stack_readiness = probe_inference_stack()
    summary: dict[str, Any] = {
        "prompt_rows": len(prompt_rows),
        "model_name_or_path": model_name_or_path,
        "adapter_path": str(adapter_path) if adapter_path else None,
        "output_path": str(output_path),
        "max_new_tokens": max_new_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "load_in_4bit": load_in_4bit,
        "trust_remote_code": trust_remote_code,
        "dry_run": dry_run,
        "inference_stack": stack_readiness,
    }

    if dry_run:
        if not stack_readiness["ready"]:
            missing_modules = ", ".join(stack_readiness["missing_modules"])
            raise ValueError(f"Inference stack missing required modules: {missing_modules}")
        return summary

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(
        model_name_or_path,
        trust_remote_code=trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token

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
    if adapter_path is not None:
        model = PeftModel.from_pretrained(model, str(adapter_path))
    model.eval()

    prediction_rows = [
        prediction_row_from_prompt_row(
            prompt_row,
            _generate_text_for_prompt(
                prompt_row=prompt_row,
                model=model,
                tokenizer=tokenizer,
                torch_module=torch,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
            ),
        )
        for prompt_row in prompt_rows
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_path, prediction_rows)
    summary["status"] = "generated"
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompts_path", type=Path)
    parser.add_argument("output_path", type=Path)
    parser.add_argument("--model-name-or-path", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--adapter-path", type=Path, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--no-load-in-4bit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = run_inference(
        prompts_path=args.prompts_path,
        output_path=args.output_path,
        model_name_or_path=args.model_name_or_path,
        adapter_path=args.adapter_path,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        load_in_4bit=not args.no_load_in_4bit,
        trust_remote_code=args.trust_remote_code,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
