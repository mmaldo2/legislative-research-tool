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
from src.llm.prompts import (
    classify_v1,
    compare_v1,
    constitutional_v1,
    pattern_detect_v1,
    summarize_v1,
    version_diff_v1,
)
from src.models.ai_analysis import AiAnalysis
from src.schemas.analysis import (
    BillSummaryOutput,
    ConstitutionalAnalysisOutput,
    PatternDetectionOutput,
    TopicClassificationOutput,
    VersionDiffOutput,
)
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

    def __init__(
        self,
        db_session: AsyncSession | None = None,
        client: anthropic.AsyncAnthropic | None = None,
    ):
        self.client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key
        )
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

        # Truncate texts to match what the prompt actually sends
        text_a = bill_a_text[:25000]
        text_b = bill_b_text[:25000]

        # Canonicalize order so compare(A,B) and compare(B,A) share cache
        canonical_ids = sorted([bill_id_a, bill_id_b])
        if canonical_ids[0] == bill_id_a:
            hash_input = f"{text_a}:{text_b}"
        else:
            hash_input = f"{text_b}:{text_a}"
        c_hash = self.content_hash(hash_input, prompt_version)
        cache_bill_id = canonical_ids[0]

        cached = await self._check_cache(
            cache_bill_id, "comparison", prompt_version, c_hash
        )
        if cached:
            return BillComparisonOutput(**cached)

        user_prompt = compare_v1.USER_PROMPT_TEMPLATE.format(
            bill_a_identifier=bill_a_identifier,
            bill_a_title=bill_a_title,
            bill_a_text=text_a,
            bill_b_identifier=bill_b_identifier,
            bill_b_title=bill_b_title,
            bill_b_text=text_b,
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
            bill_id=cache_bill_id,
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

    async def version_diff(
        self,
        bill_id: str,
        identifier: str,
        jurisdiction: str,
        version_a_name: str,
        version_a_text: str,
        version_b_name: str,
        version_b_text: str,
    ) -> VersionDiffOutput:
        """Analyze differences between two versions of the same bill."""
        prompt_version = version_diff_v1.PROMPT_VERSION
        model = settings.summary_model
        hash_input = f"{version_a_text[:25000]}:{version_b_text[:25000]}"
        c_hash = self.content_hash(hash_input, prompt_version)

        cached = await self._check_cache(bill_id, "version_diff", prompt_version, c_hash)
        if cached:
            return VersionDiffOutput(**cached)

        user_prompt = version_diff_v1.USER_PROMPT_TEMPLATE.format(
            identifier=identifier,
            jurisdiction=jurisdiction,
            version_a_name=version_a_name,
            version_a_text=version_a_text[:25000],
            version_b_name=version_b_name,
            version_b_text=version_b_text[:25000],
        )

        response = await self.client.messages.create(
            model=model,
            max_tokens=4096,
            system=version_diff_v1.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = response.content[0].text
        try:
            result_data = json.loads(response_text)
            output = VersionDiffOutput(**result_data)
        except (json.JSONDecodeError, ValueError):
            output = VersionDiffOutput(
                version_a_name=version_a_name,
                version_b_name=version_b_name,
                changes=[],
                summary_of_changes=response_text,
                direction_of_change="unknown",
                amendments_incorporated=[],
                confidence=0.3,
            )

        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        usage = self.cost_tracker.record(model, tokens_in, tokens_out, "version_diff")

        result_dict = output.model_dump()
        await self._store_result(
            bill_id=bill_id,
            analysis_type="version_diff",
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

    async def constitutional_analysis(
        self,
        bill_id: str,
        bill_text: str,
        identifier: str = "",
        jurisdiction: str = "",
        title: str = "",
    ) -> ConstitutionalAnalysisOutput:
        """Analyze a bill for potential constitutional concerns."""
        prompt_version = constitutional_v1.PROMPT_VERSION
        model = settings.summary_model
        c_hash = self.content_hash(bill_text, prompt_version)

        cached = await self._check_cache(
            bill_id, "constitutional", prompt_version, c_hash
        )
        if cached:
            return ConstitutionalAnalysisOutput(**cached)

        user_prompt = constitutional_v1.USER_PROMPT_TEMPLATE.format(
            identifier=identifier,
            jurisdiction=jurisdiction,
            title=title,
            bill_text=bill_text[:50000],
        )

        response = await self.client.messages.create(
            model=model,
            max_tokens=4096,
            system=constitutional_v1.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = response.content[0].text
        try:
            result_data = json.loads(response_text)
            output = ConstitutionalAnalysisOutput(**result_data)
        except (json.JSONDecodeError, ValueError):
            output = ConstitutionalAnalysisOutput(
                concerns=[],
                preemption_issues=[],
                has_severability_clause=False,
                overall_risk_level="unknown",
                summary=response_text,
                confidence=0.3,
            )

        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        usage = self.cost_tracker.record(
            model, tokens_in, tokens_out, "constitutional_analysis"
        )

        result_dict = output.model_dump()
        await self._store_result(
            bill_id=bill_id,
            analysis_type="constitutional",
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

    async def pattern_detect(
        self,
        source_bill_id: str,
        source_text: str,
        source_identifier: str,
        source_jurisdiction: str,
        source_title: str,
        similar_bills_text: str,
    ) -> PatternDetectionOutput:
        """Detect cross-jurisdictional patterns and model legislation."""
        prompt_version = pattern_detect_v1.PROMPT_VERSION
        model = settings.summary_model
        hash_input = f"{source_text[:25000]}:{similar_bills_text[:25000]}"
        c_hash = self.content_hash(hash_input, prompt_version)

        cached = await self._check_cache(
            source_bill_id, "pattern_detect", prompt_version, c_hash
        )
        if cached:
            return PatternDetectionOutput(**cached)

        user_prompt = pattern_detect_v1.USER_PROMPT_TEMPLATE.format(
            source_identifier=source_identifier,
            source_jurisdiction=source_jurisdiction,
            source_title=source_title,
            source_text=source_text[:25000],
            similar_bills_text=similar_bills_text[:25000],
        )

        response = await self.client.messages.create(
            model=model,
            max_tokens=4096,
            system=pattern_detect_v1.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = response.content[0].text
        try:
            result_data = json.loads(response_text)
            output = PatternDetectionOutput(**result_data)
        except (json.JSONDecodeError, ValueError):
            output = PatternDetectionOutput(
                pattern_type="unknown",
                common_framework=response_text,
                bills_analyzed=[],
                shared_provisions=[],
                key_variations=[],
                model_legislation_confidence=0.0,
                summary=response_text,
                confidence=0.3,
            )

        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        usage = self.cost_tracker.record(model, tokens_in, tokens_out, "pattern_detect")

        result_dict = output.model_dump()
        await self._store_result(
            bill_id=source_bill_id,
            analysis_type="pattern_detect",
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
