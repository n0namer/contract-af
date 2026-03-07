"""Pipeline orchestrator — wires the 7-phase contract analysis pipeline.

Phases:
    1. Intake (.ai() + fallback) — classify the contract
    2. Anatomy (.harness()) — structural parsing
    3. Analysis Plan (.ai()) — cluster sections for review
    4. Clause Review (.harness() x N) — parallel per cluster, streaming findings
    5. Review Layer — cross-ref + adversary (streaming) + gap analyst (independent)
    5.5. Coverage Gate — loop back if gaps remain (max 2 iterations)
    6. Synthesis (.harness()) — score, rank, negotiate
    7. Report (.harness()) — generate final deliverable
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from contract_af.agents.adversary import review_as_adversary
from contract_af.agents.adversary import SENTINEL as ADVERSARY_SENTINEL
from contract_af.agents.anatomy import analyze_structure
from contract_af.agents.clause_analyst import analyze_cluster
from contract_af.agents.coverage import assess_coverage
from contract_af.agents.cross_ref import resolve_cross_references
from contract_af.agents.cross_ref import SENTINEL as CROSS_REF_SENTINEL
from contract_af.agents.gap_analyst import analyze_gaps
from contract_af.agents.intake import classify_contract
from contract_af.agents.planner import create_analysis_plan
from contract_af.agents.report_writer import generate_report
from contract_af.agents.synthesizer import synthesize_findings
from contract_af.models import (
    ClauseCluster,
    ContractReport,
    Depth,
    EscalationTrigger,
)

logger = logging.getLogger(__name__)

MAX_COVERAGE_ITERATIONS = 2


async def analyze_contract(
    app: Any,
    document_text: str,
    user_context: str = "",
) -> ContractReport:
    """Run the full 7-phase contract analysis pipeline.

    Parameters
    ----------
    app:
        AgentField application instance exposing ``.ai()`` and ``.call()``.
    document_text:
        Full text of the contract document.
    user_context:
        Optional context from the user (e.g. "I am the customer").

    Returns
    -------
    ContractReport
        Complete analysis report with findings, negotiation playbook,
        and structured JSON output.
    """
    start = time.monotonic()

    # ------------------------------------------------------------------
    # Phase 1-3: Sequential setup
    # ------------------------------------------------------------------
    logger.info("Phase 1: Intake classification")
    intake = await classify_contract(app, document_text, user_context)

    logger.info("Phase 2: Document anatomy")
    anatomy = await analyze_structure(app, document_text, intake)

    logger.info("Phase 3: Analysis planning")
    plan = await create_analysis_plan(app, intake, anatomy)

    # ------------------------------------------------------------------
    # Phase 4-5: Iterative analysis with coverage gate
    # ------------------------------------------------------------------
    all_analysis_results: list = []
    all_findings: list = []
    combination_risks: list = []
    adversary_result = None
    gap_result = None

    for iteration in range(MAX_COVERAGE_ITERATIONS + 1):
        clusters_to_analyze = (
            plan.clusters
            if iteration == 0
            else _make_gap_clusters(coverage.sections_to_analyze + coverage.sections_to_deepen)
        )

        if not clusters_to_analyze:
            logger.info("No clusters to analyze in iteration %d, stopping", iteration)
            break

        logger.info(
            "Phase 4: Clause analysis (iteration %d, %d clusters)",
            iteration,
            len(clusters_to_analyze),
        )

        # Fan-out queues: each streaming consumer gets its own copy
        crossref_queue: asyncio.Queue = asyncio.Queue()
        adversary_queue: asyncio.Queue = asyncio.Queue()

        # Phase 4: Parallel clause analysts producing findings
        async def _run_analysts(
            clusters: list[ClauseCluster] = clusters_to_analyze,
            xq: asyncio.Queue = crossref_queue,
            aq: asyncio.Queue = adversary_queue,
        ) -> None:
            results = await asyncio.gather(
                *(
                    analyze_cluster(
                        app, cluster, anatomy, intake, document_text, None,
                    )
                    for cluster in clusters
                )
            )
            # Fan-out: push every finding to both consumer queues
            for result in results:
                for finding in result.findings:
                    await xq.put(finding)
                    await aq.put(finding)
                all_analysis_results.append(result)
                all_findings.extend(result.findings)
            # Signal completion to downstream consumers
            await xq.put(CROSS_REF_SENTINEL)
            await aq.put(ADVERSARY_SENTINEL)

        # Phase 5: Parallel review layer (streaming consumers + gap analyst)
        logger.info("Phase 5: Review layer (iteration %d)", iteration)

        analyst_task = asyncio.create_task(_run_analysts())

        crossref_task = asyncio.create_task(
            resolve_cross_references(app, crossref_queue, anatomy, document_text)
        )
        adversary_task = asyncio.create_task(
            review_as_adversary(app, adversary_queue, intake, anatomy, document_text)
        )

        # Collect found clause categories from ALL results so far
        found_types = _collect_found_types(all_analysis_results)

        gap_task = asyncio.create_task(
            analyze_gaps(app, intake, anatomy, found_types, document_text)
        )

        # Wait for all Phase 4+5 tasks
        await analyst_task
        new_combination_risks = await crossref_task
        combination_risks.extend(new_combination_risks)
        adversary_result = await adversary_task
        gap_result = await gap_task

        # Phase 5.5: Coverage gate
        logger.info("Phase 5.5: Coverage gate (iteration %d)", iteration)
        coverage = await assess_coverage(
            app, anatomy, all_analysis_results, adversary_result, iteration,
        )

        if coverage.is_sufficient:
            logger.info("Coverage sufficient at iteration %d (%.0f%%)", iteration, coverage.coverage_ratio * 100)
            break

        if iteration >= MAX_COVERAGE_ITERATIONS:
            logger.warning(
                "Max coverage iterations reached (%d), proceeding with %.0f%% coverage",
                MAX_COVERAGE_ITERATIONS,
                coverage.coverage_ratio * 100,
            )
            break

        logger.info(
            "Coverage gap: %d sections to analyze, %d to deepen",
            len(coverage.sections_to_analyze),
            len(coverage.sections_to_deepen),
        )

    # ------------------------------------------------------------------
    # Phase 6: Synthesis
    # ------------------------------------------------------------------
    logger.info("Phase 6: Synthesis (%d findings)", len(all_findings))
    if adversary_result is None:
        raise RuntimeError("Pipeline error: adversary review did not complete")

    synthesis = await synthesize_findings(
        app, all_findings, adversary_result, combination_risks, intake.jurisdiction,
    )

    # ------------------------------------------------------------------
    # Phase 7: Report
    # ------------------------------------------------------------------
    logger.info("Phase 7: Report generation")
    report = await generate_report(app, synthesis, intake)

    elapsed = time.monotonic() - start
    report = report.model_copy(
        update={
            "metadata": {
                **report.metadata,
                "elapsed_seconds": round(elapsed, 2),
                "coverage_iterations": min(iteration + 1, MAX_COVERAGE_ITERATIONS + 1),
                "total_findings": len(all_findings),
                "clusters_analyzed": len(all_analysis_results),
                "combination_risks": len(combination_risks),
            },
        },
    )

    logger.info("Pipeline complete in %.1fs", elapsed)
    return report


def _collect_found_types(analysis_results: list) -> list[str]:
    """Extract unique clause categories from all analysis results."""
    categories: set[str] = set()
    for result in analysis_results:
        for finding in result.findings:
            categories.add(finding.category)
    return sorted(categories)


def _make_gap_clusters(section_numbers: list[str]) -> list[ClauseCluster]:
    """Create ad-hoc clusters for coverage gap re-analysis.

    Each uncovered section gets its own single-section cluster at
    STANDARD depth with ANY_CRITICAL escalation.
    """
    if not section_numbers:
        return []
    return [
        ClauseCluster(
            name=f"coverage_gap_{num}",
            sections=[num],
            initial_depth=Depth.STANDARD,
            escalation_trigger=EscalationTrigger.ANY_CRITICAL,
        )
        for num in section_numbers
    ]
