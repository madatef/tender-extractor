"""
OpenAI provider — wraps the OpenAI chat completions API.
Used for both primary (gpt-4o-mini) and fallback (gpt-5.2) calls.
"""
from __future__ import annotations

import time

import structlog
from django.conf import settings
from openai import OpenAI, OpenAIError

from apps.tenders.domain.llm_result import LLMResult
from apps.tenders.llm.providers.base import BaseLLMProvider

logger = structlog.get_logger(__name__)


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, model_name: str, provider_name: str = "openai"):
        self.model_name = model_name
        self.provider_name = provider_name
        self._client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )

    def extract(self, system_prompt: str, user_prompt: str) -> LLMResult:
        start = time.monotonic()
        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            latency_ms = (time.monotonic() - start) * 1000
            raw_text = response.choices[0].message.content or ""
            usage = response.usage

            logger.info(
                "llm_provider_success",
                provider=self.provider_name,
                model=self.model_name,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                latency_ms=round(latency_ms, 2),
            )

            return LLMResult(
                raw_text=raw_text,
                provider=self.provider_name,
                model=self.model_name,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                latency_ms=round(latency_ms, 2),
                success=True,
            )

        except OpenAIError as exc:
            latency_ms = (time.monotonic() - start) * 1000
            error_msg = str(exc)
            logger.warning(
                "llm_provider_error",
                provider=self.provider_name,
                model=self.model_name,
                error=error_msg,
                latency_ms=round(latency_ms, 2),
            )
            return LLMResult.failure(
                provider=self.provider_name,
                model=self.model_name,
                error=error_msg,
            )

        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000
            error_msg = f"Unexpected provider error: {type(exc).__name__}: {exc}"
            logger.error(
                "llm_provider_unexpected_error",
                provider=self.provider_name,
                model=self.model_name,
                error=error_msg,
                latency_ms=round(latency_ms, 2),
            )
            return LLMResult.failure(
                provider=self.provider_name,
                model=self.model_name,
                error=error_msg,
            )
