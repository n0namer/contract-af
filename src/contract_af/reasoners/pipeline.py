"""Reasoner wrappers for all contract-af agents and phases."""

from __future__ import annotations

import asyncio
import json as _json
from typing import Any

from pydantic import BaseModel, Field

from contract_af.models import (
    AdversaryResult,
    AnatomyResult,
    ClauseAnalysisResult,
    ClauseCluster,
    CombinationRisk,
    Finding,
    IntakeResult,
    SynthesisResult,
)

from . import router

_runtime_router: Any = router


_MAX_CONTRACT_CHARS = 30_000  # ~7500 tokens — fits .ai() context comfortably


def _truncate(text: str, limit: int = _MAX_CONTRACT_CHARS) -> str:
    """Truncate long text for .ai() calls to avoid context overflow."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n\n[... middle truncated for context limit ...]\n\n" + text[-half:]


def _to_dict(result: Any, default: dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, BaseModel):
        return result.model_dump()
    if isinstance(result, dict):
        return result
    return default


@router.reasoner()
async def intake_phase(document_text: str, user_context: str = "") -> dict[str, Any]:
    """Phase 1: Intake classification."""
    from contract_af.agents.intake import classify_contract

    intake = await classify_contract(_runtime_router, document_text, user_context)
    return intake.model_dump()


@router.reasoner()
async def anatomy_phase(document_text: str, intake: dict[str, Any]) -> dict[str, Any]:
    """Phase 2: Document anatomy."""
    from contract_af.agents.anatomy import analyze_structure

    intake_obj = IntakeResult(**intake)
    anatomy = await analyze_structure(_runtime_router, document_text, intake_obj)
    return anatomy.model_dump()


@router.reasoner()
async def planner_phase(intake: dict[str, Any], anatomy: dict[str, Any]) -> dict[str, Any]:
    """Phase 3: Analysis planning."""
    from contract_af.agents.planner import create_analysis_plan

    intake_obj = IntakeResult(**intake)
    anatomy_obj = AnatomyResult(**anatomy)
    plan = await create_analysis_plan(_runtime_router, intake_obj, anatomy_obj)
    return plan.model_dump()


@router.reasoner()
async def clause_analysis_phase(
    document_text: str,
    intake: dict[str, Any],
    anatomy: dict[str, Any],
    clusters: list[dict[str, Any]],
) -> dict[str, Any]:
    """Phase 4: Parallel clause analysis."""
    from contract_af.agents.clause_analyst import analyze_cluster

    intake_obj = IntakeResult(**intake)
    anatomy_obj = AnatomyResult(**anatomy)
    cluster_objs = [ClauseCluster(**cluster) for cluster in clusters]

    raw_results = await asyncio.gather(
        *[
            analyze_cluster(_runtime_router, cluster, anatomy_obj, intake_obj, document_text, None)
            for cluster in cluster_objs
        ],
        return_exceptions=True,
    )

    analysis_results = [r for r in raw_results if not isinstance(r, BaseException)]
    findings: list[dict[str, Any]] = []
    for result in analysis_results:
        findings.extend([finding.model_dump() for finding in result.findings])

    return {
        "analysis_results": [result.model_dump() for result in analysis_results],
        "findings": findings,
    }


@router.reasoner()
async def review_phase(
    document_text: str,
    intake: dict[str, Any],
    anatomy: dict[str, Any],
    analysis_results: list[dict[str, Any]],
    found_clause_types: list[str],
) -> dict[str, Any]:
    """Phase 5: Cross-ref + adversary + gap analysis."""
    from contract_af.agents.adversary import SENTINEL as ADVERSARY_SENTINEL
    from contract_af.agents.adversary import review_as_adversary
    from contract_af.agents.cross_ref import SENTINEL as CROSS_REF_SENTINEL
    from contract_af.agents.cross_ref import resolve_cross_references
    from contract_af.agents.gap_analyst import analyze_gaps

    intake_obj = IntakeResult(**intake)
    anatomy_obj = AnatomyResult(**anatomy)
    parsed_results = [ClauseAnalysisResult(**result) for result in analysis_results]

    crossref_queue: asyncio.Queue = asyncio.Queue()
    adversary_queue: asyncio.Queue = asyncio.Queue()

    for result in parsed_results:
        for finding in result.findings:
            await crossref_queue.put(finding)
            await adversary_queue.put(finding)

    await crossref_queue.put(CROSS_REF_SENTINEL)
    await adversary_queue.put(ADVERSARY_SENTINEL)

    results = await asyncio.gather(
        resolve_cross_references(_runtime_router, crossref_queue, anatomy_obj, document_text),
        review_as_adversary(
            _runtime_router, adversary_queue, intake_obj, anatomy_obj, document_text
        ),
        analyze_gaps(_runtime_router, intake_obj, anatomy_obj, found_clause_types, document_text),
        return_exceptions=True,
    )

    combination_risks = results[0] if not isinstance(results[0], BaseException) else []
    adversary_result = (
        results[1]
        if not isinstance(results[1], BaseException)
        else AdversaryResult(
            false_positives=[],
            hidden_traps=[],
            exploitation_scenarios=[],
            uncovered_sections_with_traps=[],
        )
    )
    gap_result_obj = results[2] if not isinstance(results[2], BaseException) else None

    return {
        "combination_risks": [risk.model_dump() for risk in combination_risks]
        if isinstance(combination_risks, list)
        else [],
        "adversary_result": adversary_result.model_dump(),
        "gap_result": gap_result_obj.model_dump()
        if gap_result_obj and hasattr(gap_result_obj, "model_dump")
        else {},
    }


@router.reasoner()
async def synthesis_phase(
    findings: list[dict[str, Any]],
    adversary_result: dict[str, Any],
    combination_risks: list[dict[str, Any]],
    jurisdiction: str,
) -> dict[str, Any]:
    """Phase 6: Synthesis."""
    from contract_af.agents.synthesizer import synthesize_findings

    findings_obj = [Finding(**finding) for finding in findings]
    adversary_obj = AdversaryResult(**adversary_result)
    combination_obj = [CombinationRisk(**risk) for risk in combination_risks]

    synthesis = await synthesize_findings(
        _runtime_router,
        findings_obj,
        adversary_obj,
        combination_obj,
        jurisdiction,
    )
    return synthesis.model_dump()


@router.reasoner()
async def report_phase(
    synthesis: dict[str, Any],
    intake: dict[str, Any],
) -> dict[str, Any]:
    """Phase 7: Report generation."""
    from contract_af.agents.report_writer import generate_report

    synthesis_obj = SynthesisResult(**synthesis)
    intake_obj = IntakeResult(**intake)
    report = await generate_report(_runtime_router, synthesis_obj, intake_obj)
    return report.model_dump()


@router.reasoner()
async def intake_harness(
    document: str,
    partial_intake: dict[str, Any],
    user_context: str = "",
) -> dict[str, Any]:
    """Deep intake classification when .ai() lacks confidence."""

    class IntakeHarnessResult(BaseModel):
        contract_type: str
        parties: list[dict[str, Any]] = Field(default_factory=list)
        your_role: str = ""
        jurisdiction: str = ""
        governing_law: str = ""
        deal_structure: str = ""
        complexity: str = "standard"
        confident: bool = True

    prompt = (
        "You are a legal intake analyst. Read the full contract text and return a "
        "complete classification. Resolve uncertain fields from the partial intake."
    )

    result = await _runtime_router.ai(
        system=prompt,
        user=_json.dumps(
            {
                "document": document,
                "partial_intake": partial_intake,
                "user_context": user_context,
            },
            default=str,
        ),
        schema=IntakeHarnessResult,
    )
    return _to_dict(result, partial_intake)


@router.reasoner()
async def anatomist(
    document_text: str,
    intake: dict[str, Any],
    reason: str = "",
) -> dict[str, Any]:
    """Structural parsing fallback when regex extraction fails."""

    class AnatomistResult(BaseModel):
        sections: list[dict[str, Any]] = Field(default_factory=list)
        defined_terms: list[dict[str, Any]] = Field(default_factory=list)
        cross_references: list[dict[str, Any]] = Field(default_factory=list)
        exhibits: list[dict[str, Any]] = Field(default_factory=list)
        key_dates: list[dict[str, Any]] = Field(default_factory=list)
        risk_surface: list[dict[str, Any]] = Field(default_factory=list)

    result = await _runtime_router.ai(
        system=(
            "You are a contract anatomist. Parse structure from non-standard legal text: "
            "sections, defined terms, cross references, exhibits, key dates, and risk signals."
        ),
        user=_json.dumps(
            {
                "document_text": document_text,
                "intake": intake,
                "reason": reason,
            },
            default=str,
        ),
        schema=AnatomistResult,
    )
    return _to_dict(
        result,
        {
            "sections": [],
            "defined_terms": [],
            "cross_references": [],
            "exhibits": [],
            "key_dates": [],
            "risk_surface": [],
        },
    )


@router.reasoner()
async def clause_analyst(
    sections: dict[str, str],
    context: str,
    depth: str,
    cluster_name: str,
    jurisdiction_rules: list[str] | None = None,
) -> dict[str, Any]:
    """Analyze clause sections for risks."""

    class ClauseAnalysis(BaseModel):
        findings: list[dict[str, Any]] = Field(default_factory=list)
        references_to_follow: list[str] = Field(default_factory=list)
        deep_dives_needed: list[dict[str, Any]] = Field(default_factory=list)
        coverage_notes: list[str] = Field(default_factory=list)

    result = await _runtime_router.ai(
        system=(
            "You are a legal contract risk analyst. Analyze clause sections for risks, "
            "unfavorable terms, missing protections, and liability exposure. "
            "Return findings with clause_ref, clause_text, severity, description, reasoning, "
            "remediation, and confidence."
        ),
        user=_json.dumps(
            {
                "sections": sections,
                "context": context,
                "depth": depth,
                "cluster_name": cluster_name,
                "jurisdiction_rules": jurisdiction_rules or [],
            },
            default=str,
        ),
        schema=ClauseAnalysis,
    )
    return _to_dict(
        result,
        {
            "findings": [],
            "references_to_follow": [],
            "deep_dives_needed": [],
            "coverage_notes": [],
        },
    )


@router.reasoner()
async def definition_impact_analyzer(
    prompt: str,
    sections: list[str],
    contract_text: str,
) -> dict[str, Any]:
    """Deep-dive on definition impacts (meta-prompting target)."""

    class DefinitionImpact(BaseModel):
        findings: list[dict[str, Any]] = Field(default_factory=list)

    result = await _runtime_router.ai(
        system=(
            "You are a legal definition-impact specialist. Evaluate how defined terms "
            "change obligations, scope, and risk outcomes in the provided sections."
        ),
        user=_json.dumps(
            {
                "prompt": prompt,
                "sections": sections,
                "contract_text": _truncate(contract_text),
            },
            default=str,
        ),
        schema=DefinitionImpact,
    )
    return _to_dict(result, {"findings": []})


@router.reasoner()
async def adversary_reviewer(
    finding: dict[str, Any] | None = None,
    contract_type: str = "",
    opposing_role: str = "",
    contract_text: str = "",
    prompt: str = "",
    survival_sections: list[str] | None = None,
) -> dict[str, Any]:
    """Review from opposing party's perspective."""

    class AdversaryReview(BaseModel):
        is_false_positive: bool = False
        false_positive_reason: str = ""
        evidence: str = ""
        exploitation_scenario: str = ""
        impact: str = ""
        hidden_traps: list[dict[str, Any]] = Field(default_factory=list)
        uncovered_sections_with_traps: list[str] = Field(default_factory=list)

    result = await _runtime_router.ai(
        system=(
            "You are an adversarial contract reviewer acting for the opposing party. "
            "Identify false positives, exploit paths, and hidden traps that can be used "
            "against the user's role."
        ),
        user=_json.dumps(
            {
                "finding": finding,
                "contract_type": contract_type,
                "opposing_role": opposing_role,
                "contract_text": _truncate(contract_text),
                "prompt": prompt,
                "survival_sections": survival_sections or [],
            },
            default=str,
        ),
        schema=AdversaryReview,
    )
    return _to_dict(
        result,
        {
            "is_false_positive": False,
            "false_positive_reason": "",
            "evidence": "",
            "exploitation_scenario": "",
            "impact": "",
            "hidden_traps": [],
            "uncovered_sections_with_traps": [],
        },
    )


