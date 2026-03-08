"""Adversary reviewer agent.

A .harness() that re-reads actual clause text from the opposing party's
perspective, consuming findings from an asyncio.Queue as they arrive
from upstream analysts (streaming pipeline pattern).
"""

from __future__ import annotations

import asyncio

from contract_af.models import (
    AdversaryResult,
    Exploitation,
    FalsePositive,
    Finding,
    HiddenTrap,
    IntakeResult,
    Severity,
)

MAX_SUB_AGENTS = 2
MAX_FINDINGS_REVIEWED = 15
_MAX_WIRE_CHARS = 30_000
SENTINEL = object()


def _truncate_for_wire(text: str, limit: int = _MAX_WIRE_CHARS) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n\n[... middle truncated for wire limit ...]\n\n" + text[-half:]


async def review_as_adversary(
    app,
    findings_queue: asyncio.Queue,
    intake: IntakeResult,
    contract_text: str,
) -> AdversaryResult:
    """Review findings from the opposing party's perspective.

    Consumes findings as they arrive via *findings_queue* (streaming
    pipeline). For each finding the harness re-reads the clause text and
    checks whether it is a false positive, an exploitation opportunity,
    or hides a trap.  When multiple findings reference a survival clause,
    a sub-agent is spawned to analyse combined post-termination impact.

    Hard cap: processes at most MAX_FINDINGS_REVIEWED findings individually
    to prevent runaway execution with large contracts.
    """
    false_positives: list[FalsePositive] = []
    hidden_traps: list[HiddenTrap] = []
    exploitation_scenarios: list[Exploitation] = []
    uncovered_sections: list[str] = []
    sub_agents_used = 0
    accumulated_findings: list[Finding] = []
    findings_reviewed = 0

    while True:
        try:
            item = await asyncio.wait_for(findings_queue.get(), timeout=60.0)
        except asyncio.TimeoutError:
            break
        if item is SENTINEL:
            break

        accumulated_findings.append(item)

        # Budget gate: skip individual review once cap reached
        if findings_reviewed >= MAX_FINDINGS_REVIEWED:
            continue

        findings_reviewed += 1
        review = await app.call(
            "contract-af.adversary_reviewer",
            finding={
                "id": item.id,
                "clause_ref": item.clause_ref,
                "description": item.description,
                "severity": item.severity.value,
                "clause_text": item.clause_text,
            },
            contract_type=intake.contract_type,
            opposing_role=_get_opposing_role(intake),
            contract_text=_truncate_for_wire(contract_text),
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
                    severity=Severity(trap.get("severity", "high").lower()),
                )
            )

        # Track uncovered sections with potential traps
        uncovered_sections.extend(review.get("uncovered_sections_with_traps", []))

    # Combined pattern analysis: let the AI identify survival patterns,
    # compounding risks, and other combined threats across all findings
    if accumulated_findings and sub_agents_used < MAX_SUB_AGENTS:
        sub_agents_used += 1
        finding_summaries = [
            f"[{f.clause_ref}] {f.severity.value}: {f.description}" for f in accumulated_findings
        ]
        trap_result = await app.call(
            "contract-af.adversary_reviewer",
            prompt=(
                f"Review ALL findings below for combined risk patterns from the "
                f"opposing party's perspective. Look for:\n"
                f"- Clauses that survive termination creating combined obligations\n"
                f"- Interacting clauses that compound liability\n"
                f"- Hidden traps that only emerge when multiple clauses interact\n\n"
                f"Findings:\n" + "\n".join(finding_summaries)
            ),
            contract_text=_truncate_for_wire(contract_text),
        )
        if isinstance(trap_result, dict) and trap_result.get("hidden_traps"):
            for trap in trap_result["hidden_traps"]:
                hidden_traps.append(
                    HiddenTrap(
                        clause_refs=trap.get("clause_refs", []),
                        description=trap.get("description", ""),
                        exploitation_scenario=trap.get("exploitation_scenario", ""),
                        severity=Severity(trap.get("severity", "high").lower()),
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
