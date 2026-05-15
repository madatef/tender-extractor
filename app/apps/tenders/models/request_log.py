"""
Database models for observability, cost tracking, and failure logging.
"""
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class APIRequestLog(models.Model):
    """
    Persists every extraction request with full metadata.
    Used for cost accounting, debugging, and usage analytics.
    """

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"

    request_id = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="api_logs"
    )
    endpoint = models.CharField(max_length=256, default="/api/v1/tender-extractor/")
    provider = models.CharField(max_length=64, null=True, blank=True)
    model = models.CharField(max_length=64, null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUCCESS
    )
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(
        max_digits=12, decimal_places=8, default=0
    )
    latency_ms = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"[{self.status}] {self.request_id} — {self.provider}"


class UsageAggregation(models.Model):
    """
    Hourly roll-up of usage stats per user.
    Populated by a Celery periodic task.
    """

    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="usage_agg"
    )
    hour_timestamp = models.DateTimeField(db_index=True)
    total_hits = models.PositiveIntegerField(default=0)
    success_hits = models.PositiveIntegerField(default=0)
    failure_hits = models.PositiveIntegerField(default=0)
    total_input_tokens = models.PositiveBigIntegerField(default=0)
    total_output_tokens = models.PositiveBigIntegerField(default=0)
    total_cost_usd = models.DecimalField(max_digits=12, decimal_places=8, default=0)

    class Meta:
        unique_together = [("user", "hour_timestamp")]
        ordering = ["-hour_timestamp"]

    def __str__(self):
        return f"Usage [{self.user_id}] @ {self.hour_timestamp}"


class ProviderFailureLog(models.Model):
    """
    Records individual provider-level failures for trend analysis.
    """

    provider = models.CharField(max_length=64)
    model = models.CharField(max_length=64, null=True, blank=True)
    request_id = models.CharField(max_length=128, null=True, blank=True)
    exception_type = models.CharField(max_length=128, null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    failure_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["provider", "created_at"])]

    def __str__(self):
        return f"Failure [{self.provider}] @ {self.created_at}"
