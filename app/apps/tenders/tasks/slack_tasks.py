"""
Async task: send a Slack webhook alert when all LLM providers fail.
Falls back gracefully if no webhook URL is configured.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List

import requests
import structlog
from celery import shared_task
from django.conf import settings

logger = structlog.get_logger(__name__)


@shared_task(
    name="tenders.send_slack_alert",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    ignore_result=True,
)
def send_slack_alert_task(
    self,
    request_id: str,
    error_summary: str,
    providers_tried: List[str],
) -> None:
    webhook_url = getattr(settings, "SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        logger.info("slack_alert_skipped_no_webhook", request_id=request_id)
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    providers_str = ", ".join(set(providers_tried)) if providers_tried else "none"

    payload = {
        "text": ":rotating_light: *Tender Extractor — All Providers Failed*",
        "attachments": [
            {
                "color": "#FF0000",
                "fields": [
                    {"title": "Request ID", "value": request_id, "short": True},
                    {"title": "Providers Tried", "value": providers_str, "short": True},
                    {"title": "Error", "value": error_summary, "short": False},
                    {"title": "Timestamp", "value": timestamp, "short": True},
                ],
            }
        ],
    }

    try:
        resp = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("slack_alert_sent", request_id=request_id, status_code=resp.status_code)
    except requests.RequestException as exc:
        logger.error("slack_alert_failed", request_id=request_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task(
    name="tenders.aggregate_hourly_usage",
    ignore_result=True,
)
def aggregate_hourly_usage_task() -> None:
    """
    Rolls up the last hour's APIRequestLog entries into UsageAggregation.
    Intended to run every hour via Celery Beat.
    """
    from datetime import timedelta

    from django.db.models import Count, Sum
    from django.utils import timezone

    from apps.tenders.models import APIRequestLog, UsageAggregation

    now = timezone.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    hour_end = hour_start + timedelta(hours=1)

    logs = APIRequestLog.objects.filter(
        created_at__gte=hour_start, created_at__lt=hour_end
    )

    user_ids = logs.values_list("user_id", flat=True).distinct()

    for user_id in user_ids:
        user_logs = logs.filter(user_id=user_id)
        totals = user_logs.aggregate(
            total_hits=Count("id"),
            success_hits=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(status="success")),
            total_input=Sum("input_tokens"),
            total_output=Sum("output_tokens"),
            total_cost=Sum("estimated_cost_usd"),
        )
        UsageAggregation.objects.update_or_create(
            user_id=user_id,
            hour_timestamp=hour_start,
            defaults={
                "total_hits": totals["total_hits"] or 0,
                "success_hits": totals["success_hits"] or 0,
                "failure_hits": (totals["total_hits"] or 0) - (totals["success_hits"] or 0),
                "total_input_tokens": totals["total_input"] or 0,
                "total_output_tokens": totals["total_output"] or 0,
                "total_cost_usd": totals["total_cost"] or 0,
            },
        )

    logger.info("hourly_aggregation_done", hour=str(hour_start), users=len(list(user_ids)))
