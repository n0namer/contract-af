"""Agent entry point for Contract-AF.

Registers the contract-af agent node with the AgentField control plane
and exposes the ``analyze`` reasoner as the main entry point.
"""

from __future__ import annotations

# pyright: reportMissingImports=false

import os
import time
from pathlib import Path
from typing import Any, cast

import agentfield as _agentfield
from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")

from agentfield import Agent, AIConfig

from .config import AIIntegrationConfig
from .reasoners import router as reasoner_router

_ai_config = AIIntegrationConfig.from_env()
NODE_ID = os.getenv("NODE_ID", "contract-af")
HarnessConfig = getattr(_agentfield, "HarnessConfig")

app = Agent(
    node_id=NODE_ID,
    version="0.1.0",
    description="AI-Native Legal Contract Risk Analyzer",
    agentfield_server=os.getenv("AGENTFIELD_SERVER", "http://localhost:8080"),
    callback_url=os.getenv("AGENT_CALLBACK_URL", "http://127.0.0.1:8004"),
    api_key=os.getenv("AGENTFIELD_API_KEY"),
    harness_config=HarnessConfig(
        provider=_ai_config.provider,
        model=_ai_config.harness_model,
        max_turns=_ai_config.max_turns,
        env=_ai_config.provider_env(),
        opencode_bin=_ai_config.opencode_bin,
        permission_mode="auto",
    ),
    ai_config=AIConfig(
        model=_ai_config.ai_model,
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        api_base="https://openrouter.ai/api/v1",
    ),
)


def _unwrap_phase(result: object, name: str) -> dict[str, Any]:
    if isinstance(result, dict):
        if "output" in result and isinstance(result["output"], dict):
            return result["output"]
        if "result" in result and isinstance(result["result"], dict):
            return result["result"]
        return result
    raise RuntimeError(f"{name} returned non-dict: {type(result)}")


@app.reasoner()
async def analyze(
    document_text: str,
    user_context: str = "",
) -> dict[str, Any]:
    """Main entry point — runs the full 7-phase pipeline via phase reasoners."""
    from .agents.coverage import assess_coverage
    from .models import AdversaryResult, AnatomyResult, ClauseAnalysisResult
    from .pipeline.orchestrator import (
        MAX_COVERAGE_ITERATIONS,
        _collect_found_types,
        _make_gap_clusters,
    )

    start = time.monotonic()
    node_id = os.getenv("NODE_ID", "contract-af")

    app.note("Starting Contract-AF analysis pipeline", tags=["analyze", "start"])

    app.note("Phase 1: Intake", tags=["phase", "intake"])
    intake_raw = await app.call(
        f"{node_id}.intake_phase", document_text=document_text, user_context=user_context
    )
    intake = _unwrap_phase(intake_raw, "intake_phase")

    app.note("Phase 2: Anatomy", tags=["phase", "anatomy"])
    anatomy_raw = await app.call(
        f"{node_id}.anatomy_phase", document_text=document_text, intake=intake
    )
    anatomy = _unwrap_phase(anatomy_raw, "anatomy_phase")

    app.note("Phase 3: Planner", tags=["phase", "planner"])
    plan_raw = await app.call(f"{node_id}.planner_phase", intake=intake, anatomy=anatomy)
    plan = _unwrap_phase(plan_raw, "planner_phase")

    all_analysis_results: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []
    combination_risks: list[dict[str, Any]] = []
    adversary_result: dict[str, Any] | None = None
    coverage = None
    iterations_run = 0

    anatomy_obj = AnatomyResult(**anatomy)

    for iteration in range(MAX_COVERAGE_ITERATIONS + 1):
        iterations_run = iteration + 1
        clusters_to_analyze = (
            plan.get("clusters", [])
            if iteration == 0
            else [
                cluster.model_dump()
                for cluster in _make_gap_clusters(
                    cast("Any", coverage).sections_to_analyze
                    + cast("Any", coverage).sections_to_deepen
                )
            ]
        )

        if not clusters_to_analyze:
            break

        app.note(
            f"Phase 4: Clause analysis iteration {iteration}", tags=["phase", "clause", "analysis"]
        )
        analysis_raw = await app.call(
            f"{node_id}.clause_analysis_phase",
            document_text=document_text,
            intake=intake,
            anatomy=anatomy,
            clusters=clusters_to_analyze,
        )
        analysis_payload = _unwrap_phase(analysis_raw, "clause_analysis_phase")

        iteration_results = cast(
            "list[dict[str, Any]]",
            analysis_payload.get("analysis_results", []),
        )
        iteration_findings = cast("list[dict[str, Any]]", analysis_payload.get("findings", []))

        all_analysis_results.extend(iteration_results)
        all_findings.extend(iteration_findings)

        found_types = _collect_found_types(
            [ClauseAnalysisResult(**result) for result in all_analysis_results]
        )

        app.note(f"Phase 5: Review iteration {iteration}", tags=["phase", "review"])
        review_raw = await app.call(
            f"{node_id}.review_phase",
            document_text=document_text,
            intake=intake,
            anatomy=anatomy,
            analysis_results=iteration_results,
            found_clause_types=found_types,
        )
        review_payload = _unwrap_phase(review_raw, "review_phase")

        combination_risks.extend(
            cast("list[dict[str, Any]]", review_payload.get("combination_risks", []))
        )
        adversary_result = cast("dict[str, Any]", review_payload.get("adversary_result", {}))

        coverage = await assess_coverage(
            app,
            anatomy_obj,
            [ClauseAnalysisResult(**result) for result in all_analysis_results],
            AdversaryResult(**adversary_result),
            iteration,
        )

        if coverage.is_sufficient:
            break

        if iteration >= MAX_COVERAGE_ITERATIONS:
            break

    if adversary_result is None:
        raise RuntimeError("Pipeline error: adversary review did not complete")

    app.note("Phase 6: Synthesis", tags=["phase", "synthesis"])
    synthesis_raw = await app.call(
        f"{node_id}.synthesis_phase",
        findings=all_findings,
        adversary_result=adversary_result,
        combination_risks=combination_risks,
        jurisdiction=intake.get("jurisdiction", ""),
    )
    synthesis = _unwrap_phase(synthesis_raw, "synthesis_phase")

    app.note("Phase 7: Report", tags=["phase", "report"])
    report_raw = await app.call(
        f"{node_id}.report_phase",
        synthesis=synthesis,
        intake=intake,
    )
    report = _unwrap_phase(report_raw, "report_phase")

    elapsed = time.monotonic() - start
    report["metadata"] = {
        **cast("dict[str, Any]", report.get("metadata", {})),
        "elapsed_seconds": round(elapsed, 2),
        "coverage_iterations": min(iterations_run, MAX_COVERAGE_ITERATIONS + 1),
        "total_findings": len(all_findings),
        "clusters_analyzed": len(all_analysis_results),
        "combination_risks": len(combination_risks),
    }

    app.note("Contract-AF analysis complete", tags=["analyze", "complete"])
    return report


async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "service": "contract-af"}


cast("Any", app).add_api_route("/health", health, methods=["GET"])

app.include_router(reasoner_router)


def main() -> None:
    """Entry point for the Contract-AF agent."""
    app.run(port=8004, host="0.0.0.0")


if __name__ == "__main__":
    main()
