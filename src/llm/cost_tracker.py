"""Track LLM token usage and costs."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Pricing per million tokens (as of Feb 2026)
PRICING = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
}

# Batch API discount
BATCH_DISCOUNT = 0.5


@dataclass
class UsageRecord:
    model: str
    tokens_input: int
    tokens_output: int
    cost_usd: float
    task_type: str


@dataclass
class CostTracker:
    records: list[UsageRecord] = field(default_factory=list)

    def record(
        self,
        model: str,
        tokens_input: int,
        tokens_output: int,
        task_type: str,
        batch: bool = False,
    ) -> UsageRecord:
        pricing = PRICING.get(model, {"input": 3.00, "output": 15.00})
        discount = BATCH_DISCOUNT if batch else 1.0

        cost = (
            (tokens_input / 1_000_000) * pricing["input"] * discount
            + (tokens_output / 1_000_000) * pricing["output"] * discount
        )

        record = UsageRecord(
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=round(cost, 6),
            task_type=task_type,
        )
        self.records.append(record)
        logger.info(
            f"LLM cost: ${cost:.4f} ({tokens_input} in / {tokens_output} out) "
            f"model={model} task={task_type}"
        )
        return record

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def total_tokens(self) -> tuple[int, int]:
        return (
            sum(r.tokens_input for r in self.records),
            sum(r.tokens_output for r in self.records),
        )

    def summary(self) -> str:
        total_in, total_out = self.total_tokens
        return (
            f"LLM Usage: {len(self.records)} calls, "
            f"{total_in:,} input tokens, {total_out:,} output tokens, "
            f"${self.total_cost:.4f} total cost"
        )
