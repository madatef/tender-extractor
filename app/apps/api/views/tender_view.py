"""
TenderExtractorView — thin DRF view.

Responsibilities:
  1. Validate request via serializer
  2. Delegate to TenderExtractionService
  3. Return structured response

No LLM logic. No business logic. No fallback logic.
"""
from __future__ import annotations

import structlog
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.serializers.tender_serializers import (
    TenderExtractionRequestSerializer,
    TenderExtractionResponseSerializer,
)
from apps.tenders.services.extraction_service import TenderExtractionService

logger = structlog.get_logger(__name__)


class TenderExtractorView(APIView):
    """
    Extract structured information from a tender document.

    Requires JWT Bearer authentication.
    Primary model: gpt-4o-mini. Fallback: gpt-5.2.
    """

    @extend_schema(
        request=TenderExtractionRequestSerializer,
        responses={200: TenderExtractionResponseSerializer},
        summary="Extract tender information",
        description=(
            "Accepts raw tender document text and returns a structured JSON payload "
            "with all extractable fields. Uses gpt-4o-mini with automatic fallback to "
            "gpt-5.2. Always returns HTTP 200 — even on LLM failure, returning a "
            "null-filled payload."
        ),
        examples=[
            OpenApiExample(
                "Arabic extraction",
                value={
                    "request_id": "req-001",
                    "text": "مناقصة رقم 2024/55 - توريد معدات مكتبية ...",
                    "output_language": "Arabic",
                },
                request_only=True,
            ),
            OpenApiExample(
                "English extraction",
                value={
                    "request_id": "req-002",
                    "text": "Tender Notice: Supply of IT Equipment. Deadline: 2024-06-30.",
                    "output_language": "English",
                },
                request_only=True,
            ),
        ],
        tags=["Tender Extraction"],
    )
    def post(self, request: Request) -> Response:
        serializer = TenderExtractionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        request_id: str = data["request_id"]
        text: str = data["text"]
        output_language: str = data["output_language"]

        log = logger.bind(
            request_id=request_id,
            user_id=request.user.id if request.user.is_authenticated else None,
        )
        log.info("tender_extractor_view_invoked", output_language=output_language)

        service = TenderExtractionService()
        result = service.extract(
            text=text,
            output_language=output_language,
            request_id=request_id,
            user_id=request.user.id if request.user.is_authenticated else None,
        )

        response_payload = {
            "request_id": result.request_id,
            "tender": result.tender,
            "meta": {
                "success": result.success,
                "provider_used": result.provider_used,
                "model_used": result.model_used,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cost_usd": result.cost_usd,
                "latency_ms": result.latency_ms,
            },
        }

        return Response(response_payload, status=status.HTTP_200_OK)
