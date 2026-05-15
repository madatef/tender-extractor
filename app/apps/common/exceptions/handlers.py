"""
Custom DRF exception handler.
Ensures all errors return a consistent JSON shape.
Never exposes internal stack traces or provider exceptions.
"""
from __future__ import annotations

import structlog
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = structlog.get_logger(__name__)


def custom_exception_handler(exc: Exception, context: dict) -> Response:
    # Let DRF handle known API exceptions first
    response = exception_handler(exc, context)

    if response is not None:
        # Reshape DRF's default response into our standard envelope
        original_data = response.data
        response.data = {
            "error": True,
            "status_code": response.status_code,
            "detail": original_data.get("detail", original_data)
            if isinstance(original_data, dict)
            else original_data,
        }
        return response

    # Unknown/unhandled exception — return 500, never expose internals
    logger.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
    )
    return Response(
        {
            "error": True,
            "status_code": 500,
            "detail": "An internal server error occurred.",
        },
        status=500,
    )
