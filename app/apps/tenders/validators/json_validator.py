"""
Multi-stage JSON validation pipeline.

Stage 1: Direct JSON parse
Stage 2: Strip markdown fences, attempt again
Stage 3: Extract first {...} block, attempt again
Stage 4: Pydantic normalization
"""
from __future__ import annotations

import json
import re
from typing import Optional, Tuple

import structlog
from pydantic import ValidationError

from apps.tenders.domain.schemas import TenderSchema

logger = structlog.get_logger(__name__)


class JSONValidationError(Exception):
    pass


class LLMJSONValidator:
    def validate(
        self, raw_text: str, request_id: str = ""
    ) -> Tuple[Optional[TenderSchema], Optional[str]]:
        """
        Returns (TenderSchema, None) on success or (None, error_message) on failure.
        Never raises.
        """
        parsed_dict = self._parse_json(raw_text, request_id)
        if parsed_dict is None:
            return None, "Could not parse JSON from LLM response"

        try:
            schema = TenderSchema.model_validate(parsed_dict)
            logger.debug(
                "json_validation_success",
                request_id=request_id,
            )
            return schema, None
        except ValidationError as exc:
            error_msg = f"Pydantic validation failed: {exc.error_count()} errors"
            logger.warning(
                "json_validation_pydantic_error",
                request_id=request_id,
                errors=exc.errors(),
            )
            return None, error_msg

    def _parse_json(self, raw_text: str, request_id: str) -> Optional[dict]:
        """Try progressively more lenient parsing strategies."""
        text = raw_text.strip()

        # Stage 1: direct parse
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # Stage 2: strip markdown code fences
        stripped = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        stripped = re.sub(r"\s*```$", "", stripped, flags=re.MULTILINE).strip()
        try:
            result = json.loads(stripped)
            if isinstance(result, dict):
                logger.debug("json_parse_recovered_from_fences", request_id=request_id)
                return result
        except json.JSONDecodeError:
            pass

        # Stage 3: extract first { ... } block
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, dict):
                    logger.debug(
                        "json_parse_recovered_from_extraction", request_id=request_id
                    )
                    return result
            except json.JSONDecodeError:
                pass

        logger.warning(
            "json_parse_all_strategies_failed",
            request_id=request_id,
            raw_preview=raw_text[:200],
        )
        return None
