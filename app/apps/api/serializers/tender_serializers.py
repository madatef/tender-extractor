"""
Request/response serializers for the tender extractor API.
No business logic here — only I/O validation and shape.
"""
import uuid

from rest_framework import serializers


class TenderExtractionRequestSerializer(serializers.Serializer):
    request_id = serializers.CharField(
        max_length=128,
        required=False,
        help_text="Optional client-supplied correlation ID. Auto-generated if omitted.",
    )
    text = serializers.CharField(
        min_length=10,
        max_length=50_000,
        help_text="Full tender document text to extract information from.",
    )
    output_language = serializers.ChoiceField(
        choices=["Arabic", "English"],
        default="Arabic",
        help_text="Language for extracted text values. Defaults to Arabic.",
    )

    def validate_request_id(self, value: str) -> str:
        return value.strip() or str(uuid.uuid4())

    def validate(self, attrs):
        if "request_id" not in attrs or not attrs.get("request_id"):
            attrs["request_id"] = str(uuid.uuid4())
        return attrs


class BudgetResponseSerializer(serializers.Serializer):
    amount = serializers.FloatField(allow_null=True)
    currency = serializers.CharField(allow_null=True)


class ContactResponseSerializer(serializers.Serializer):
    name = serializers.CharField(allow_null=True)
    email = serializers.CharField(allow_null=True)
    phone = serializers.CharField(allow_null=True)


class TenderResponseSerializer(serializers.Serializer):
    title = serializers.CharField(allow_null=True)
    issuer = serializers.CharField(allow_null=True)
    reference_number = serializers.CharField(allow_null=True)
    publication_date = serializers.DateField(allow_null=True)
    submission_deadline = serializers.DateField(allow_null=True)
    budget = BudgetResponseSerializer()
    scope_of_work = serializers.CharField(allow_null=True)
    key_requirements = serializers.ListField(child=serializers.CharField())
    eligibility_criteria = serializers.ListField(child=serializers.CharField())
    evaluation_criteria = serializers.ListField(child=serializers.CharField())
    deliverables = serializers.ListField(child=serializers.CharField())
    contact = ContactResponseSerializer()


class TenderExtractionResponseSerializer(serializers.Serializer):
    request_id = serializers.CharField()
    tender = TenderResponseSerializer()
    meta = serializers.DictField()
