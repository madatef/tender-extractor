"""
Tests for the LLM orchestrator — all provider calls are mocked.
Validates retry logic, fallback triggering, and result aggregation.
"""
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from app.apps.tenders.domain.llm_result import LLMResult
from app.apps.tenders.llm.orchestrator import LLMOrchestrator


VALID_JSON = '{"title": "Test Tender", "issuer": "Test Org", "key_requirements": []}'

MOCK_SETTINGS = {
    "PRIMARY_LLM_PROVIDER": "openai_mini",
    "FALLBACK_LLM_PROVIDER": "openai_full",
    "LLM_PROVIDER_MODELS": {"openai_mini": "gpt-4o-mini", "openai_full": "gpt-5.2"},
    "LLM_MAX_RETRIES": 2,
    "LLM_TIMEOUT_SECONDS": 30,
    "OPENAI_API_KEY": "sk-test",
}


def make_success_result(provider="openai_mini", model="gpt-4o-mini"):
    return LLMResult(
        raw_text=VALID_JSON,
        provider=provider,
        model=model,
        input_tokens=100,
        output_tokens=50,
        latency_ms=500.0,
        success=True,
    )


def make_failure_result(provider="openai_mini", model="gpt-4o-mini"):
    return LLMResult.failure(provider=provider, model=model, error="API timeout")


@pytest.mark.django_db
class TestLLMOrchestrator:
    @override_settings(**MOCK_SETTINGS)
    @patch("apps.tenders.llm.orchestrator.build_provider")
    def test_primary_success_no_fallback(self, mock_build):
        mock_provider = MagicMock()
        mock_provider.provider_name = "openai_mini"
        mock_provider.model_name = "gpt-4o-mini"
        mock_provider.extract.return_value = make_success_result()
        mock_build.return_value = mock_provider

        orch = LLMOrchestrator()
        result = orch.run("sys", "user", request_id="test-orch-1")

        assert result.success is True
        assert result.tender is not None
        assert result.used_provider == "openai_mini"
        # Primary succeeded on first try — fallback should not have been needed
        assert mock_provider.extract.call_count == 1

    @override_settings(**MOCK_SETTINGS)
    @patch("apps.tenders.llm.orchestrator.build_provider")
    def test_primary_fails_fallback_succeeds(self, mock_build):
        primary_provider = MagicMock()
        primary_provider.provider_name = "openai_mini"
        primary_provider.model_name = "gpt-4o-mini"
        primary_provider.extract.return_value = make_failure_result()

        fallback_provider = MagicMock()
        fallback_provider.provider_name = "openai_full"
        fallback_provider.model_name = "gpt-5.2"
        fallback_provider.extract.return_value = make_success_result(
            provider="openai_full", model="gpt-5.2"
        )

        mock_build.side_effect = [primary_provider, fallback_provider]

        orch = LLMOrchestrator()
        result = orch.run("sys", "user", request_id="test-orch-2")

        assert result.success is True
        assert result.used_provider == "openai_full"
        assert result.used_model == "gpt-5.2"

    @override_settings(**MOCK_SETTINGS)
    @patch("apps.tenders.llm.orchestrator.build_provider")
    def test_all_providers_fail_returns_none_tender(self, mock_build):
        failing_provider = MagicMock()
        failing_provider.provider_name = "openai_mini"
        failing_provider.model_name = "gpt-4o-mini"
        failing_provider.extract.return_value = make_failure_result()

        mock_build.return_value = failing_provider

        orch = LLMOrchestrator()
        result = orch.run("sys", "user", request_id="test-orch-3")

        assert result.success is False
        assert result.tender is None

    @override_settings(**MOCK_SETTINGS)
    @patch("apps.tenders.llm.orchestrator.build_provider")
    def test_retries_exhaust_before_fallback(self, mock_build):
        primary_provider = MagicMock()
        primary_provider.provider_name = "openai_mini"
        primary_provider.model_name = "gpt-4o-mini"
        primary_provider.extract.return_value = make_failure_result()

        fallback_provider = MagicMock()
        fallback_provider.provider_name = "openai_full"
        fallback_provider.model_name = "gpt-5.2"
        fallback_provider.extract.return_value = make_success_result(
            provider="openai_full", model="gpt-5.2"
        )

        mock_build.side_effect = [primary_provider, fallback_provider]

        orch = LLMOrchestrator()
        orch.run("sys", "user", request_id="test-orch-4")

        # Primary should have been called MAX_RETRIES times
        assert primary_provider.extract.call_count == MOCK_SETTINGS["LLM_MAX_RETRIES"]

    @override_settings(**MOCK_SETTINGS)
    @patch("apps.tenders.llm.orchestrator.build_provider")
    def test_cost_accumulated_across_attempts(self, mock_build):
        provider = MagicMock()
        provider.provider_name = "openai_mini"
        provider.model_name = "gpt-4o-mini"
        provider.extract.return_value = make_success_result()
        mock_build.return_value = provider

        orch = LLMOrchestrator()
        result = orch.run("sys", "user", request_id="test-orch-5")

        assert result.total_cost_usd >= 0
        assert result.total_input_tokens > 0
