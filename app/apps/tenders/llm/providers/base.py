"""
Abstract base class for all LLM providers.
Every provider must return a normalized LLMResult.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from apps.tenders.domain.llm_result import LLMResult


class BaseLLMProvider(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def extract(self, system_prompt: str, user_prompt: str) -> LLMResult:
        """
        Execute the LLM call and return a normalized LLMResult.
        Must never raise — catch all exceptions and return LLMResult.failure().
        """
        ...
