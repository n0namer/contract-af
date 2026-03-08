"""Phase 1: Intake classification with .ai() and .harness() fallback.

Uses .ai() on the first ~3000 chars for fast classification.
Falls back to a .harness() call when the quick pass lacks confidence,
finds no parties, or returns an unknown contract type.
"""

from __future__ import annotations

from typing import Any

from contract_af.models import IntakeResult, Party

INTAKE_PROMPT = """You are a legal contract intake classifier. From the provided text
(typically the first 2-3 pages), extract structured metadata.

Required fields:
- contract_type: specific type (e.g. "master_services_agreement", "nda", "saas_agreement", "employment", "license")
- parties: each party's name, role (e.g. "provider", "customer"), and entity_type (e.g. "corporation", "llc")
- your_role: which party the user represents (infer from user_context)
- jurisdiction: governing jurisdiction
- governing_law: applicable law
- deal_structure: one-line summary of the deal
- complexity: "simple", "standard", or "complex"

Confidence rules:
- Set confident=true if you can identify the contract_type AND at least one party from the text.
  Most contracts clearly state these on the first page — title, preamble, or recitals.
- Set confident=false ONLY if the text is genuinely ambiguous — no identifiable contract type,
  no party names, or the text appears to be a fragment/exhibit without context.
- When in doubt, lean toward confident=true. A table of contents or section headers
  alone are sufficient to classify the contract type."""

FIRST_PAGES_CHAR_LIMIT = 3000


def _needs_fallback(intake: IntakeResult) -> bool:
    """Determine whether the .ai() result requires harness escalation."""
    return not intake.confident or not intake.parties or intake.contract_type == "unknown"


async def classify_contract(
    app: Any,
    document_text: str,
    user_context: str = "",
) -> IntakeResult:
    """Classify a contract document, escalating to harness when needed.

    Parameters
    ----------
    app:
        AgentField application instance exposing ``.ai()`` and ``.call()``.
    document_text:
        Full text of the contract document.
    user_context:
        Optional context from the user (e.g. "I am the customer").

    Returns
    -------
    IntakeResult
        Structured classification of the contract.
    """
    first_pages = document_text[:FIRST_PAGES_CHAR_LIMIT]

    import json as _json

    intake: IntakeResult = await app.ai(
        system=INTAKE_PROMPT,
        user=_json.dumps({"text": first_pages, "user_context": user_context}),
        schema=IntakeResult,
    )

    if _needs_fallback(intake):
        harness_result = await app.call(
            "contract-af.intake_harness",
            document=document_text,
            partial_intake=intake.model_dump(),
            user_context=user_context,
        )
        # The harness may return a dict or an IntakeResult depending on
        # how the harness serialises its output.
        if isinstance(harness_result, dict):
            intake = IntakeResult(**harness_result)
        elif isinstance(harness_result, IntakeResult):
            intake = harness_result
        else:
            raise TypeError(f"Unexpected harness response type: {type(harness_result)}")

    return intake
