"""Deterministic risk scoring logic. No LLM calls -- pure programmatic computation."""

from __future__ import annotations

from contract_af.models import (
    AdversaryResult,
    CombinationRisk,
    Finding,
    Severity,
)

SEVERITY_WEIGHTS: dict[Severity, float] = {
    Severity.CRITICAL: 10.0,
    Severity.HIGH: 7.0,
    Severity.MEDIUM: 4.0,
    Severity.LOW: 2.0,
    Severity.INFO: 0.5,
}

# Known unenforceability patterns by jurisdiction
UNENFORCEABLE_PATTERNS: dict[str, list[str]] = {
    "california": ["non_compete"],
    "north_dakota": ["non_compete"],
    "oklahoma": ["non_compete"],
}


def compute_risk_score(
    finding: Finding,
    adversary_result: AdversaryResult | None = None,
    combination_risks: list[CombinationRisk] | None = None,
    jurisdiction: str = "",
) -> float:
    """Compute composite risk score for a finding using deterministic rules."""
    score = SEVERITY_WEIGHTS.get(finding.severity, 4.0)

    # Combination risk multiplier
    if combination_risks:
        for cr in combination_risks:
            if finding.clause_ref in cr.clause_refs:
                score *= 1.5
                break

    # Exploitability multiplier
    if adversary_result:
        exploited = any(
            e.finding_id == finding.id
            for e in adversary_result.exploitation_scenarios
        )
        if exploited:
            score *= 1.3

    # Jurisdiction enforceability discount
    if not is_enforceable(finding, jurisdiction):
        score *= 0.3

    return round(score, 2)


def is_enforceable(finding: Finding, jurisdiction: str) -> bool:
    """Check if a finding's category is enforceable in the given jurisdiction."""
    jurisdiction_lower = jurisdiction.lower()
    for region, categories in UNENFORCEABLE_PATTERNS.items():
        if region in jurisdiction_lower and finding.category in categories:
            return False
    return True
