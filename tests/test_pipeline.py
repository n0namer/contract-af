"""Integration tests for the full pipeline orchestrator.

Tests the 7-phase pipeline end-to-end with mocked app.ai() and app.call()
responses, verifying correct orchestration, parallel execution, coverage
looping, and report generation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from contract_af.models import (
    ContractReport,
    CoverageAssessment,
    IntakeResult,
    Party,
    Severity,
)
from contract_af.pipeline.orchestrator import (
    MAX_COVERAGE_ITERATIONS,
    analyze_contract,
)


# ---------------------------------------------------------------------------
# Shared helpers: mock data builders (immutable — return new objects each time)
# ---------------------------------------------------------------------------


def _make_intake() -> IntakeResult:
    return IntakeResult(
        contract_type="saas_agreement",
        parties=[
            Party(name="Acme Cloud Inc.", role="provider", entity_type="corporation"),
            Party(name="TechStart LLC", role="customer", entity_type="llc"),
        ],
        your_role="customer",
        jurisdiction="Delaware, USA",
        governing_law="Delaware",
        deal_structure="SaaS subscription for project management",
        complexity="standard",
        confident=True,
    )


def _make_finding_raw(
    *,
    clause_ref: str = "5.1",
    severity: str = "high",
    category: str = "ip",
    description: str = "Overbroad IP assignment",
) -> dict:
    return {
        "clause_ref": clause_ref,
        "clause_text": "All Work Product shall be the sole property of Provider.",
        "category": category,
        "severity": severity,
        "description": description,
        "reasoning": "Assigns all inventions regardless of relation to business.",
        "remediation": "Limit to inventions using Provider's confidential info.",
        "confidence": 0.9,
    }


def _make_coverage_sufficient() -> CoverageAssessment:
    return CoverageAssessment(
        is_sufficient=True,
        coverage_ratio=0.95,
        sections_to_analyze=[],
        sections_to_deepen=[],
        iteration=0,
    )


def _make_coverage_insufficient(
    sections_to_analyze: list[str] | None = None,
) -> CoverageAssessment:
    return CoverageAssessment(
        is_sufficient=False,
        coverage_ratio=0.60,
        sections_to_analyze=sections_to_analyze or ["11"],
        sections_to_deepen=[],
        iteration=0,
    )


# ---------------------------------------------------------------------------
# Mock app factory
# ---------------------------------------------------------------------------


def _build_mock_app(
    *,
    coverage_sequence: list[CoverageAssessment] | None = None,
    clause_findings: list[list[dict]] | None = None,
) -> MagicMock:
    """Build a mock app with side_effect dispatchers for .ai() and .call().

    Parameters
    ----------
    coverage_sequence:
        Sequence of CoverageAssessment objects returned by successive
        .ai() coverage calls. Defaults to a single sufficient assessment.
    clause_findings:
        Per-cluster findings lists returned by successive clause_analyst
        calls. Defaults to a single cluster with one finding.
    """
    app = MagicMock()
    intake = _make_intake()

    # --- Defaults ---
    if coverage_sequence is None:
        coverage_sequence = [_make_coverage_sufficient()]
    if clause_findings is None:
        clause_findings = [[_make_finding_raw()]]

    coverage_iter = iter(coverage_sequence)
    findings_iter = iter(clause_findings)

    # --- .ai() dispatcher ---
    async def ai_side_effect(*, prompt, input, schema, **kwargs):  # noqa: A002
        if schema is IntakeResult:
            return intake

        # AnalysisPlan
        from contract_af.models import AnalysisPlan, ClauseCluster, Depth, EscalationTrigger

        if schema is AnalysisPlan:
            return AnalysisPlan(
                clusters=[
                    ClauseCluster(
                        name="ip_work_product",
                        sections=["5"],
                        initial_depth=Depth.STANDARD,
                        escalation_trigger=EscalationTrigger.ANY_CRITICAL,
                    ),
                    ClauseCluster(
                        name="liability_indemnity",
                        sections=["8", "9"],
                        initial_depth=Depth.STANDARD,
                        escalation_trigger=EscalationTrigger.MULTIPLE_HIGH,
                    ),
                ],
                skipped_sections=["15"],
            )

        # CoverageAssessment
        if schema is CoverageAssessment:
            try:
                return next(coverage_iter)
            except StopIteration:
                return _make_coverage_sufficient()

        raise ValueError(f"Unexpected .ai() schema: {schema}")

    app.ai = AsyncMock(side_effect=ai_side_effect)

    # --- .call() dispatcher ---
    async def call_side_effect(agent_name, *, input, **kwargs):  # noqa: A002
        if agent_name == "contract-af.intake_harness":
            return intake.model_dump()

        if agent_name == "contract-af.anatomist":
            return {
                "sections": [
                    {"number": "1", "title": "DEFINITIONS"},
                    {"number": "5", "title": "INTELLECTUAL PROPERTY"},
                    {"number": "8", "title": "LIMITATION OF LIABILITY"},
                    {"number": "9", "title": "INDEMNIFICATION"},
                    {"number": "15", "title": "MISCELLANEOUS"},
                ],
                "defined_terms": [],
                "cross_references": [],
            }

        if agent_name == "contract-af.clause_analyst":
            try:
                raw_findings = next(findings_iter)
            except StopIteration:
                raw_findings = []
            return {
                "findings": raw_findings,
                "references_to_follow": [],
                "deep_dives_needed": [],
                "coverage_notes": [],
            }

        if agent_name == "contract-af.cross_ref_resolver":
            return {"has_interaction": False}

        if agent_name == "contract-af.adversary_reviewer":
            return {
                "is_false_positive": False,
                "exploitation_scenario": "",
                "hidden_traps": [],
                "uncovered_sections_with_traps": [],
            }

        if agent_name == "contract-af.gap_analyst":
            return {"found": False}

        if agent_name == "contract-af.risk_synthesizer":
            task = input.get("task", "") if isinstance(input, dict) else ""
            if task == "generate_negotiation_strategy":
                return {
                    "strategy": "Negotiate removal of overbroad clause",
                }
            if task == "generate_negotiation_plan":
                return {
                    "priorities": ["Remove IP assignment clause"],
                    "fallback_positions": ["Limit to related inventions"],
                    "deal_breakers": ["Unrestricted IP transfer"],
                }
            if task == "generate_executive_summary":
                return {
                    "summary": "High risk contract requiring negotiation.",
                }
            return {"strategy": "Default strategy", "summary": "Default summary"}

        if agent_name == "contract-af.report_writer":
            task = input.get("task", "") if isinstance(input, dict) else ""
            if task == "generate_markdown_report":
                return {"markdown": "# Contract Review Report\n\nFindings here."}
            if task == "generate_negotiation_playbook":
                return {"playbook": "## Negotiation Playbook\n\nSteps here."}
            return {"markdown": "# Report", "playbook": "## Playbook"}

        if agent_name == "contract-af.definition_impact_analyzer":
            return {"findings": []}

        if agent_name == "contract-af.combination_deep_dive":
            return {"findings": []}

        return {}

    app.call = AsyncMock(side_effect=call_side_effect)

    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_simple(sample_contract_text: str):
    """Full pipeline with all mocks returns a ContractReport with all fields."""
    app = _build_mock_app()

    report = await analyze_contract(app, sample_contract_text, user_context="I am the customer")

    assert isinstance(report, ContractReport)
    assert report.executive_summary
    assert report.risk_report_md
    assert report.negotiation_playbook
    assert isinstance(report.structured_json, dict)
    assert report.structured_json["contract_type"] == "saas_agreement"
    assert report.metadata.get("elapsed_seconds") is not None
    assert report.metadata["elapsed_seconds"] >= 0


@pytest.mark.asyncio
async def test_parallel_cluster_execution(sample_contract_text: str):
    """Multiple clusters produce distinct findings that all appear in the report."""
    ip_finding = _make_finding_raw(
        clause_ref="5.1",
        severity="high",
        category="ip",
        description="Overbroad IP assignment",
    )
    liability_finding = _make_finding_raw(
        clause_ref="8.1",
        severity="medium",
        category="liability",
        description="Liability cap too low",
    )

    app = _build_mock_app(clause_findings=[[ip_finding], [liability_finding]])

    report = await analyze_contract(app, sample_contract_text)

    assert isinstance(report, ContractReport)
    # Both clusters should be analyzed
    assert report.metadata["clusters_analyzed"] >= 2

    # Both cluster categories should appear in structured output
    # Note: _parse_finding uses cluster.name as category, not the raw finding's category
    finding_categories = {
        f["category"] for f in report.structured_json.get("findings", [])
    }
    assert "ip_work_product" in finding_categories
    assert "liability_indemnity" in finding_categories


@pytest.mark.asyncio
async def test_coverage_loop_retries(sample_contract_text: str):
    """First coverage check returns insufficient; second returns sufficient."""
    coverage_seq = [
        _make_coverage_insufficient(sections_to_analyze=["11"]),
        _make_coverage_sufficient(),
    ]
    # Findings for iteration 0 clusters (2 clusters) then iteration 1 gap cluster
    findings_seq = [
        [_make_finding_raw(clause_ref="5.1")],
        [_make_finding_raw(clause_ref="8.1")],
        [_make_finding_raw(clause_ref="11.1", category="non_compete")],
    ]

    app = _build_mock_app(
        coverage_sequence=coverage_seq,
        clause_findings=findings_seq,
    )

    report = await analyze_contract(app, sample_contract_text)

    assert isinstance(report, ContractReport)
    assert report.metadata["coverage_iterations"] == 2
    assert report.metadata["total_findings"] >= 3


@pytest.mark.asyncio
async def test_coverage_max_iterations(sample_contract_text: str):
    """Coverage never becomes sufficient; pipeline stops at MAX_COVERAGE_ITERATIONS."""
    # Every coverage check returns insufficient
    coverage_seq = [
        _make_coverage_insufficient(sections_to_analyze=["11"]),
        _make_coverage_insufficient(sections_to_analyze=["12"]),
        _make_coverage_insufficient(sections_to_analyze=["13"]),
    ]

    # Provide enough findings for all iterations
    findings_seq = [
        [_make_finding_raw(clause_ref="5.1")],
        [_make_finding_raw(clause_ref="8.1")],
        # iteration 1: gap cluster for section 11
        [_make_finding_raw(clause_ref="11.1")],
        # iteration 2: gap cluster for section 12
        [_make_finding_raw(clause_ref="12.1")],
    ]

    app = _build_mock_app(
        coverage_sequence=coverage_seq,
        clause_findings=findings_seq,
    )

    report = await analyze_contract(app, sample_contract_text)

    assert isinstance(report, ContractReport)
    # Should stop at MAX + 1 iterations (0-indexed loop runs 0..MAX)
    assert report.metadata["coverage_iterations"] <= MAX_COVERAGE_ITERATIONS + 1


@pytest.mark.asyncio
async def test_report_metadata(sample_contract_text: str):
    """Report metadata contains elapsed_seconds, total_findings, clusters_analyzed."""
    app = _build_mock_app()

    report = await analyze_contract(app, sample_contract_text)

    assert "elapsed_seconds" in report.metadata
    assert isinstance(report.metadata["elapsed_seconds"], (int, float))
    assert report.metadata["elapsed_seconds"] >= 0

    assert "total_findings" in report.metadata
    assert isinstance(report.metadata["total_findings"], int)

    assert "clusters_analyzed" in report.metadata
    assert isinstance(report.metadata["clusters_analyzed"], int)
    assert report.metadata["clusters_analyzed"] >= 1

    assert "coverage_iterations" in report.metadata
    assert "combination_risks" in report.metadata


@pytest.mark.asyncio
async def test_empty_findings(sample_contract_text: str):
    """No findings from analysts; pipeline still completes with empty report."""
    app = _build_mock_app(clause_findings=[[], []])

    report = await analyze_contract(app, sample_contract_text)

    assert isinstance(report, ContractReport)
    assert report.metadata["total_findings"] == 0
    # Structured JSON should still be valid even with no findings
    assert isinstance(report.structured_json, dict)
    assert report.structured_json.get("findings") is not None
