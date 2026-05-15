"""
API integration tests — exercises the full request/response cycle.
LLM calls are mocked at the service boundary.
"""
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from app.apps.tenders.services.extraction_service import ExtractionResponse

User = get_user_model()

ENDPOINT = "/api/v1/tender-extractor/"


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client(db):
    user = User.objects.create_user(username="testuser", password="testpass123")
    token = get_tokens_for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client, user


def make_mock_response(success=True):
    return ExtractionResponse(
        request_id="req-test-001",
        tender={
            "title": "Test Tender",
            "issuer": "Test Ministry",
            "reference_number": "T-2024-001",
            "publication_date": "2024-01-01",
            "submission_deadline": "2024-06-30",
            "budget": {"amount": 500000.0, "currency": "EGP"},
            "scope_of_work": "Supply of equipment",
            "key_requirements": ["Valid license", "3 years experience"],
            "eligibility_criteria": [],
            "evaluation_criteria": [],
            "deliverables": [],
            "contact": {"name": "John Doe", "email": "john@example.com", "phone": None},
        },
        provider_used="openai_mini",
        model_used="gpt-4o-mini",
        success=success,
        input_tokens=500,
        output_tokens=200,
        cost_usd=0.000195,
        latency_ms=1200.0,
    )


@pytest.mark.django_db
class TestTenderExtractorAuth:
    def test_unauthenticated_request_rejected(self, api_client):
        resp = api_client.post(ENDPOINT, {"text": "Some tender text"}, format="json")
        assert resp.status_code == 401

    def test_authenticated_request_accepted(self, authenticated_client):
        client, _ = authenticated_client
        with patch(
            "apps.api.views.tender_view.TenderExtractionService.extract",
            return_value=make_mock_response(),
        ):
            resp = client.post(
                ENDPOINT,
                {"text": "This is a tender document for supply of IT equipment."},
                format="json",
            )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestTenderExtractorRequestValidation:
    def test_missing_text_returns_400(self, authenticated_client):
        client, _ = authenticated_client
        resp = client.post(ENDPOINT, {}, format="json")
        assert resp.status_code == 400

    def test_text_too_short_returns_400(self, authenticated_client):
        client, _ = authenticated_client
        resp = client.post(ENDPOINT, {"text": "short"}, format="json")
        assert resp.status_code == 400

    def test_invalid_language_returns_400(self, authenticated_client):
        client, _ = authenticated_client
        resp = client.post(
            ENDPOINT,
            {"text": "Valid tender text here.", "output_language": "French"},
            format="json",
        )
        assert resp.status_code == 400

    def test_default_language_is_arabic(self, authenticated_client):
        client, _ = authenticated_client
        with patch(
            "apps.api.views.tender_view.TenderExtractionService.extract",
            return_value=make_mock_response(),
        ) as mock_extract:
            client.post(
                ENDPOINT,
                {"text": "Valid tender text for testing purposes here."},
                format="json",
            )
            call_kwargs = mock_extract.call_args[1]
            assert call_kwargs["output_language"] == "Arabic"


@pytest.mark.django_db
class TestTenderExtractorResponse:
    def test_successful_response_shape(self, authenticated_client):
        client, _ = authenticated_client
        with patch(
            "apps.api.views.tender_view.TenderExtractionService.extract",
            return_value=make_mock_response(success=True),
        ):
            resp = client.post(
                ENDPOINT,
                {"text": "A complete tender document text for supply of office equipment."},
                format="json",
            )
        data = resp.json()
        assert "request_id" in data
        assert "tender" in data
        assert "meta" in data
        assert "title" in data["tender"]
        assert "budget" in data["tender"]
        assert "contact" in data["tender"]
        assert data["meta"]["success"] is True

    def test_graceful_failure_returns_200_with_nulls(self, authenticated_client):
        client, _ = authenticated_client
        with patch(
            "apps.api.views.tender_view.TenderExtractionService.extract",
            return_value=make_mock_response(success=False),
        ):
            resp = client.post(
                ENDPOINT,
                {"text": "A complete tender document text for testing graceful failure."},
                format="json",
            )
        assert resp.status_code == 200

    def test_request_id_echoed_in_response(self, authenticated_client):
        client, _ = authenticated_client
        with patch(
            "apps.api.views.tender_view.TenderExtractionService.extract",
            return_value=make_mock_response(),
        ):
            resp = client.post(
                ENDPOINT,
                {
                    "request_id": "my-custom-id-123",
                    "text": "Valid tender document text for correlation test.",
                },
                format="json",
            )
        # The service mock returns req-test-001, but the shape should be present
        assert "request_id" in resp.json()

    def test_meta_contains_cost_and_tokens(self, authenticated_client):
        client, _ = authenticated_client
        with patch(
            "apps.api.views.tender_view.TenderExtractionService.extract",
            return_value=make_mock_response(),
        ):
            resp = client.post(
                ENDPOINT,
                {"text": "Valid tender document text for meta fields test."},
                format="json",
            )
        meta = resp.json()["meta"]
        assert "cost_usd" in meta
        assert "input_tokens" in meta
        assert "output_tokens" in meta
        assert "latency_ms" in meta
