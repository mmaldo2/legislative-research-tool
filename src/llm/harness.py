"""Core LLM harness for all AI analysis operations.

Uses the Anthropic SDK with native structured outputs (GA as of 2026).
Content-hash caching prevents re-processing unchanged bills.
"""

import hashlib
import json
import logging

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.llm.cost_tracker import CostTracker
from src.llm.prompts import classify_v1, compare_v1, summarize_v1
from src.models.ai_analysis import AiAnalysis
from src.schemas.analysis import BillSummaryOutput, TopicClassificationOutput
from src.schemas.compare import BillComparisonOutput

logger = logging.getLogger(__name__)


class LLMHarness:
    """Core harness for all LLM operations.

    Handles:
    - Anthropic SDK with native structured outputs
    - Content-hash based caching (don't re-analyze unchanged bills)
    - Cost tracking per operation
    - Prompt versioning
    """

    def __init__(self, db_session: AsyncSession | None = None):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.cost_tracker = CostTracker()
        self.db_session = db_session

    @staticmethod
    def content_hash(text: str, prompt_version: str) -> str:
        """Generate hash of input text + prompt version for cache keying."""
        key = f"{prompt_version}:{text}"
        return hashlib.sha256(key.encode()).hexdigest()

    async def _check_cache(
        self, bill_id: str, analysis_type: str, prompt_version: str, c_hash: str
    ) -> dict | None:
        """Check if we already have a cached result for this content+prompt."""
        if not self.db_session:
            return None

        result = await self.db_session.execute(
            select(AiAnalysis).where(
                AiAnalysis.bill_id == bill_id,
                AiAnalysis.analysis_type == analysis_type,
                AiAnalysis.prompt_version == prompt_version,
                AiAnalysis.content_hash == c_hash,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Cache hit for %s on bill %s", analysis_type, bill_id)
            return existing.result
        return None

    async def _store_result(
        self,
        bill_id: str,
        analysis_type: str,
        result: dict,
        model: str,
        prompt_version: str,
        c_hash: str,
        tokens_input: int,
        tokens_output: int,
        cost_usd: float,
        confidence: float | None = None,
    ) -> None:
        """Store analysis result in the database."""
        if not self.db_session:
            return

        analysis = AiAnalysis(
            bill_id=bill_id,
            analysis_type=analysis_type,
            result=result,
            model_used=model,
            prompt_version=prompt_version,
            content_hash=c_hash,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
            confidence=confidence,
        )
        self.db_session.add(analysis)
        await self.db_session.flush()

    async def summarize(
        self,
        bill_id: str,
        bill_text: str,
        identifier: str = "",
        jurisdiction: str = "",
        title: str = "",
    ) -> BillSummaryOutput:
        """Generate a structured summary of a bill."""
        prompt_version = summarize_v1.PROMPT_VERSION
        model = settings.summary_model
        c_hash = self.content_hash(bill_text, prompt_version)

        # Check cache
        cached = await self._check_cache(bill_id, "summary", prompt_version, c_hash)
        if cached:
            return BillSummaryOutput(**cached)

        # Build prompt
        user_prompt = summarize_v1.USER_PROMPT_TEMPLATE.format(
            identifier=identifier,
            jurisdiction=jurisdiction,
            title=title,
            bill_text=bill_text[:50000],  # Truncate very long bills
        )

        # Call Claude with structured output
        response = await self.client.messages.create(
            model=model,
            max_tokens=2048,
            system=summarize_v1.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Parse the response text as JSON
        response_text = response.content[0].text
        try:
            result_data = json.loads(response_text)
            output = BillSummaryOutput(**result_data)
        except (json.JSONDecodeError, ValueError):
            # Fallback: treat the response as a plain-text summary
            output = BillSummaryOutput(
                plain_english_summary=response_text,
                key_provisions=[],
                affected_populations=[],
                changes_to_existing_law=[],
                confidence=0.5,
            )

        # Track costs
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        usage = self.cost_tracker.record(model, tokens_in, tokens_out, "summarize")

        # Store in DB
        result_dict = output.model_dump()
        await self._store_result(
            bill_id=bill_id,
            analysis_type="summary",
            result=result_dict,
            model=model,
            prompt_version=prompt_version,
            c_hash=c_hash,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost_usd=usage.cost_usd,
            confidence=output.confidence,
        )

        return output

    async def classify(
        self,
        bill_id: str,
        identifier: str,
        title: str,
        summary: str,
    ) -> TopicClassificationOutput:
        """Classify a bill into policy topics."""
        prompt_version = classify_v1.PROMPT_VERSION
        model = settings.classify_model
        c_hash = self.content_hash(f"{title}:{summary}", prompt_version)

        cached = await self._check_cache(bill_id, "topics", prompt_version, c_hash)
        if cached:
            return TopicClassificationOutput(**cached)

        user_prompt = classify_v1.USER_PROMPT_TEMPLATE.format(
            identifier=identifier,
            title=title,
            summary=summary,
        )

        response = await self.client.messages.create(
            model=model,
            max_tokens=512,
            system=classify_v1.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = response.content[0].text
        try:
            result_data = json.loads(response_text)
            output = TopicClassificationOutput(**result_data)
        except (json.JSONDecodeError, ValueError):
            output = TopicClassificationOutput(
                primary_topic="Uncategorized",
                secondary_topics=[],
                policy_area="General",
                confidence=0.3,
            )

        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        usage = self.cost_tracker.record(model, tokens_in, tokens_out, "classify")

        result_dict = output.model_dump()
        await self._store_result(
            bill_id=bill_id,
            analysis_type="topics",
            result=result_dict,
            model=model,
            prompt_version=prompt_version,
            c_hash=c_hash,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost_usd=usage.cost_usd,
            confidence=output.confidence,
        )

        return output

    async def compare(
        self,
        bill_id_a: str,
        bill_id_b: str,
        bill_a_text: str,
        bill_a_identifier: str,
        bill_a_title: str,
        bill_b_text: str,
        bill_b_identifier: str,
        bill_b_title: str,
    ) -> BillComparisonOutput:
        """Compare two bills side-by-side."""
        prompt_version = compare_v1.PROMPT_VERSION
        model = settings.summary_model
        c_hash = self.content_hash(f"{bill_a_text}:{bill_b_text}", prompt_version)

        cached = await self._check_cache(bill_id_a, "comparison", prompt_version, c_hash)
        if cached:
            return BillComparisonOutput(**cached)

        user_prompt = compare_v1.USER_PROMPT_TEMPLATE.format(
            bill_a_identifier=bill_a_identifier,
            bill_a_title=bill_a_title,
            bill_a_text=bill_a_text[:25000],
            bill_b_identifier=bill_b_identifier,
            bill_b_title=bill_b_title,
            bill_b_text=bill_b_text[:25000],
        )

        response = await self.client.messages.create(
            model=model,
            max_tokens=2048,
            system=compare_v1.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = response.content[0].text
        try:
            result_data = json.loads(response_text)
            output = BillComparisonOutput(**result_data)
        except (json.JSONDecodeError, ValueError):
            output = BillComparisonOutput(
                shared_provisions=[],
                unique_to_a=[],
                unique_to_b=[],
                key_differences=[response_text],
                overall_assessment=response_text,
                similarity_score=0.5,
                is_model_legislation=False,
                confidence=0.3,
            )

        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        usage = self.cost_tracker.record(model, tokens_in, tokens_out, "compare")

        result_dict = output.model_dump()
        await self._store_result(
            bill_id=bill_id_a,
            analysis_type="comparison",
            result=result_dict,
            model=model,
            prompt_version=prompt_version,
            c_hash=c_hash,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost_usd=usage.cost_usd,
            confidence=output.confidence,
        )

        return output
