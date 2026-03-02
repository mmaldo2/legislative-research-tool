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
    predict_v1,
    report_v1,
    summarize_v1,
    trend_narrative_v1,
    version_diff_v1,
)
from src.models.ai_analysis import AiAnalysis
from src.schemas.analysis import (
    BillSummaryOutput,
    ConstitutionalAnalysisOutput,
    PatternDetectionOutput,
    PredictionOutput,
    ReportOutput,
    TopicClassificationOutput,
    VersionDiffOutput,
)
from src.schemas.compare import BillComparisonOutput
from src.schemas.trend import TrendResponse, TrendSummaryResponse, TrendTopicResponse

logger = logging.getLogger(__name__)

# Text truncation limits — balances LLM context budget vs. analysis quality.
MAX_SINGLE_TEXT_CHARS = 50_000  # Full bill text (summarize, constitutional)
MAX_PAIRED_TEXT_CHARS = 25_000  # Each side of a comparison/diff

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
        self.client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
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
        skip_store: bool = False,
    ) -> T:
        """Run a single analysis: cache check, API call, parse, track, store.

        This is the common backbone for all analysis methods. Each public method
        prepares the hash/prompt and provides a typed fallback, then delegates here.
        """
        # 1. Check cache (skip for non-bill entities like reports)
        if not skip_store:
            cached = await self._check_cache(bill_id, analysis_type, prompt_version, c_hash)
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
        usage = self.cost_tracker.record(model, tokens_in, tokens_out, cost_label)

        # 5. Store in DB (skip for non-bill entities like reports)
        if not skip_store:
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
                bill_text=bill_text[:MAX_SINGLE_TEXT_CHARS],
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
            c_hash=self.content_hash(f"{title}:{summary}", classify_v1.PROMPT_VERSION),
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
        text_a = bill_a_text[:MAX_PAIRED_TEXT_CHARS]
        text_b = bill_b_text[:MAX_PAIRED_TEXT_CHARS]

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
                f"{version_a_text[:MAX_PAIRED_TEXT_CHARS]}:{version_b_text[:MAX_PAIRED_TEXT_CHARS]}",
                version_diff_v1.PROMPT_VERSION,
            ),
            system_prompt=version_diff_v1.SYSTEM_PROMPT,
            user_prompt=version_diff_v1.USER_PROMPT_TEMPLATE.format(
                identifier=identifier,
                jurisdiction=jurisdiction,
                version_a_name=version_a_name,
                version_a_text=version_a_text[:MAX_PAIRED_TEXT_CHARS],
                version_b_name=version_b_name,
                version_b_text=version_b_text[:MAX_PAIRED_TEXT_CHARS],
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
            c_hash=self.content_hash(bill_text, constitutional_v1.PROMPT_VERSION),
            system_prompt=constitutional_v1.SYSTEM_PROMPT,
            user_prompt=constitutional_v1.USER_PROMPT_TEMPLATE.format(
                identifier=identifier,
                jurisdiction=jurisdiction,
                title=title,
                bill_text=bill_text[:MAX_SINGLE_TEXT_CHARS],
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
                f"{source_text[:MAX_PAIRED_TEXT_CHARS]}:{similar_bills_text[:MAX_PAIRED_TEXT_CHARS]}",
                pattern_detect_v1.PROMPT_VERSION,
            ),
            system_prompt=pattern_detect_v1.SYSTEM_PROMPT,
            user_prompt=pattern_detect_v1.USER_PROMPT_TEMPLATE.format(
                source_identifier=source_identifier,
                source_jurisdiction=source_jurisdiction,
                source_title=source_title,
                source_text=source_text[:MAX_PAIRED_TEXT_CHARS],
                similar_bills_text=similar_bills_text[:MAX_PAIRED_TEXT_CHARS],
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

    async def predict_outcome(
        self,
        bill_id: str,
        identifier: str,
        jurisdiction: str,
        title: str,
        status: str,
        classification: str,
        sponsors_text: str,
        sponsor_count: int,
        actions_text: str,
        action_count: int,
        subjects: str,
        session_info: str,
    ) -> PredictionOutput:
        """Predict the likely outcome of a bill."""
        hash_input = f"{identifier}:{status}:{sponsors_text}:{actions_text}"
        return await self._run_analysis(
            bill_id=bill_id,
            analysis_type="prediction",
            prompt_version=predict_v1.PROMPT_VERSION,
            model=settings.summary_model,
            c_hash=self.content_hash(hash_input, predict_v1.PROMPT_VERSION),
            system_prompt=predict_v1.SYSTEM_PROMPT,
            user_prompt=predict_v1.USER_PROMPT_TEMPLATE.format(
                identifier=identifier,
                jurisdiction=jurisdiction,
                title=title,
                status=status,
                classification=classification,
                sponsors_text=sponsors_text[:5000],
                sponsor_count=sponsor_count,
                actions_text=actions_text[:5000],
                action_count=action_count,
                subjects=subjects,
                session_info=session_info,
            ),
            max_tokens=2048,
            output_type=PredictionOutput,
            fallback_fn=lambda text: PredictionOutput(
                predicted_outcome="uncertain",
                confidence=0.3,
                passage_probability=0.5,
                key_factors=[],
                historical_comparison=text,
                summary=text,
            ),
            cost_label="predict_outcome",
        )

    async def generate_report(
        self,
        report_id: str,
        query: str,
        bills_text: str,
        bill_count: int,
        jurisdiction_count: int,
        jurisdiction_filter: str | None = None,
    ) -> ReportOutput:
        """Generate a multi-bill research report."""
        jf = f"Jurisdiction Filter: {jurisdiction_filter}" if jurisdiction_filter else ""
        return await self._run_analysis(
            bill_id=report_id,
            analysis_type="report",
            prompt_version=report_v1.PROMPT_VERSION,
            model=settings.summary_model,
            c_hash=self.content_hash(f"{query}:{bills_text[:10000]}", report_v1.PROMPT_VERSION),
            system_prompt=report_v1.SYSTEM_PROMPT,
            user_prompt=report_v1.USER_PROMPT_TEMPLATE.format(
                query=query,
                jurisdiction_filter=jf,
                bill_count=bill_count,
                jurisdiction_count=jurisdiction_count,
                bills_text=bills_text[:MAX_SINGLE_TEXT_CHARS],
            ),
            max_tokens=8192,
            output_type=ReportOutput,
            fallback_fn=lambda text: ReportOutput(
                title=f"Report: {query}",
                executive_summary=text,
                sections=[],
                bills_analyzed=bill_count,
                jurisdictions_covered=[],
                key_findings=[],
                trends=[],
                confidence=0.3,
            ),
            cost_label="generate_report",
            skip_store=True,
        )

    async def generate_trend_narrative(
        self,
        bills_data: TrendResponse,
        actions_data: TrendResponse,
        topics_data: TrendTopicResponse,
        bucket: str = "month",
        group_by: str = "jurisdiction",
    ) -> TrendSummaryResponse:
        """Generate an LLM narrative summary from aggregated trend data."""
        period_covered = f"{bills_data.meta.date_from} to {bills_data.meta.date_to}"
        total_bills = bills_data.meta.total_count

        # Format data as text for the prompt
        bills_text = "\n".join(
            f"  {p.period} | {p.dimension}: {p.count}" for p in bills_data.data[:50]
        )
        actions_text = "\n".join(
            f"  {p.period} | {p.dimension}: {p.count}" for p in actions_data.data[:50]
        )
        topics_text = "\n".join(
            f"  {p.period} | {p.dimension}: {p.count} ({p.share_pct}%)"
            for p in topics_data.data[:50]
        )

        user_prompt = trend_narrative_v1.USER_PROMPT_TEMPLATE.format(
            period_covered=period_covered,
            group_by=group_by,
            bucket=bucket,
            bills_data=bills_text or "(no data)",
            actions_data=actions_text or "(no data)",
            topics_data=topics_text or "(no data)",
            total_bills=total_bills,
        )

        c_hash = self.content_hash(user_prompt, trend_narrative_v1.PROMPT_VERSION)

        try:
            result = await self._run_analysis(
                bill_id=f"trend-{c_hash[:12]}",
                analysis_type="trend_narrative",
                prompt_version=trend_narrative_v1.PROMPT_VERSION,
                model=settings.summary_model,
                c_hash=c_hash,
                system_prompt=trend_narrative_v1.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=2048,
                output_type=TrendSummaryResponse,
                fallback_fn=lambda text: TrendSummaryResponse(
                    narrative=text or "Unable to generate summary.",
                    key_findings=[],
                    confidence=0.3,
                ),
                cost_label="trend_narrative",
                skip_store=True,
            )
        except Exception:
            logger.exception("Failed to generate trend narrative")
            result = TrendSummaryResponse(
                narrative="Unable to generate trend summary at this time.",
                key_findings=[],
                confidence=0.0,
            )

        result.period_covered = period_covered
        result.bills_analyzed = total_bills
        return result
