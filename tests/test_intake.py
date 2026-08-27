"""Tests for Phase 1: Intake classifier (classify_contract)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, call

import pytest

from contract_af.agents.intake import FIRST_PAGES_CHAR_LIMIT, classify_contract
from contract_af.models import IntakeResult, Party


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_intake(
    *,
    confident: bool = True,
    contract_type: str = "saas_agreement",
    parties: list[Party] | None = None,
) -> IntakeResult:
    """Build an IntakeResult with sensible defaults."""
    if parties is None:
        parties = [
            Party(name="Acme Cloud Inc.", role="provider", entity_type="corporation"),
            Party(name="TechStart LLC", role="customer", entity_type="llc"),
        ]
    return IntakeResult(
        contract_type=contract_type,
        parties=parties,
        your_role="customer",
        jurisdiction="Delaware, USA",
        governing_law="Delaware",
        deal_structure="SaaS subscription for project management platform",
        complexity="standard",
        confident=confident,
    )


# ---------------------------------------------------------------------------
# Happy path — .ai() is confident, no fallback
# ---------------------------------------------------------------------------


async def test_happy_path_no_fallback(mock_app, sample_first_pages):
    """When .ai() returns confident=True with valid data, no harness fallback."""
    confident_result = _make_intake(confident=True)
    mock_app.ai.return_value = confident_result

    result = await classify_contract(mock_app, sample_first_pages)

    assert result == confident_result
    mock_app.ai.assert_awaited_once()
    mock_app.call.assert_not_awaited()


# ---------------------------------------------------------------------------
# Fallback triggers
# ---------------------------------------------------------------------------


async def test_fallback_on_confident_false(mock_app, sample_contract_text):
    """When .ai() returns confident=False, harness fallback is invoked."""
    low_confidence = _make_intake(confident=False)
    harness_return = _make_intake(confident=True)

    mock_app.ai.return_value = low_confidence
    mock_app.call.return_value = harness_return

    result = await classify_contract(mock_app, sample_contract_text)

    mock_app.call.assert_awaited_once()
    call_args = mock_app.call.call_args
    assert call_args[0][0] == "contract-af.intake_harness"
    assert result.confident is True


async def test_fallback_on_empty_parties(mock_app, sample_contract_text):
    """When .ai() returns an empty parties list, harness fallback is invoked."""
    empty_parties = _make_intake(parties=[])
    harness_return = _make_intake(confident=True)

    mock_app.ai.return_value = empty_parties
    mock_app.call.return_value = harness_return

    result = await classify_contract(mock_app, sample_contract_text)

    mock_app.call.assert_awaited_once()
    assert len(result.parties) > 0


async def test_fallback_on_unknown_type(mock_app, sample_contract_text):
    """When .ai() returns contract_type='unknown', harness fallback is invoked."""
    unknown_type = _make_intake(contract_type="unknown")
    harness_return = _make_intake(contract_type="saas_agreement")

    mock_app.ai.return_value = unknown_type
    mock_app.call.return_value = harness_return

    result = await classify_contract(mock_app, sample_contract_text)

    mock_app.call.assert_awaited_once()
    assert result.contract_type == "saas_agreement"


# ---------------------------------------------------------------------------
# Harness returns a dict (serialised output)
# ---------------------------------------------------------------------------


async def test_fallback_returns_dict(mock_app, sample_contract_text):
    """When harness returns a dict, it is correctly parsed to IntakeResult."""
    low_confidence = _make_intake(confident=False)
    harness_dict = _make_intake(confident=True).model_dump()

    mock_app.ai.return_value = low_confidence
    mock_app.call.return_value = harness_dict

    result = await classify_contract(mock_app, sample_contract_text)

    assert isinstance(result, IntakeResult)
    assert result.confident is True
    assert result.contract_type == "saas_agreement"


# ---------------------------------------------------------------------------
# Text truncation
# ---------------------------------------------------------------------------


async def test_uses_first_3000_chars(mock_app):
    """Verify .ai() receives at most FIRST_PAGES_CHAR_LIMIT characters."""
    long_text = "A" * 10_000
    confident_result = _make_intake(confident=True)
    mock_app.ai.return_value = confident_result

    await classify_contract(mock_app, long_text)

    ai_call_kwargs = mock_app.ai.call_args
    input_text = ai_call_kwargs.kwargs.get("input") or ai_call_kwargs[1].get("input")
    if input_text is None:
        # Positional args: prompt, input, schema
        input_text = ai_call_kwargs[0][1] if len(ai_call_kwargs[0]) > 1 else ai_call_kwargs.kwargs["input"]

    assert len(input_text["text"]) == FIRST_PAGES_CHAR_LIMIT
