"""Prompting helpers for the LegalLM student pilot."""

from __future__ import annotations

DEFAULT_SYSTEM_PROMPT = (
    "You are a legal analysis assistant. Reply in exactly two lines: "
    "'Answer: ...' and 'Reasoning: ...'. Keep reasoning concise and legally grounded."
)

CLOSED_LABELS_BY_FAMILY = {
    "definition_classification": ("Yes", "No"),
    "policy_regulatory_qa": ("Required", "Prohibited", "Permitted", "Conditional"),
    "sara_entailment": ("Entailment", "Contradiction"),
}


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.strip().split())


def format_assistant_response(answer: str, reasoning: str) -> str:
    answer_text = _collapse_whitespace(answer)
    reasoning_text = _collapse_whitespace(reasoning)
    if not answer_text:
        raise ValueError("answer must be non-empty")
    if not reasoning_text:
        raise ValueError("reasoning must be non-empty")
    return f"Answer: {answer_text}\nReasoning: {reasoning_text}"


def build_training_messages(
    user_prompt: str,
    teacher_answer: str,
    teacher_reasoning_short: str,
    *,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _collapse_whitespace(system_prompt)},
        {"role": "user", "content": user_prompt.strip()},
        {
            "role": "assistant",
            "content": format_assistant_response(teacher_answer, teacher_reasoning_short),
        },
    ]


def build_inference_messages(
    user_prompt: str,
    *,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _collapse_whitespace(system_prompt)},
        {"role": "user", "content": user_prompt.strip()},
    ]
