"""
Pydantic v2 schemas for tender extraction output.
These are the single source of truth for what a valid extracted tender looks like.
"""
from __future__ import annotations

from datetime import date
from typing import Any, List, Optional

from pydantic import BaseModel, field_validator, model_validator


class BudgetSchema(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None

    model_config = {"extra": "ignore", "coerce_numbers_to_str": False}

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount(cls, v: Any) -> Optional[float]:
        if v is None or v == "" or v == "N/A":
            return None
        try:
            # Strip common currency symbols / commas
            if isinstance(v, str):
                cleaned = v.replace(",", "").replace(" ", "")
                for sym in ["$", "€", "£", "﷼", "EGP", "USD", "EUR", "SAR"]:
                    cleaned = cleaned.replace(sym, "")
                return float(cleaned)
            return float(v)
        except (ValueError, TypeError):
            return None

    @field_validator("currency", mode="before")
    @classmethod
    def coerce_currency(cls, v: Any) -> Optional[str]:
        if not v or v in ("N/A", "null", "none"):
            return None
        return str(v).strip().upper()


class ContactSchema(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    model_config = {"extra": "ignore"}

    @field_validator("*", mode="before")
    @classmethod
    def empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() in ("", "N/A", "null", "none", "None"):
            return None
        return v


class TenderSchema(BaseModel):
    title: Optional[str] = None
    issuer: Optional[str] = None
    reference_number: Optional[str] = None
    publication_date: Optional[date] = None
    submission_deadline: Optional[date] = None
    budget: BudgetSchema = BudgetSchema()
    scope_of_work: Optional[str] = None
    key_requirements: List[str] = []
    eligibility_criteria: List[str] = []
    evaluation_criteria: List[str] = []
    deliverables: List[str] = []
    contact: ContactSchema = ContactSchema()

    model_config = {"extra": "ignore"}

    @field_validator(
        "title", "issuer", "reference_number", "scope_of_work", mode="before"
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip() in ("", "N/A", "null", "none", "None"):
            return None
        return v

    @field_validator(
        "key_requirements",
        "eligibility_criteria",
        "evaluation_criteria",
        "deliverables",
        mode="before",
    )
    @classmethod
    def ensure_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, list):
            return [str(item).strip() for item in v if item]
        return []

    @field_validator("publication_date", "submission_deadline", mode="before")
    @classmethod
    def parse_date(cls, v: Any) -> Optional[date]:
        if not v or v in ("N/A", "null", "none", "None", ""):
            return None
        if isinstance(v, date):
            return v
        from dateutil import parser as dateparser

        try:
            return dateparser.parse(str(v), dayfirst=True).date()
        except Exception:
            return None

    @field_validator("budget", mode="before")
    @classmethod
    def coerce_budget(cls, v: Any) -> Any:
        if v is None:
            return BudgetSchema()
        if isinstance(v, dict):
            return v
        return BudgetSchema()

    @field_validator("contact", mode="before")
    @classmethod
    def coerce_contact(cls, v: Any) -> Any:
        if v is None:
            return ContactSchema()
        if isinstance(v, dict):
            return v
        return ContactSchema()

    @model_validator(mode="after")
    def validate_dates(self) -> "TenderSchema":
        """Warn if deadline is before publication date — don't reject, just nullify deadline."""
        if (
            self.publication_date
            and self.submission_deadline
            and self.submission_deadline < self.publication_date
        ):
            self.submission_deadline = None
        return self

    def to_response_dict(self) -> dict:
        return {
            "title": self.title,
            "issuer": self.issuer,
            "reference_number": self.reference_number,
            "publication_date": self.publication_date.isoformat()
            if self.publication_date
            else None,
            "submission_deadline": self.submission_deadline.isoformat()
            if self.submission_deadline
            else None,
            "budget": {
                "amount": self.budget.amount,
                "currency": self.budget.currency,
            },
            "scope_of_work": self.scope_of_work,
            "key_requirements": self.key_requirements,
            "eligibility_criteria": self.eligibility_criteria,
            "evaluation_criteria": self.evaluation_criteria,
            "deliverables": self.deliverables,
            "contact": {
                "name": self.contact.name,
                "email": self.contact.email,
                "phone": self.contact.phone,
            },
        }

    @classmethod
    def empty(cls) -> "TenderSchema":
        """Return a fully null/empty schema for graceful failure responses."""
        return cls()
