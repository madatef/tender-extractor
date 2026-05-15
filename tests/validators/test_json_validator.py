"""
Tests for the JSON validator and Pydantic schema normalization.
These tests are fully offline — no LLM calls, no DB, no Redis.
"""
import pytest

from app.apps.tenders.validators.json_validator import LLMJSONValidator
from app.apps.tenders.domain.schemas import TenderSchema


class TestLLMJSONValidator:
    def setup_method(self):
        self.validator = LLMJSONValidator()

    def test_valid_json_parsed_correctly(self):
        raw = '{"title": "Supply of Goods", "issuer": "Ministry", "key_requirements": []}'
        schema, error = self.validator.validate(raw, request_id="test-1")
        assert error is None
        assert schema is not None
        assert schema.title == "Supply of Goods"

    def test_markdown_fences_stripped(self):
        raw = '```json\n{"title": "Test Tender"}\n```'
        schema, error = self.validator.validate(raw, request_id="test-2")
        assert error is None
        assert schema is not None
        assert schema.title == "Test Tender"

    def test_json_embedded_in_prose(self):
        raw = 'Here is the result: {"title": "Embedded Tender", "issuer": null}'
        schema, error = self.validator.validate(raw, request_id="test-3")
        assert error is None
        assert schema is not None

    def test_empty_string_returns_error(self):
        schema, error = self.validator.validate("", request_id="test-4")
        assert schema is None
        assert error is not None

    def test_garbage_input_returns_error(self):
        schema, error = self.validator.validate("not json at all!!!", request_id="test-5")
        assert schema is None
        assert error is not None

    def test_unknown_fields_ignored(self):
        raw = '{"title": "T", "unknown_field": "should_be_ignored", "key_requirements": []}'
        schema, error = self.validator.validate(raw, request_id="test-6")
        assert error is None
        assert schema is not None
        assert not hasattr(schema, "unknown_field")

    def test_missing_fields_default_correctly(self):
        raw = '{"title": "Minimal"}'
        schema, error = self.validator.validate(raw, request_id="test-7")
        assert error is None
        assert schema.key_requirements == []
        assert schema.eligibility_criteria == []
        assert schema.budget.amount is None


class TestTenderSchema:
    def test_date_normalization(self):
        data = {"publication_date": "30/06/2024", "submission_deadline": "2024-08-01"}
        schema = TenderSchema.model_validate(data)
        assert schema.publication_date is not None
        assert schema.publication_date.year == 2024

    def test_deadline_before_publication_nullified(self):
        data = {
            "publication_date": "2024-08-01",
            "submission_deadline": "2024-01-01",
        }
        schema = TenderSchema.model_validate(data)
        assert schema.submission_deadline is None

    def test_budget_amount_coercion(self):
        data = {"budget": {"amount": "1,500,000", "currency": "EGP"}}
        schema = TenderSchema.model_validate(data)
        assert schema.budget.amount == 1500000.0
        assert schema.budget.currency == "EGP"

    def test_na_strings_become_none(self):
        data = {"title": "N/A", "issuer": "null", "scope_of_work": ""}
        schema = TenderSchema.model_validate(data)
        assert schema.title is None
        assert schema.issuer is None
        assert schema.scope_of_work is None

    def test_list_coercion_from_string(self):
        data = {"key_requirements": "Single requirement"}
        schema = TenderSchema.model_validate(data)
        assert schema.key_requirements == ["Single requirement"]

    def test_empty_returns_all_nulls(self):
        schema = TenderSchema.empty()
        assert schema.title is None
        assert schema.key_requirements == []
        assert schema.budget.amount is None
        assert schema.contact.email is None

    def test_to_response_dict_structure(self):
        schema = TenderSchema.empty()
        d = schema.to_response_dict()
        assert "title" in d
        assert "budget" in d
        assert "contact" in d
        assert isinstance(d["key_requirements"], list)
