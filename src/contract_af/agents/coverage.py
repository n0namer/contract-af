"""Coverage gate: .ai() call that assesses whether analysis coverage is sufficient."""

from __future__ import annotations

from contract_af.models import (
    AdversaryResult,
    AnatomyResult,
    ClauseAnalysisResult,
    CoverageAssessment,
)

MAX_ITERATIONS = 2
MAX_NEW_ANALYSTS = 3

COVERAGE_PROMPT = """Assess analysis coverage. Given sections analyzed vs total,
coverage notes from analysts, uncovered sections with potential traps,
and risk signals for unanalyzed sections, determine if coverage is sufficient.
If not, specify which sections need analysis or deeper review."""


async def assess_coverage(
    app,
    anatomy: AnatomyResult,
    analysis_results: list[ClauseAnalysisResult],
    adversary_result: AdversaryResult | None = None,
    iteration: int = 0,
) -> CoverageAssessment:
    """Check if analysis coverage is sufficient."""
    if iteration >= MAX_ITERATIONS:
        return CoverageAssessment(
            is_sufficient=True,
            coverage_ratio=_compute_coverage_ratio(anatomy, analysis_results),
            iteration=iteration,
        )

    all_analyzed: set[str] = set()
    coverage_notes: list[str] = []
    for result in analysis_results:
        all_analyzed.update(result.sections_analyzed)
        coverage_notes.extend(result.coverage_notes)

    all_sections = {s.number for s in anatomy.sections}
    unanalyzed = all_sections - all_analyzed

    uncovered_with_traps = (
        adversary_result.uncovered_sections_with_traps
        if adversary_result
        else []
    )

    risk_signals_for_unanalyzed = [
        rs for rs in anatomy.risk_surface if rs.section in unanalyzed
    ]

    assessment = await app.ai(
        prompt=COVERAGE_PROMPT,
        input={
            "total_sections": len(all_sections),
            "analyzed_sections": len(all_analyzed),
            "unanalyzed_sections": list(unanalyzed),
            "coverage_notes": coverage_notes,
            "uncovered_with_traps": uncovered_with_traps,
            "risk_signals": [
                rs.model_dump() for rs in risk_signals_for_unanalyzed
            ],
        },
        schema=CoverageAssessment,
    )

    assessment = assessment.model_copy(
        update={
            "iteration": iteration,
            "coverage_ratio": _compute_coverage_ratio(anatomy, analysis_results),
            "sections_to_analyze": assessment.sections_to_analyze[
                :MAX_NEW_ANALYSTS
            ],
        },
    )

    return assessment


def _compute_coverage_ratio(
    anatomy: AnatomyResult,
    results: list[ClauseAnalysisResult],
) -> float:
    """Compute the ratio of analyzed sections to total sections."""
    all_sections = {s.number for s in anatomy.sections}
    analyzed: set[str] = set()
    for r in results:
        analyzed.update(r.sections_analyzed)
    return len(analyzed) / max(len(all_sections), 1)
