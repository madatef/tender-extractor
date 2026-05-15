"""
Factory that builds provider instances from settings.
"""
from __future__ import annotations

from django.conf import settings

from apps.tenders.llm.providers.base import BaseLLMProvider
from apps.tenders.llm.providers.openai_provider import OpenAIProvider


def build_provider(provider_key: str) -> BaseLLMProvider:
    """
    Build and return a provider instance for the given settings key.
    e.g. provider_key='openai_mini' -> OpenAIProvider(model='gpt-4o-mini')
    """
    model_name = settings.LLM_PROVIDER_MODELS.get(provider_key)
    if not model_name:
        raise ValueError(f"Unknown provider key: {provider_key!r}. "
                         f"Available: {list(settings.LLM_PROVIDER_MODELS.keys())}")
    return OpenAIProvider(model_name=model_name, provider_name=provider_key)
