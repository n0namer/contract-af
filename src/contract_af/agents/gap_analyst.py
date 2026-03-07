"""Gap analyst agent.

A .harness() that verifies missing clauses are truly absent from the
contract, rather than simply present under a different name or buried
in an unexpected section.
"""

from __future__ import annotations

from contract_af.models import AnatomyResult, GapResult, IntakeResult

# Expected clauses by contract type
EXPECTED_CLAUSES: dict[str, list[str]] = {
    "saas_agreement": [
        "definitions",
        "grant_of_license",
        "fees_payment",
        "data_protection",
        "intellectual_property",
        "confidentiality",
        "warranties",
        "limitation_of_liability",
        "indemnification",
        "term_termination",
        "governing_law",
        "dispute_resolution",
    ],
    "employment": [
        "definitions",
        "position_duties",
        "compensation",
        "benefits",
        "intellectual_property",
        "confidentiality",
        "non_compete",
        "non_solicitation",
        "term_termination",
        "severance",
        "governing_law",
    ],
    "nda": [
        "definitions",
        "confidential_information",
        "obligations",
        "exclusions",
        "term",
        "return_of_materials",
        "remedies",
        "governing_law",
    ],
}

CLAUSE_ALIASES: dict[str, list[str]] = {
    "intellectual_property": [
        "ip",
        "proprietary rights",
        "ownership",
        "work product",
    ],
    "limitation_of_liability": [
        "liability cap",
        "damages limitation",
        "liability",
    ],
    "fees_payment": [
        "compensation",
        "pricing",
        "fees",
        "payment terms",
    ],
    "term_termination": [
        "term",
        "termination",
        "duration",
    ],
    "data_protection": [
        "data privacy",
        "gdpr",
        "data security",
        "customer data",
    ],
    "dispute_resolution": [
        "arbitration",
        "mediation",
        "disputes",
    ],
    "non_compete": [
        "restrictive covenant",
        "competition",
    ],
    "non_solicitation": [
        "solicitation",
        "hiring restriction",
    ],
}


async def analyze_gaps(
    app,
    intake: IntakeResult,
    anatomy: AnatomyResult,
    found_clause_types: list[str],
    contract_text: str,
) -> GapResult:
    """Check for missing clauses, verifying absence by reading the contract.

    For each expected clause type that is not in *found_clause_types*,
    the function first checks section-title aliases locally. If no alias
    matches, it dispatches a harness to search the full contract text and
    confirm the clause is genuinely absent.
    """
    contract_type = intake.contract_type.lower().replace(" ", "_")
    expected = EXPECTED_CLAUSES.get(contract_type, EXPECTED_CLAUSES["saas_agreement"])

    found_lower = {c.lower() for c in found_clause_types}
    section_titles = {s.title.lower() for s in anatomy.sections}

    missing: list[str] = []
    verified_absent: list[str] = []
    found_elsewhere: list[dict[str, str]] = []

    for clause_type in expected:
        if clause_type in found_lower:
            continue

        # Check aliases in section titles
        aliases = CLAUSE_ALIASES.get(clause_type, [])
        found_under_alias = _match_alias(aliases, section_titles)

        if found_under_alias:
            found_elsewhere.append(
                {
                    "expected": clause_type,
                    "actual_section": found_under_alias,
                }
            )
            continue

        # Ask harness to verify absence by reading contract
        verification = await app.call(
            "contract-af.gap_analyst",
            clause_type=clause_type,
            aliases=aliases,
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


def _match_alias(aliases: list[str], section_titles: set[str]) -> str | None:
    """Return the first section title that matches any alias, or None."""
    for alias in aliases:
        for title in section_titles:
            if alias in title:
                return title
    return None
