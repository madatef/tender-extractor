"""
RequestLoggingMiddleware — logs every inbound request and outbound response
using structured JSON via structlog.
"""
from __future__ import annotations

import time

import structlog
from django.http import HttpRequest, HttpResponse

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start = time.monotonic()

        logger.info(
            "http_request_received",
            method=request.method,
            path=request.path,
            user_agent=request.headers.get("User-Agent", ""),
        )

        response: HttpResponse = self.get_response(request)

        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "http_response_sent",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        return response
