"""
CorrelationIDMiddleware — generates or propagates X-Request-ID on every request.

The ID is:
  1. Read from the incoming X-Request-ID header (if client supplies one)
  2. Otherwise auto-generated as a UUID4

It is:
  - Stored in structlog context vars (so every log line in the request gets it)
  - Added to the outgoing response headers
"""
from __future__ import annotations

import uuid

import structlog
from django.http import HttpRequest, HttpResponse


class CorrelationIDMiddleware:
    HEADER = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.headers.get(self.HEADER) or str(uuid.uuid4())
        request.correlation_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response: HttpResponse = self.get_response(request)
        response[self.HEADER] = request_id
        return response
