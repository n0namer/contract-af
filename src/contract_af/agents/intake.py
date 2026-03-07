"""Phase 1: Intake classification with .ai() and .harness() fallback.

Uses .ai() on the first ~3000 chars for fast classification.
Falls back to a .harness() call when the quick pass lacks confidence,
finds no parties, or returns an unknown contract type.
"""

from __future__ import annotations

from typing import Any

from contract_af.models import IntakeResult, Party

INTAKE_PROMPT = """Classify this contract from the first 2-3 pages.
Extract: contract_type, parties (name, role, entity_type), your_role,
jurisdiction, governing_law, deal_structure (one-line summary), complexity.
Set confident=false if key metadata is unclear from these pages."""

FIRST_PAGES_CHAR_LIMIT = 3000


def _needs_fallback(intake: IntakeResult) -> bool:
    """Determine whether the .ai() result requires harness escalation."""
    return (
        not intake.confident
        or not intake.parties
        or intake.contract_type == "unknown"
    )


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

    intake: IntakeResult = await app.ai(
        prompt=INTAKE_PROMPT,
        input={"text": first_pages, "user_context": user_context},
        schema=IntakeResult,
    )

    if _needs_fallback(intake):
        harness_result = await app.call(
            "contract-af.intake_harness",
            input={
                "document": document_text,
                "partial_intake": intake.model_dump(),
                "user_context": user_context,
            },
        )
        # The harness may return a dict or an IntakeResult depending on
        # how the harness serialises its output.
        if isinstance(harness_result, dict):
            intake = IntakeResult(**harness_result)
        elif isinstance(harness_result, IntakeResult):
            intake = harness_result
        else:
            raise TypeError(
                f"Unexpected harness response type: {type(harness_result)}"
            )

    return intake
