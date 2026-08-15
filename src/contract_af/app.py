"""Agent entry point for Contract-AF.

Registers the contract-af agent node with the AgentField control plane
and exposes the ``analyze`` reasoner as the main entry point.
"""

from __future__ import annotations

# pyright: reportMissingImports=false

import os
import shutil
import tempfile
import time
import uuid as _uuid
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
    callback_url=os.getenv("AGENT_CALLBACK_URL", f"http://127.0.0.1:{os.getenv('PORT', '8004')}"),
    api_key=os.getenv("AGENTFIELD_API_KEY"),
    harness_config=HarnessConfig(
        provider=_ai_config.provider,
        model=_ai_config.harness_model,
        max_turns=_ai_config.max_turns,
        env=_ai_config.provider_env(),
        opencode_bin=_ai_config.opencode_bin,
        aforge_bin=_ai_config.aforge_bin,
        permission_mode="auto",
    ),
    ai_config=AIConfig(
        model=_ai_config.ai_model,
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        api_base="https://openrouter.ai/api/v1",
    ),
)


def _unwrap(result: object, name: str) -> object:
    """Extract payload from control-plane envelope, raising on error."""
    if isinstance(result, dict):
        if "error" in result and isinstance(result["error"], dict):
            message = (
                result["error"].get("message")
                or result["error"].get("detail")
                or str(result["error"])
            )
            raise RuntimeError(f"{name} failed: {message}")
        if "output" in result:
            return result["output"]
        if "result" in result:
            return result["result"]
    return result


def _as_dict(payload: object, name: str) -> dict[str, Any]:
    """Ensure *payload* is a dict, raising descriptively if not."""
    if not isinstance(payload, dict):
        raise RuntimeError(f"{name} returned non-dict payload: {type(payload).__name__}")
    return payload


# ---------------------------------------------------------------------------
# Pipeline helpers (inlined from deleted pipeline/orchestrator.py)
# ---------------------------------------------------------------------------

MAX_COVERAGE_ITERATIONS = 2  # Hard cap: max 3 total iterations (0, 1, 2)
MAX_PIPELINE_TIMEOUT_S = 1800  # 30-minute hard wall-clock limit


def _collect_found_types(analysis_results: list) -> list[str]:
    """Extract unique clause categories from all analysis results."""
    categories: set[str] = set()
    for result in analysis_results:
        for finding in result.findings:
            categories.add(finding.category)
    return sorted(categories)


def _make_gap_clusters(section_numbers: list[str]) -> list:
    """Create ad-hoc clusters for coverage gap re-analysis."""
    from .models import ClauseCluster, Depth, EscalationTrigger

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


