"""
PromptBuilder — constructs the system and user prompts for tender extraction.
Keeps prompt logic completely separate from provider/orchestrator logic.
"""
from __future__ import annotations

from typing import Literal

OutputLanguage = Literal["Arabic", "English"]

OUTPUT_SCHEMA = """{
  "title": "string or null",
  "issuer": "string or null",
  "reference_number": "string or null",
  "publication_date": "YYYY-MM-DD or null",
  "submission_deadline": "YYYY-MM-DD or null",
  "budget": {
    "amount": "number or null",
    "currency": "string or null"
  },
  "scope_of_work": "string or null",
  "key_requirements": ["string", "..."],
  "eligibility_criteria": ["string", "..."],
  "evaluation_criteria": ["string", "..."],
  "deliverables": ["string", "..."],
  "contact": {
    "name": "string or null",
    "email": "string or null",
    "phone": "string or null"
  }
}"""

LANGUAGE_INSTRUCTIONS = {
    "Arabic": (
        "You MUST write every extracted text value in Arabic. "
        "Translate any non-Arabic field values into Arabic. "
        "Dates must remain in ISO 8601 format (YYYY-MM-DD). "
        "Numbers must remain as numeric values. "
        "JSON keys must remain in English exactly as shown."
    ),
    "English": (
        "You MUST write every extracted text value in English. "
        "Translate any non-English field values into English. "
        "Dates must remain in ISO 8601 format (YYYY-MM-DD). "
        "Numbers must remain as numeric values. "
        "JSON keys must remain in English exactly as shown."
    ),
}


class PromptBuilder:
    def build_system_prompt(self, output_language: OutputLanguage = "Arabic") -> str:
        lang_instruction = LANGUAGE_INSTRUCTIONS[output_language]

        return f"""You are an expert tender document analysis engine.

## TASK DEFINITION
Extract structured information from the provided tender document text.
Return ONLY a valid JSON object. No markdown, no code fences, no commentary, no preamble.

## OUTPUT LANGUAGE
{lang_instruction}

## OUTPUT SCHEMA
Return exactly this JSON structure:
{OUTPUT_SCHEMA}

## EXTRACTION GUIDELINES
- Extract all fields present in the document.
- Use null for fields that are genuinely absent or cannot be determined.
- For dates, normalize to ISO 8601 format: YYYY-MM-DD.
- For budget amounts, extract numeric value only (no currency symbols in the amount field).
- For lists (key_requirements, eligibility_criteria, evaluation_criteria, deliverables), return an array of concise strings. Return [] if none found.
- For reference_number, extract any tender ID, procurement number, or reference code.
- For contact, extract the primary contact point mentioned for submissions or queries.

## INVALID INPUT HANDLING
- If the input is empty, nonsensical, or clearly not a tender document, return the schema with all fields set to null and empty arrays.
- Do not invent information not present in the text.

## IMPORTANT NOTES
- Your entire response must be parseable by JSON.parse() with zero modifications.
- Do not include trailing commas.
- Do not include comments inside the JSON.
- String values must be properly escaped.
"""

    def build_user_prompt(self, tender_text: str) -> str:
        return f"""Tender document text:

---
{tender_text}
---

Extract the structured information now. Return only the JSON object."""
