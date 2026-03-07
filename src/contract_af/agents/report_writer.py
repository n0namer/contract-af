"""Report writer: .harness() that generates the final report in multiple formats."""

from __future__ import annotations

from contract_af.models import ContractReport, IntakeResult, SynthesisResult


async def generate_report(
    app,
    synthesis: SynthesisResult,
    intake: IntakeResult,
) -> ContractReport:
    """Generate final contract review report in multiple formats."""
    # Generate markdown report via harness
    md_result = await app.call(
        "contract-af.report_writer",
        task="generate_markdown_report",
        executive_summary=synthesis.executive_summary,
        findings=[
            {
                "rank": rf.rank,
                "severity": rf.finding.severity.value,
                "clause_ref": rf.finding.clause_ref,
                "description": rf.finding.description,
                "reasoning": rf.finding.reasoning,
                "remediation": rf.finding.remediation,
                "negotiation": rf.negotiation_strategy,
                "score": rf.composite_score,
            }
            for rf in synthesis.findings
        ],
        risk_profile=synthesis.overall_risk_profile.model_dump(),
        contract_type=intake.contract_type,
        parties=[p.model_dump() for p in intake.parties],
    )

    risk_report_md = (
        md_result.get("markdown", _generate_fallback_markdown(synthesis, intake))
        if isinstance(md_result, dict)
        else _generate_fallback_markdown(synthesis, intake)
    )

    # Generate negotiation playbook
    playbook_result = await app.call(
        "contract-af.report_writer",
        task="generate_negotiation_playbook",
        findings=[
            {
                "clause_ref": rf.finding.clause_ref,
                "description": rf.finding.description,
                "negotiation": rf.negotiation_strategy,
            }
            for rf in synthesis.findings
            if rf.composite_score >= 5.0
        ],
        negotiation_plan=synthesis.negotiation_strategy.model_dump(),
    )

    playbook = playbook_result.get("playbook", "") if isinstance(playbook_result, dict) else ""

    # Build structured JSON (programmatic, no LLM)
    structured = {
        "contract_type": intake.contract_type,
        "parties": [p.model_dump() for p in intake.parties],
        "overall_risk": synthesis.overall_risk_profile.overall_risk.value,
        "deal_recommendation": synthesis.overall_risk_profile.deal_recommendation,
        "finding_count": len(synthesis.findings),
        "findings": [
            {
                "rank": rf.rank,
                "severity": rf.finding.severity.value,
                "clause_ref": rf.finding.clause_ref,
                "category": rf.finding.category,
                "description": rf.finding.description,
                "remediation": rf.finding.remediation,
                "composite_score": rf.composite_score,
            }
            for rf in synthesis.findings
        ],
        "category_scores": synthesis.overall_risk_profile.category_scores,
    }

    return ContractReport(
        executive_summary=synthesis.executive_summary,
        risk_report_md=risk_report_md,
        negotiation_playbook=playbook,
        structured_json=structured,
        metadata={
            "finding_count": len(synthesis.findings),
            "overall_risk": synthesis.overall_risk_profile.overall_risk.value,
        },
    )


def _generate_fallback_markdown(synthesis: SynthesisResult, intake: IntakeResult) -> str:
    """Fallback markdown if harness fails."""
    lines = [
        f"# Contract Review Report: {intake.contract_type.replace('_', ' ').title()}",
        "",
        "## Executive Summary",
        synthesis.executive_summary,
        "",
        f"**Overall Risk:** {synthesis.overall_risk_profile.overall_risk.value.upper()}",
        f"**Recommendation:** {synthesis.overall_risk_profile.deal_recommendation}",
        "",
        "## Findings",
        "",
    ]
    for rf in synthesis.findings:
        lines.extend(
            [
                f"### {rf.rank}. [{rf.finding.severity.value.upper()}] {rf.finding.clause_ref}",
                f"**Score:** {rf.composite_score}",
                "",
                rf.finding.description,
                "",
                f"**Remediation:** {rf.finding.remediation}",
                "",
                f"**Negotiation:** {rf.negotiation_strategy}",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)
