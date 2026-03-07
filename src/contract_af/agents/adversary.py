"""Adversary reviewer agent.

A .harness() that re-reads actual clause text from the opposing party's
perspective, consuming findings from an asyncio.Queue as they arrive
from upstream analysts (streaming pipeline pattern).
"""

from __future__ import annotations

import asyncio

from contract_af.models import (
    AdversaryResult,
    AnatomyResult,
    Exploitation,
    FalsePositive,
    Finding,
    HiddenTrap,
    IntakeResult,
    Severity,
)

MAX_SUB_AGENTS = 2
SENTINEL = object()


async def review_as_adversary(
    app,
    findings_queue: asyncio.Queue,
    intake: IntakeResult,
    anatomy: AnatomyResult,
    contract_text: str,
) -> AdversaryResult:
    """Review findings from the opposing party's perspective.

    Consumes findings as they arrive via *findings_queue* (streaming
    pipeline). For each finding the harness re-reads the clause text and
    checks whether it is a false positive, an exploitation opportunity,
    or hides a trap.  When multiple findings reference a survival clause,
    a sub-agent is spawned to analyse combined post-termination impact.
    """
    false_positives: list[FalsePositive] = []
    hidden_traps: list[HiddenTrap] = []
    exploitation_scenarios: list[Exploitation] = []
    uncovered_sections: list[str] = []
    sub_agents_used = 0
    accumulated_findings: list[Finding] = []

    while True:
        try:
            item = await asyncio.wait_for(findings_queue.get(), timeout=60.0)
        except asyncio.TimeoutError:
            break
        if item is SENTINEL:
            break

        accumulated_findings.append(item)

        # For each finding, ask harness to review from adversary perspective
        review = await app.call(
            "contract-af.adversary_reviewer",
            input={
                "finding": {
                    "id": item.id,
                    "clause_ref": item.clause_ref,
                    "description": item.description,
                    "severity": item.severity.value,
                    "clause_text": item.clause_text,
                },
                "contract_type": intake.contract_type,
                "opposing_role": _get_opposing_role(intake),
                "contract_text": contract_text,
            },
        )

        if not isinstance(review, dict):
            continue

        # Check for false positive
        if review.get("is_false_positive"):
            false_positives.append(
                FalsePositive(
                    finding_id=item.id,
                    reason=review.get("false_positive_reason", ""),
                    evidence=review.get("evidence", ""),
                )
            )

        # Check for exploitation scenario
        if review.get("exploitation_scenario"):
            exploitation_scenarios.append(
                Exploitation(
                    finding_id=item.id,
                    scenario=review["exploitation_scenario"],
                    impact=review.get("impact", ""),
                )
            )

        # Check for hidden traps
        for trap in review.get("hidden_traps", []):
            hidden_traps.append(
                HiddenTrap(
                    clause_refs=trap.get("clause_refs", [item.clause_ref]),
                    description=trap.get("description", ""),
                    exploitation_scenario=trap.get("exploitation_scenario", ""),
                    severity=Severity(trap.get("severity", "high")),
                )
            )

        # Track uncovered sections with potential traps
        uncovered_sections.extend(review.get("uncovered_sections_with_traps", []))

    # Pattern detection: if multiple findings reference same survival clause,
    # spawn sub-agent to analyze combined survival impact
    survival_refs = _find_survival_patterns(accumulated_findings, anatomy)
    if survival_refs and sub_agents_used < MAX_SUB_AGENTS:
        sub_agents_used += 1
        trap_result = await app.call(
            "contract-af.adversary_reviewer",
            input={
                "prompt": (
                    f"Multiple clauses survive termination: {survival_refs}. "
                    f"Analyze combined post-termination obligations for {intake.your_role}."
                ),
                "survival_sections": survival_refs,
                "contract_text": contract_text,
            },
        )
        if isinstance(trap_result, dict) and trap_result.get("hidden_traps"):
            for trap in trap_result["hidden_traps"]:
                hidden_traps.append(
                    HiddenTrap(
                        clause_refs=trap.get("clause_refs", []),
                        description=trap.get("description", ""),
                        exploitation_scenario=trap.get("exploitation_scenario", ""),
                        severity=Severity(trap.get("severity", "high")),
                    )
                )

    return AdversaryResult(
        false_positives=false_positives,
        hidden_traps=hidden_traps,
        exploitation_scenarios=exploitation_scenarios,
        uncovered_sections_with_traps=list(set(uncovered_sections)),
    )


def _get_opposing_role(intake: IntakeResult) -> str:
    """Determine the opposing party's role from intake metadata."""
    roles = {p.role for p in intake.parties}
    your = intake.your_role.lower()
    for role in roles:
        if role.lower() != your:
            return role
    return "opposing party"


def _find_survival_patterns(
    findings: list[Finding],
    anatomy: AnatomyResult,
) -> list[str]:
    """Find findings whose clauses are referenced in a survival section."""
    survival_sections: set[str] = set()
    for cr in anatomy.cross_references:
        if "surviv" in cr.relationship_type.lower() or "14" in cr.from_section:
            survival_sections.add(cr.to_section)

    matching = [f.clause_ref for f in findings if f.clause_ref in survival_sections]
    return matching if len(matching) >= 2 else []