@router.reasoner()
async def cross_ref_resolver(
    finding_a: dict[str, Any],
    finding_b: dict[str, Any],
    cross_references: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check cross-clause interactions between a pair of findings."""

    class CrossRefInteraction(BaseModel):
        has_interaction: bool = False
        severity: str = "high"
        description: str = ""
        investigation: str = ""
        deep_dive_prompt: str = ""

    result = await _runtime_router.ai(
        system=(
            "You are a cross-clause interaction analyst. Determine whether two findings "
            "interact to create additive or compounding legal risk."
        ),
        user=_json.dumps(
            {
                "finding_a": finding_a,
                "finding_b": finding_b,
                "cross_references": cross_references,
            },
            default=str,
        ),
        schema=CrossRefInteraction,
    )
    return _to_dict(result, {"has_interaction": False})


@router.reasoner()
async def combination_deep_dive(
    prompt: str,
    sections: list[str],
    contract_text: str,
) -> dict[str, Any]:
    """Deep-dive on critical clause combinations."""

    class CombinationDive(BaseModel):
        findings: list[dict[str, Any]] = Field(default_factory=list)

    result = await _runtime_router.ai(
        system=(
            "You are a legal combination-risk specialist. Investigate interactions among "
            "the referenced sections and return concrete combined-risk findings."
        ),
        user=_json.dumps(
            {
                "prompt": prompt,
                "sections": sections,
                "contract_text": _truncate(contract_text),
            },
            default=str,
        ),
        schema=CombinationDive,
    )
    return _to_dict(result, {"findings": []})


@router.reasoner()
async def gap_analyst(
    clause_type: str,
    aliases: list[str],
    contract_text: str,
    existing_sections: list[str],
) -> dict[str, Any]:
    """Verify clause absence in contract."""

    class GapVerification(BaseModel):
        found: bool = False
        found_in: str = ""

    result = await _runtime_router.ai(
        system=(
            "You are a contract completeness analyst. Verify whether the expected clause type "
            "is present under an alternate heading or genuinely absent."
        ),
        user=_json.dumps(
            {
                "clause_type": clause_type,
                "aliases": aliases,
                "existing_sections": existing_sections,
                "contract_text": _truncate(contract_text),
            },
            default=str,
        ),
        schema=GapVerification,
    )
    return _to_dict(result, {"found": False, "found_in": ""})


@router.reasoner()
async def risk_synthesizer(
    task: str = "",
    finding_description: str = "",
    clause_text: str = "",
    severity: str = "",
    jurisdiction: str = "",
    top_findings: list[dict[str, Any]] | None = None,
    overall_risk: str = "",
    finding_count: int = 0,
    top_risks: list[str] | None = None,
    recommendation: str = "",
) -> dict[str, Any]:
    """Generate negotiation strategies and summaries."""

    class NegotiationStrategyResult(BaseModel):
        strategy: str = ""

    class NegotiationPlanResult(BaseModel):
        priorities: list[str] = Field(default_factory=list)
        fallback_positions: list[str] = Field(default_factory=list)
        deal_breakers: list[str] = Field(default_factory=list)

    class ExecutiveSummaryResult(BaseModel):
        summary: str = ""

    payload = {
        "task": task,
        "finding_description": finding_description,
        "clause_text": clause_text,
        "severity": severity,
        "jurisdiction": jurisdiction,
        "top_findings": top_findings or [],
        "overall_risk": overall_risk,
        "finding_count": finding_count,
        "top_risks": top_risks or [],
        "recommendation": recommendation,
    }

    if task == "generate_negotiation_strategy":
        result = await _runtime_router.ai(
            system="Write concise negotiation strategy language for a specific finding.",
            user=_json.dumps(payload, default=str),
            schema=NegotiationStrategyResult,
        )
        return _to_dict(result, {"strategy": ""})

    if task == "generate_negotiation_plan":
        result = await _runtime_router.ai(
            system="Generate an ordered negotiation plan with priorities, fallback positions, and deal breakers.",
            user=_json.dumps(payload, default=str),
            schema=NegotiationPlanResult,
        )
        return _to_dict(result, {"priorities": [], "fallback_positions": [], "deal_breakers": []})

    if task == "generate_executive_summary":
        result = await _runtime_router.ai(
            system="Generate an executive summary of contract risk and recommendation.",
            user=_json.dumps(payload, default=str),
            schema=ExecutiveSummaryResult,
        )
        return _to_dict(result, {"summary": ""})

    return {}


@router.reasoner()
async def report_writer(
    task: str = "",
    executive_summary: str = "",
    findings: list[dict[str, Any]] | None = None,
    risk_profile: dict[str, Any] | None = None,
    contract_type: str = "",
    parties: list[dict[str, Any]] | None = None,
    negotiation_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate markdown reports and playbooks."""

    class MarkdownResult(BaseModel):
        markdown: str = ""

    class PlaybookResult(BaseModel):
        playbook: str = ""

    payload = {
        "task": task,
        "executive_summary": executive_summary,
        "findings": findings or [],
        "risk_profile": risk_profile or {},
        "contract_type": contract_type,
        "parties": parties or [],
        "negotiation_plan": negotiation_plan or {},
    }

    if task == "generate_markdown_report":
        result = await _runtime_router.ai(
            system=(
                "You are a legal report writer. Produce a structured markdown contract risk report "
                "with sections for summary, findings, and recommended actions."
            ),
            user=_json.dumps(payload, default=str),
            schema=MarkdownResult,
        )
        return _to_dict(result, {"markdown": ""})

    if task == "generate_negotiation_playbook":
        result = await _runtime_router.ai(
            system=(
                "You are a legal negotiator. Generate a practical negotiation playbook with "
                "talk tracks, fallback positions, and sequencing guidance."
            ),
            user=_json.dumps(payload, default=str),
            schema=PlaybookResult,
        )
        return _to_dict(result, {"playbook": ""})

    return {}
