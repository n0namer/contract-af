"""Cross-reference resolver — consumes findings from a streaming queue and
checks for cross-clause interactions.

Uses .harness() to evaluate pairwise finding interactions and spawns
deep-dive sub-agents for critical combination risks (meta-prompting pattern).
"""

from __future__ import annotations

import asyncio

from contract_af.models import (
    AnatomyResult,
    CombinationRisk,
    Finding,
    Severity,
)

MAX_DEEP_DIVES = 3
SENTINEL = object()  # Queue termination signal


async def resolve_cross_references(
    app,
    findings_queue: asyncio.Queue,
    anatomy: AnatomyResult,
    contract_text: str,
) -> list[CombinationRisk]:
    """Consume findings from queue, check for cross-clause interactions.

    Implements the streaming pipeline pattern: downstream agent processes
    findings as they arrive from upstream clause analysts, rather than
    waiting for all analysts to complete.
    """
    accumulated_findings: list[Finding] = []
    combination_risks: list[CombinationRisk] = []
    deep_dives = 0

    while True:
        try:
            item = await asyncio.wait_for(findings_queue.get(), timeout=60.0)
        except asyncio.TimeoutError:
            break

        if item is SENTINEL:
            break

        accumulated_findings.append(item)

        # Need at least 2 findings to check combinations
        if len(accumulated_findings) < 2:
            continue

        # Check new finding against all previous findings
        new_finding = accumulated_findings[-1]
        for prev in accumulated_findings[:-1]:
            # Build list of cross-references relevant to this pair
            relevant_refs = [
                cr.model_dump()
                for cr in anatomy.cross_references
                if cr.from_section in (prev.clause_ref, new_finding.clause_ref)
                or cr.to_section in (prev.clause_ref, new_finding.clause_ref)
            ]

            interaction = await app.call(
                "contract-af.cross_ref_resolver",
                finding_a={
                    "clause_ref": prev.clause_ref,
                    "description": prev.description,
                    "clause_text": prev.clause_text,
                },
                finding_b={
                    "clause_ref": new_finding.clause_ref,
                    "description": new_finding.description,
                    "clause_text": new_finding.clause_text,
                },
                cross_references=relevant_refs,
            )

            if not isinstance(interaction, dict) or not interaction.get("has_interaction"):
                continue

            severity = Severity(interaction.get("severity", "high").lower())
            risk = CombinationRisk(
                clause_refs=[prev.clause_ref, new_finding.clause_ref],
                description=interaction.get("description", ""),
                severity=severity,
                investigation_result=interaction.get("investigation", ""),
            )
            combination_risks.append(risk)

            # Spawn deep-dive for critical combinations (budget-capped)
            if severity == Severity.CRITICAL and deep_dives < MAX_DEEP_DIVES:
                deep_dives += 1
                deep_result = await app.call(
                    "contract-af.combination_deep_dive",
                    prompt=interaction.get("deep_dive_prompt", ""),
                    sections=[prev.clause_ref, new_finding.clause_ref],
                    contract_text=contract_text,
                )
                if isinstance(deep_result, dict) and deep_result.get("findings"):
                    for f in deep_result["findings"]:
                        additional_risk = CombinationRisk(
                            clause_refs=f.get("clause_refs", []),
                            description=f.get("description", ""),
                            severity=Severity(f.get("severity", "high").lower()),
                            investigation_result=f.get("investigation", ""),
                        )
                        combination_risks.append(additional_risk)

    return combination_risks
