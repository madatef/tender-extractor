"""
LLMOrchestrator — executes the provider sequence with retries and fallback.

Execution order:
  1. Primary provider (gpt-4o-mini) — up to MAX_RETRIES attempts
  2. Fallback provider (gpt-5.2)    — up to MAX_RETRIES attempts

Returns the first successfully validated TenderSchema, or None if all fail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import structlog
from django.conf import settings

from apps.tenders.domain.llm_result import LLMResult
from apps.tenders.domain.schemas import TenderSchema
from apps.tenders.llm.providers.base import BaseLLMProvider
from apps.tenders.llm.providers.factory import build_provider
from apps.tenders.validators.json_validator import LLMJSONValidator

logger = structlog.get_logger(__name__)


@dataclass
class OrchestrationResult:
    tender: Optional[TenderSchema]
    used_provider: Optional[str]
    used_model: Optional[str]
    all_results: List[LLMResult] = field(default_factory=list)
    validation_error: Optional[str] = None
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_ms: float = 0.0
    success: bool = False


class LLMOrchestrator:
    def __init__(self):
        self._validator = LLMJSONValidator()
        self._max_retries: int = settings.LLM_MAX_RETRIES

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        request_id: str = "",
    ) -> OrchestrationResult:
        result = OrchestrationResult(tender=None, used_provider=None, used_model=None)

        primary_key = settings.PRIMARY_LLM_PROVIDER
        fallback_key = settings.FALLBACK_LLM_PROVIDER

        providers: List[Tuple[str, BaseLLMProvider]] = []
        try:
            providers.append((primary_key, build_provider(primary_key)))
        except Exception as exc:
            logger.error("orchestrator_primary_build_failed", error=str(exc))

        try:
            providers.append((fallback_key, build_provider(fallback_key)))
        except Exception as exc:
            logger.error("orchestrator_fallback_build_failed", error=str(exc))

        for provider_key, provider in providers:
            tender, llm_results = self._run_provider_with_retries(
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                request_id=request_id,
            )
            result.all_results.extend(llm_results)

            # Accumulate cost/tokens across all attempts
            for r in llm_results:
                result.total_cost_usd += r.cost_usd
                result.total_input_tokens += r.input_tokens
                result.total_output_tokens += r.output_tokens
                result.total_latency_ms += r.latency_ms

            if tender is not None:
                result.tender = tender
                result.used_provider = provider.provider_name
                result.used_model = provider.model_name
                result.success = True
                logger.info(
                    "orchestrator_success",
                    request_id=request_id,
                    provider=provider_key,
                    model=provider.model_name,
                    total_cost_usd=round(result.total_cost_usd, 6),
                )
                return result

            logger.warning(
                "orchestrator_provider_exhausted",
                request_id=request_id,
                provider=provider_key,
            )

        # All providers failed
        logger.error(
            "orchestrator_all_providers_failed",
            request_id=request_id,
            attempts=len(result.all_results),
        )
        result.success = False
        result.validation_error = "All LLM providers failed to produce valid output"
        return result

    def _run_provider_with_retries(
        self,
        provider: BaseLLMProvider,
        system_prompt: str,
        user_prompt: str,
        request_id: str,
    ) -> Tuple[Optional[TenderSchema], List[LLMResult]]:
        llm_results: List[LLMResult] = []

        for attempt in range(1, self._max_retries + 1):
            logger.info(
                "orchestrator_attempt",
                request_id=request_id,
                provider=provider.provider_name,
                model=provider.model_name,
                attempt=attempt,
            )

            llm_result = provider.extract(system_prompt, user_prompt)
            llm_results.append(llm_result)

            if not llm_result.success:
                logger.warning(
                    "orchestrator_provider_call_failed",
                    request_id=request_id,
                    provider=provider.provider_name,
                    attempt=attempt,
                    error=llm_result.error,
                )
                continue

            tender, error = self._validator.validate(
                llm_result.raw_text, request_id=request_id
            )
            if tender is not None:
                return tender, llm_results

            logger.warning(
                "orchestrator_validation_failed",
                request_id=request_id,
                provider=provider.provider_name,
                attempt=attempt,
                error=error,
            )

        return None, llm_results
