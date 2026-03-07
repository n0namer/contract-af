"""Phase reasoner wrappers — called by app.py via app.call()."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

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
