"""Core LLM harness for all AI analysis operations.

Uses the Anthropic SDK with native structured outputs (GA as of 2026).
Content-hash caching prevents re-processing unchanged bills.
"""

import hashlib
import json
import logging
from collections.abc import Callable
from typing import TypeVar

import anthropic
from pydantic import BaseModel
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

T = TypeVar("T", bound=BaseModel)


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

    async def _run_analysis(
        self,
        *,
        bill_id: str,
        analysis_type: str,
        prompt_version: str,
        model: str,
        c_hash: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        output_type: type[T],
        fallback_fn: Callable[[str], T],
        cost_label: str,
    ) -> T:
        """Run a single analysis: cache check, API call, parse, track, store.

        This is the common backbone for all analysis methods. Each public method
        prepares the hash/prompt and provides a typed fallback, then delegates here.
        """
        # 1. Check cache
        cached = await self._check_cache(
            bill_id, analysis_type, prompt_version, c_hash
        )
        if cached:
            return output_type(**cached)

        # 2. Call Anthropic API
        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # 3. Parse JSON response, fall back on failure
        if not response.content:
            response_text = ""
        else:
            response_text = response.content[0].text

        try:
            result_data = json.loads(response_text)
            output = output_type(**result_data)
        except (json.JSONDecodeError, ValueError):
            output = fallback_fn(response_text)

        # 4. Track costs
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        usage = self.cost_tracker.record(
            model, tokens_in, tokens_out, cost_label
        )

        # 5. Store in DB
        result_dict = output.model_dump()
        await self._store_result(
            bill_id=bill_id,
            analysis_type=analysis_type,
            result=result_dict,
            model=model,
            prompt_version=prompt_version,
            c_hash=c_hash,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost_usd=usage.cost_usd,
            confidence=getattr(output, "confidence", None),
        )

        return output

    # ------------------------------------------------------------------
    # Public analysis methods — thin wrappers around _run_analysis
    # ------------------------------------------------------------------

    async def summarize(
        self,
        bill_id: str,
        bill_text: str,
        identifier: str = "",
        jurisdiction: str = "",
        title: str = "",
    ) -> BillSummaryOutput:
        """Generate a structured summary of a bill."""
        return await self._run_analysis(
            bill_id=bill_id,
            analysis_type="summary",
            prompt_version=summarize_v1.PROMPT_VERSION,
            model=settings.summary_model,
            c_hash=self.content_hash(bill_text, summarize_v1.PROMPT_VERSION),
            system_prompt=summarize_v1.SYSTEM_PROMPT,
            user_prompt=summarize_v1.USER_PROMPT_TEMPLATE.format(
                identifier=identifier,
                jurisdiction=jurisdiction,
                title=title,
                bill_text=bill_text[:50000],
            ),
            max_tokens=2048,
            output_type=BillSummaryOutput,
            fallback_fn=lambda text: BillSummaryOutput(
                plain_english_summary=text or "Analysis unavailable.",
                key_provisions=[],
                affected_populations=[],
                changes_to_existing_law=[],
                confidence=0.5,
            ),
            cost_label="summarize",
        )

    async def classify(
        self,
        bill_id: str,
        identifier: str,
        title: str,
        summary: str,
    ) -> TopicClassificationOutput:
        """Classify a bill into policy topics."""
        return await self._run_analysis(
            bill_id=bill_id,
            analysis_type="topics",
            prompt_version=classify_v1.PROMPT_VERSION,
            model=settings.classify_model,
            c_hash=self.content_hash(
                f"{title}:{summary}", classify_v1.PROMPT_VERSION
            ),
            system_prompt=classify_v1.SYSTEM_PROMPT,
            user_prompt=classify_v1.USER_PROMPT_TEMPLATE.format(
                identifier=identifier,
                title=title,
                summary=summary,
            ),
            max_tokens=512,
            output_type=TopicClassificationOutput,
            fallback_fn=lambda _text: TopicClassificationOutput(
                primary_topic="Uncategorized",
                secondary_topics=[],
                policy_area="General",
                confidence=0.3,
            ),
            cost_label="classify",
        )

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
        text_a = bill_a_text[:25000]
        text_b = bill_b_text[:25000]

        # Canonicalize order so compare(A,B) and compare(B,A) share cache
        canonical_ids = sorted([bill_id_a, bill_id_b])
        if canonical_ids[0] == bill_id_a:
            hash_input = f"{text_a}:{text_b}"
        else:
            hash_input = f"{text_b}:{text_a}"

        return await self._run_analysis(
            bill_id=canonical_ids[0],
            analysis_type="comparison",
            prompt_version=compare_v1.PROMPT_VERSION,
            model=settings.summary_model,
            c_hash=self.content_hash(hash_input, compare_v1.PROMPT_VERSION),
            system_prompt=compare_v1.SYSTEM_PROMPT,
            user_prompt=compare_v1.USER_PROMPT_TEMPLATE.format(
                bill_a_identifier=bill_a_identifier,
                bill_a_title=bill_a_title,
                bill_a_text=text_a,
                bill_b_identifier=bill_b_identifier,
                bill_b_title=bill_b_title,
                bill_b_text=text_b,
            ),
            max_tokens=2048,
            output_type=BillComparisonOutput,
            fallback_fn=lambda text: BillComparisonOutput(
                shared_provisions=[],
                unique_to_a=[],
                unique_to_b=[],
                key_differences=[text],
                overall_assessment=text,
                similarity_score=0.5,
                is_model_legislation=False,
                confidence=0.3,
            ),
            cost_label="compare",
        )

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
        return await self._run_analysis(
            bill_id=bill_id,
            analysis_type="version_diff",
            prompt_version=version_diff_v1.PROMPT_VERSION,
            model=settings.summary_model,
            c_hash=self.content_hash(
                f"{version_a_text[:25000]}:{version_b_text[:25000]}",
                version_diff_v1.PROMPT_VERSION,
            ),
            system_prompt=version_diff_v1.SYSTEM_PROMPT,
            user_prompt=version_diff_v1.USER_PROMPT_TEMPLATE.format(
                identifier=identifier,
                jurisdiction=jurisdiction,
                version_a_name=version_a_name,
                version_a_text=version_a_text[:25000],
                version_b_name=version_b_name,
                version_b_text=version_b_text[:25000],
            ),
            max_tokens=4096,
            output_type=VersionDiffOutput,
            fallback_fn=lambda text: VersionDiffOutput(
                version_a_name=version_a_name,
                version_b_name=version_b_name,
                changes=[],
                summary_of_changes=text,
                direction_of_change="unknown",
                amendments_incorporated=[],
                confidence=0.3,
            ),
            cost_label="version_diff",
        )

    async def constitutional_analysis(
        self,
        bill_id: str,
        bill_text: str,
        identifier: str = "",
        jurisdiction: str = "",
        title: str = "",
    ) -> ConstitutionalAnalysisOutput:
        """Analyze a bill for potential constitutional concerns."""
        return await self._run_analysis(
            bill_id=bill_id,
            analysis_type="constitutional",
            prompt_version=constitutional_v1.PROMPT_VERSION,
            model=settings.summary_model,
            c_hash=self.content_hash(
                bill_text, constitutional_v1.PROMPT_VERSION
            ),
            system_prompt=constitutional_v1.SYSTEM_PROMPT,
            user_prompt=constitutional_v1.USER_PROMPT_TEMPLATE.format(
                identifier=identifier,
                jurisdiction=jurisdiction,
                title=title,
                bill_text=bill_text[:50000],
            ),
            max_tokens=4096,
            output_type=ConstitutionalAnalysisOutput,
            fallback_fn=lambda text: ConstitutionalAnalysisOutput(
                concerns=[],
                preemption_issues=[],
                has_severability_clause=False,
                overall_risk_level="unknown",
                summary=text,
                confidence=0.3,
            ),
            cost_label="constitutional_analysis",
        )

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
        return await self._run_analysis(
            bill_id=source_bill_id,
            analysis_type="pattern_detect",
            prompt_version=pattern_detect_v1.PROMPT_VERSION,
            model=settings.summary_model,
            c_hash=self.content_hash(
                f"{source_text[:25000]}:{similar_bills_text[:25000]}",
                pattern_detect_v1.PROMPT_VERSION,
            ),
            system_prompt=pattern_detect_v1.SYSTEM_PROMPT,
            user_prompt=pattern_detect_v1.USER_PROMPT_TEMPLATE.format(
                source_identifier=source_identifier,
                source_jurisdiction=source_jurisdiction,
                source_title=source_title,
                source_text=source_text[:25000],
                similar_bills_text=similar_bills_text[:25000],
            ),
            max_tokens=4096,
            output_type=PatternDetectionOutput,
            fallback_fn=lambda text: PatternDetectionOutput(
                pattern_type="unknown",
                common_framework=text,
                bills_analyzed=[],
                shared_provisions=[],
                key_variations=[],
                model_legislation_confidence=0.0,
                summary=text,
                confidence=0.3,
            ),
            cost_label="pattern_detect",
        )
