"""
Repository layer — all DB access for tenders goes through here.
Keeps models out of service/orchestrator logic.
"""
from __future__ import annotations

from typing import Optional

import structlog

from apps.tenders.models import APIRequestLog, ProviderFailureLog

logger = structlog.get_logger(__name__)


class RequestLogRepository:
    @staticmethod
    def create(
        request_id: str,
        user_id: Optional[int],
        provider: Optional[str],
        model: Optional[str],
        success: bool,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: float,
    ) -> None:
        try:
            APIRequestLog.objects.create(
                request_id=request_id,
                user_id=user_id,
                provider=provider or "",
                model=model or "",
                status=APIRequestLog.Status.SUCCESS if success else APIRequestLog.Status.FAILURE,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost_usd,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            logger.error(
                "request_log_create_failed",
                request_id=request_id,
                error=str(exc),
            )

    @staticmethod
    def log_provider_failure(
        provider: str,
        model: Optional[str],
        request_id: Optional[str],
        exception_type: Optional[str],
        retry_count: int,
        failure_reason: Optional[str],
    ) -> None:
        try:
            ProviderFailureLog.objects.create(
                provider=provider,
                model=model or "",
                request_id=request_id or "",
                exception_type=exception_type or "",
                retry_count=retry_count,
                failure_reason=failure_reason or "",
            )
        except Exception as exc:
            logger.error(
                "provider_failure_log_create_failed",
                provider=provider,
                error=str(exc),
            )
