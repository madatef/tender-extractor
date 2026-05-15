"""
Async task: persist API request log to the database.
Runs in the background so it doesn't add latency to the HTTP response.
"""
from __future__ import annotations

from typing import Optional

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(
    name="tenders.log_api_request",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    ignore_result=True,
)
def log_api_request_task(
    self,
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
        from apps.tenders.repositories.request_log_repo import RequestLogRepository

        RequestLogRepository.create(
            request_id=request_id,
            user_id=user_id,
            provider=provider,
            model=model,
            success=success,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
        logger.info("log_api_request_task_done", request_id=request_id)
    except Exception as exc:
        logger.error("log_api_request_task_failed", request_id=request_id, error=str(exc))
        raise self.retry(exc=exc)
