"""
TenderExtractionService — the single entry point for the extraction pipeline.

Responsibilities:
  - Build prompts
  - Run the LLM orchestrator
  - Handle graceful failure
  - Persist request log
  - Dispatch async side-effect tasks
  - Return a clean response dict
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog

from apps.tenders.domain.schemas import TenderSchema
from apps.tenders.llm.orchestrator import LLMOrchestrator, OrchestrationResult
from apps.tenders.prompts.builder import OutputLanguage, PromptBuilder

logger = structlog.get_logger(__name__)


@dataclass
class ExtractionResponse:
    request_id: str
    tender: dict
    provider_used: Optional[str]
    model_used: Optional[str]
    success: bool
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float


class TenderExtractionService:
    def __init__(self):
        self._prompt_builder = PromptBuilder()
        self._orchestrator = LLMOrchestrator()

    def extract(
        self,
        text: str,
        output_language: OutputLanguage,
        request_id: str,
        user_id: Optional[int] = None,
    ) -> ExtractionResponse:
        logger.info(
            "extraction_started",
            request_id=request_id,
            output_language=output_language,
            text_length=len(text),
            user_id=user_id,
        )

        system_prompt = self._prompt_builder.build_system_prompt(output_language)
        user_prompt = self._prompt_builder.build_user_prompt(text)

        orch_result: OrchestrationResult = self._orchestrator.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            request_id=request_id,
        )

        if orch_result.success and orch_result.tender:
            tender_dict = orch_result.tender.to_response_dict()
            success = True
        else:
            tender_dict = TenderSchema.empty().to_response_dict()
            success = False
            logger.error(
                "extraction_complete_failure",
                request_id=request_id,
                error=orch_result.validation_error,
            )
            self._dispatch_failure_alert(request_id, orch_result)

        response = ExtractionResponse(
            request_id=request_id,
            tender=tender_dict,
            provider_used=orch_result.used_provider,
            model_used=orch_result.used_model,
            success=success,
            input_tokens=orch_result.total_input_tokens,
            output_tokens=orch_result.total_output_tokens,
            cost_usd=round(orch_result.total_cost_usd, 6),
            latency_ms=round(orch_result.total_latency_ms, 2),
        )

        self._dispatch_log_task(response, user_id)

        logger.info(
            "extraction_finished",
            request_id=request_id,
            success=success,
            provider=orch_result.used_provider,
            cost_usd=response.cost_usd,
            latency_ms=response.latency_ms,
        )

        return response

    def _dispatch_log_task(
        self, response: ExtractionResponse, user_id: Optional[int]
    ) -> None:
        try:
            from apps.tenders.tasks.logging_tasks import log_api_request_task

            log_api_request_task.delay(
                request_id=response.request_id,
                user_id=user_id,
                provider=response.provider_used,
                model=response.model_used,
                success=response.success,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=response.cost_usd,
                latency_ms=response.latency_ms,
            )
        except Exception as exc:
            logger.warning("dispatch_log_task_failed", error=str(exc))

    def _dispatch_failure_alert(
        self, request_id: str, orch_result: OrchestrationResult
    ) -> None:
        try:
            from apps.tenders.tasks.slack_tasks import send_slack_alert_task

            send_slack_alert_task.delay(
                request_id=request_id,
                error_summary=orch_result.validation_error or "Unknown failure",
                providers_tried=[r.provider for r in orch_result.all_results],
            )
        except Exception as exc:
            logger.warning("dispatch_slack_task_failed", error=str(exc))
