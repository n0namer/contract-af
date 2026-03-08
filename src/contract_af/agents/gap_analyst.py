"""Gap analyst agent — AI-driven missing clause detection.

Asks the AI what clauses are expected for the contract type, then verifies
each missing clause by reading the contract (no hardcoded expected-clause
tables or alias dictionaries).
"""

from __future__ import annotations

import json as _json

from typing import Any

from pydantic import BaseModel, Field

from contract_af.models import AnatomyResult, GapResult, IntakeResult

MAX_GAP_VERIFICATIONS = 10


class _ExpectedClauses(BaseModel):
    expected: list[str] = Field(default_factory=list)


_EXPECTED_CLAUSES_PROMPT = (
    "You are a legal contract completeness expert. Given the contract type, "
    "jurisdiction, and document structure, determine what clause types SHOULD "
    "be present in this contract.\n\n"
    "Return a list of expected clause type slugs (e.g. 'intellectual_property', "
    "'limitation_of_liability', 'indemnification', 'term_termination', "
    "'confidentiality', 'data_protection', 'non_compete', etc.).\n\n"
    "Be thorough — include ALL standard clauses for this contract type and "
    "jurisdiction. Include both universal clauses (definitions, governing_law) "
    "and type-specific ones."
)


async def analyze_gaps(
    app: Any,
    intake: IntakeResult,
    anatomy: AnatomyResult,
    found_clause_types: list[str],
    contract_text: str,
) -> GapResult:
    """Check for missing clauses using AI to determine expectations and verify absence."""
    expected_result: _ExpectedClauses = await app.ai(
        system=_EXPECTED_CLAUSES_PROMPT,
        user=_json.dumps(
            {
                "contract_type": intake.contract_type,
                "jurisdiction": intake.jurisdiction,
                "governing_law": intake.governing_law,
                "complexity": intake.complexity,
                "section_titles": [s.title for s in anatomy.sections],
            },
            default=str,
        ),
        schema=_ExpectedClauses,
    )

    found_lower = {c.lower() for c in found_clause_types}
    potentially_missing = [
        clause for clause in expected_result.expected if clause.lower() not in found_lower
    ][:MAX_GAP_VERIFICATIONS]

    missing: list[str] = []
    verified_absent: list[str] = []
    found_elsewhere: list[dict[str, str]] = []

    for clause_type in potentially_missing:
        verification = await app.call(
            "contract-af.gap_analyst",
            clause_type=clause_type,
            aliases=[],
            contract_text=contract_text,
            existing_sections=[s.title for s in anatomy.sections],
        )

        if isinstance(verification, dict):
            if verification.get("found"):
                found_elsewhere.append(
                    {
                        "expected": clause_type,
                        "actual_section": verification.get("found_in", "unknown"),
                    }
                )
            else:
                verified_absent.append(clause_type)
                missing.append(clause_type)
        else:
            missing.append(clause_type)
            verified_absent.append(clause_type)

    return GapResult(
        missing_clauses=missing,
        verified_absent=verified_absent,
        found_elsewhere=found_elsewhere,
    )
