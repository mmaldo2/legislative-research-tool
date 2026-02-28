from pydantic import BaseModel


class BillSummaryOutput(BaseModel):
    """Structured output for bill summarization — used as LLM output schema."""

    plain_english_summary: str
    key_provisions: list[str]
    affected_populations: list[str]
    changes_to_existing_law: list[str]
    fiscal_implications: str | None = None
    effective_date: str | None = None
    confidence: float


class TopicClassificationOutput(BaseModel):
    """Structured output for topic classification."""

    primary_topic: str
    secondary_topics: list[str]
    policy_area: str
    confidence: float


class BillComparisonOutput(BaseModel):
    """Structured output for comparing two bills or bill versions."""

    similarities: list[str]
    differences: list[str]
    key_changes: list[str]
    overall_assessment: str
    similarity_score: float