def _force_partial_report(
    intake: dict[str, Any],
    all_findings: list[dict[str, Any]],
    combination_risks: list[dict[str, Any]],
    adversary_result: dict[str, Any] | None,
    elapsed: float,
    iterations_run: int,
    all_analysis_results: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    """Build a partial report from whatever results we have when hitting a budget cap."""
    return {
        "executive_summary": f"Analysis terminated early: {reason}. Partial results below.",
        "risk_report_md": "",
        "negotiation_playbook": "",
        "structured_json": {
            "findings": all_findings,
            "combination_risks": combination_risks,
            "adversary_result": adversary_result or {},
            "overall_risk_profile": {
                "overall_risk": "unknown",
                "category_scores": {},
                "deal_recommendation": "incomplete_analysis",
            },
        },
        "metadata": {
            "elapsed_seconds": round(elapsed, 2),
            "coverage_iterations": iterations_run,
            "total_findings": len(all_findings),
            "clusters_analyzed": len(all_analysis_results),
            "combination_risks": len(combination_risks),
            "terminated_early": True,
            "termination_reason": reason,
        },
    }


@app.reasoner()
async def analyze(
    document_text: str,
    user_context: str = "",
) -> dict[str, Any]:
    """Main entry point — runs the full 7-phase pipeline via phase reasoners.

    Writes the document to a temp file ONCE and passes the *path* through
    ``app.call()`` wire calls so the 175 KB+ contract is never serialised
    as inline JSON on every hop.  All phases in this process share the
    same filesystem so they can read the file directly.
    """
    from .agents.coverage import assess_coverage
    from .models import AdversaryResult, AnatomyResult, ClauseAnalysisResult

    start = time.monotonic()
    node_id = os.getenv("NODE_ID", "contract-af")

    workdir = tempfile.mkdtemp(prefix=f"contract-af-{_uuid.uuid4().hex[:8]}-")
    doc_path = os.path.join(workdir, "contract.txt")
    Path(doc_path).write_text(document_text, encoding="utf-8")

    def _check_timeout() -> None:
        elapsed = time.monotonic() - start
        if elapsed > MAX_PIPELINE_TIMEOUT_S:
            raise TimeoutError(f"Pipeline exceeded {MAX_PIPELINE_TIMEOUT_S}s wall-clock limit")

    app.note("Starting Contract-AF analysis pipeline", tags=["analyze", "start"])

    all_analysis_results: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []
    combination_risks: list[dict[str, Any]] = []
    adversary_result: dict[str, Any] | None = None
    iterations_run = 0

    try:
        _check_timeout()
        app.note("Phase 1: Intake", tags=["phase", "intake"])
        intake_raw = await app.call(
            f"{node_id}.intake_phase", document_path=doc_path, user_context=user_context
        )
        intake = _as_dict(_unwrap(intake_raw, "intake_phase"), "intake_phase")

        _check_timeout()
        app.note("Phase 2: Anatomy", tags=["phase", "anatomy"])
        anatomy_raw = await app.call(
            f"{node_id}.anatomy_phase", document_path=doc_path, intake=intake
        )
        anatomy = _as_dict(_unwrap(anatomy_raw, "anatomy_phase"), "anatomy_phase")

        _check_timeout()
        app.note("Phase 3: Planner", tags=["phase", "planner"])
        plan_raw = await app.call(f"{node_id}.planner_phase", intake=intake, anatomy=anatomy)
        plan = _as_dict(_unwrap(plan_raw, "planner_phase"), "planner_phase")

        coverage = None
        anatomy_obj = AnatomyResult(**anatomy)

        for iteration in range(MAX_COVERAGE_ITERATIONS + 1):
            _check_timeout()
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
                f"Phase 4: Clause analysis iteration {iteration}",
                tags=["phase", "clause", "analysis"],
            )
            analysis_raw = await app.call(
                f"{node_id}.clause_analysis_phase",
                document_path=doc_path,
                intake=intake,
                anatomy=anatomy,
                clusters=clusters_to_analyze,
            )
            analysis_payload = _as_dict(
                _unwrap(analysis_raw, "clause_analysis_phase"), "clause_analysis_phase"
            )

            iteration_results = cast(
                "list[dict[str, Any]]",
                analysis_payload.get("analysis_results", []),
            )
            iteration_findings = cast("list[dict[str, Any]]", analysis_payload.get("findings", []))

            all_analysis_results.extend(iteration_results)
            all_findings.extend(iteration_findings)

            _check_timeout()
            found_types = _collect_found_types(
                [ClauseAnalysisResult(**result) for result in all_analysis_results]
            )

            app.note(f"Phase 5: Review iteration {iteration}", tags=["phase", "review"])
            review_raw = await app.call(
                f"{node_id}.review_phase",
                document_path=doc_path,
                intake=intake,
                anatomy=anatomy,
                analysis_results=iteration_results,
                found_clause_types=found_types,
            )
            review_payload = _as_dict(_unwrap(review_raw, "review_phase"), "review_phase")

            combination_risks.extend(
                cast("list[dict[str, Any]]", review_payload.get("combination_risks", []))
            )
            adversary_result = cast("dict[str, Any]", review_payload.get("adversary_result", {}))

            _check_timeout()
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

    except TimeoutError as exc:
        elapsed = time.monotonic() - start
        app.note(f"Pipeline timeout: {exc}", tags=["analyze", "timeout"])
        shutil.rmtree(workdir, ignore_errors=True)
        return _force_partial_report(
            intake=locals().get("intake", {}),
            all_findings=all_findings,
            combination_risks=combination_risks,
            adversary_result=adversary_result,
            elapsed=elapsed,
            iterations_run=iterations_run,
            all_analysis_results=all_analysis_results,
            reason=str(exc),
        )

    if adversary_result is None:
        adversary_result = {}

    _check_timeout()
    app.note("Phase 6: Synthesis", tags=["phase", "synthesis"])
    try:
        synthesis_raw = await app.call(
            f"{node_id}.synthesis_phase",
            findings=all_findings,
            adversary_result=adversary_result,
            combination_risks=combination_risks,
            jurisdiction=intake.get("jurisdiction", ""),
        )
        synthesis = _as_dict(_unwrap(synthesis_raw, "synthesis_phase"), "synthesis_phase")
    except (TimeoutError, RuntimeError):
        elapsed = time.monotonic() - start
        shutil.rmtree(workdir, ignore_errors=True)
        return _force_partial_report(
            intake=intake,
            all_findings=all_findings,
            combination_risks=combination_risks,
            adversary_result=adversary_result,
            elapsed=elapsed,
            iterations_run=iterations_run,
            all_analysis_results=all_analysis_results,
            reason="Synthesis phase failed or timed out",
        )

    app.note("Phase 7: Report", tags=["phase", "report"])
    try:
        report_raw = await app.call(
            f"{node_id}.report_phase",
            synthesis=synthesis,
            intake=intake,
        )
        report = _as_dict(_unwrap(report_raw, "report_phase"), "report_phase")
    except (TimeoutError, RuntimeError):
        elapsed = time.monotonic() - start
        shutil.rmtree(workdir, ignore_errors=True)
        return _force_partial_report(
            intake=intake,
            all_findings=all_findings,
            combination_risks=combination_risks,
            adversary_result=adversary_result,
            elapsed=elapsed,
            iterations_run=iterations_run,
            all_analysis_results=all_analysis_results,
            reason="Report phase failed or timed out",
        )

    shutil.rmtree(workdir, ignore_errors=True)

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
