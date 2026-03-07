"""Risk synthesizer: .harness() that processes findings with programmatic scoring."""

from __future__ import annotations

from contract_af.models import (
    AdversaryResult,
    CombinationRisk,
    Finding,
    NegotiationPlan,
    RankedFinding,
    RiskProfile,
    Severity,
    SynthesisResult,
)
from contract_af.scoring import compute_risk_score


async def synthesize_findings(
    app,
    findings: list[Finding],
    adversary_result: AdversaryResult,
    combination_risks: list[CombinationRisk],
    jurisdiction: str,
) -> SynthesisResult:
    """Synthesize all findings into ranked report with negotiation strategy."""
    # Remove false positives
    false_positive_ids = {fp.finding_id for fp in adversary_result.false_positives}
    active_findings = [f for f in findings if f.id not in false_positive_ids]

    # Add hidden traps as new findings
    for idx, trap in enumerate(adversary_result.hidden_traps):
        active_findings.append(
            Finding(
                id=f"trap-{len(findings) + idx}",
                clause_ref=", ".join(trap.clause_refs),
                clause_text="",
                category="hidden_trap",
                severity=trap.severity,
                description=trap.description,
                reasoning=trap.exploitation_scenario,
                remediation="",
            )
        )

    # Score and rank (PROGRAMMATIC - no LLM)
    scored: list[tuple[Finding, float]] = []
    for finding in active_findings:
        score = compute_risk_score(finding, adversary_result, combination_risks, jurisdiction)
        scored.append((finding, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    # Generate negotiation strategy via LLM for top findings
    ranked_findings: list[RankedFinding] = []
    for rank, (finding, score) in enumerate(scored, 1):
        if score >= 5.0:
            strategy = await app.call(
                "contract-af.risk_synthesizer",
                finding_description=finding.description,
                clause_text=finding.clause_text,
                severity=finding.severity.value,
                jurisdiction=jurisdiction,
                task="generate_negotiation_strategy",
            )
            negotiation_text = strategy.get("strategy", "") if isinstance(strategy, dict) else ""
        else:
            negotiation_text = "Low priority - monitor but no immediate action needed."

        ranked_findings.append(
            RankedFinding(
                finding=finding,
                composite_score=score,
                rank=rank,
                negotiation_strategy=negotiation_text,
            )
        )

    # Generate overall plan via LLM
    plan_result = await app.call(
        "contract-af.risk_synthesizer",
        task="generate_negotiation_plan",
        top_findings=[
            {
                "description": rf.finding.description,
                "score": rf.composite_score,
            }
            for rf in ranked_findings[:10]
        ],
        jurisdiction=jurisdiction,
    )

    negotiation_plan = NegotiationPlan(
        priorities=(plan_result.get("priorities", []) if isinstance(plan_result, dict) else []),
        fallback_positions=(
            plan_result.get("fallback_positions", []) if isinstance(plan_result, dict) else []
        ),
        deal_breakers=(
            plan_result.get("deal_breakers", []) if isinstance(plan_result, dict) else []
        ),
    )

    # Compute risk profile (PROGRAMMATIC)
    category_scores: dict[str, float] = {}
    for finding, score in scored:
        cat = finding.category
        category_scores[cat] = max(category_scores.get(cat, 0), score)

    max_score = max((s for _, s in scored), default=0)
    overall = (
        Severity.CRITICAL
        if max_score >= 13
        else Severity.HIGH
        if max_score >= 9
        else Severity.MEDIUM
        if max_score >= 5
        else Severity.LOW
    )

    recommendation = (
        "walk_away"
        if overall == Severity.CRITICAL
        else "high_risk_review"
        if overall == Severity.HIGH
        else "proceed_with_changes"
        if overall == Severity.MEDIUM
        else "acceptable"
    )

    risk_profile = RiskProfile(
        overall_risk=overall,
        category_scores=category_scores,
        deal_recommendation=recommendation,
    )

    # Executive summary via LLM (string per archei rules - consumed by Report Writer)
    summary_result = await app.call(
        "contract-af.risk_synthesizer",
        task="generate_executive_summary",
        overall_risk=overall.value,
        finding_count=len(ranked_findings),
        top_risks=[rf.finding.description for rf in ranked_findings[:5]],
        recommendation=recommendation,
    )
    executive_summary = (
        summary_result.get("summary", "")
        if isinstance(summary_result, dict)
        else str(summary_result)
    )

    return SynthesisResult(
        findings=ranked_findings,
        negotiation_strategy=negotiation_plan,
        overall_risk_profile=risk_profile,
        executive_summary=executive_summary,
    )
