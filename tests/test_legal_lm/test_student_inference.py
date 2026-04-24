import json
from pathlib import Path

import pytest

from legal_lm.student.run_inference import (
    load_prompt_rows,
    prediction_row_from_prompt_row,
    render_prompt_messages,
    run_inference,
)


def make_prompt_row(example_id: str):
    return {
        "id": example_id,
        "source": "synthetic_eval",
        "task_family": "definition_classification",
        "user_prompt": f"Prompt for {example_id}?",
        "reference_answer": "Yes",
        "reference_reasoning_short": f"Reasoning for {example_id}.",
        "reference_rubric_points": ["State the right answer", "Keep it concise"],
        "doctrine": "Synthetic Doctrine",
        "messages": [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": f"Prompt for {example_id}?"},
        ],
    }


class _ChatTemplateTokenizer:
    def __init__(self):
        self.calls = []

    def apply_chat_template(self, messages, *, tokenize=False, add_generation_prompt=False):
        self.calls.append(
            {
                "messages": messages,
                "tokenize": tokenize,
                "add_generation_prompt": add_generation_prompt,
            }
        )
        return "<rendered prompt>"


class _NoTemplateTokenizer:
    pass


def test_load_prompt_rows_rejects_rows_without_final_user_turn(tmp_path: Path):
    path = tmp_path / "test_prompts.jsonl"
    rows = [
        make_prompt_row("good-1"),
        {
            **make_prompt_row("bad-1"),
            "messages": [
                {"role": "system", "content": "System prompt."},
                {"role": "assistant", "content": "Premature answer."},
            ],
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    with pytest.raises(ValueError, match="final user turn") as exc_info:
        load_prompt_rows(path)

    assert "bad-1" in str(exc_info.value)


def test_render_prompt_messages_uses_chat_template_with_generation_prompt():
    tokenizer = _ChatTemplateTokenizer()
    messages = make_prompt_row("row-1")["messages"]

    rendered = render_prompt_messages(messages, tokenizer)

    assert rendered == "<rendered prompt>"
    assert tokenizer.calls == [
        {
            "messages": messages,
            "tokenize": False,
            "add_generation_prompt": True,
        }
    ]


def test_render_prompt_messages_falls_back_to_role_blocks_with_assistant_prefix():
    messages = make_prompt_row("row-1")["messages"]

    rendered = render_prompt_messages(messages, _NoTemplateTokenizer())

    assert rendered == "System: System prompt.\n\nUser: Prompt for row-1?\n\nAssistant:"


def test_prediction_row_from_prompt_row_preserves_prompt_metadata_and_output():
    prompt_row = make_prompt_row("row-1")

    prediction_row = prediction_row_from_prompt_row(
        prompt_row,
        "Answer: Yes\nReasoning: It defines a legal term.",
    )

    assert prediction_row["id"] == "row-1"
    assert prediction_row["reference_answer"] == "Yes"
    assert prediction_row["messages"] == prompt_row["messages"]
    assert prediction_row["generated_text"] == "Answer: Yes\nReasoning: It defines a legal term."


def test_run_inference_dry_run_reports_config_without_writing_predictions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    prompts_path = tmp_path / "test_prompts.jsonl"
    output_path = tmp_path / "predictions.jsonl"
    prompts_path.write_text(json.dumps(make_prompt_row("row-1")) + "\n")

    monkeypatch.setattr(
        "legal_lm.student.run_inference.probe_inference_stack",
        lambda module_names=None: {
            "ready": True,
            "available_modules": ["torch", "transformers"],
            "missing_modules": [],
        },
    )

    summary = run_inference(
        prompts_path=prompts_path,
        output_path=output_path,
        model_name_or_path="test-model",
        adapter_path=None,
        dry_run=True,
        load_in_4bit=False,
    )

    assert summary == {
        "prompt_rows": 1,
        "model_name_or_path": "test-model",
        "adapter_path": None,
        "output_path": str(output_path),
        "max_new_tokens": 128,
        "temperature": 0.0,
        "top_p": 1.0,
        "load_in_4bit": False,
        "trust_remote_code": False,
        "dry_run": True,
        "inference_stack": {
            "ready": True,
            "available_modules": ["torch", "transformers"],
            "missing_modules": [],
        },
    }
    assert not output_path.exists()
