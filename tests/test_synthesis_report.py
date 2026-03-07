"""Tests for scoring, coverage gate, risk synthesizer, and report writer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from contract_af.agents.coverage import (
    MAX_ITERATIONS,
    _compute_coverage_ratio,
    assess_coverage,
)
from contract_af.agents.report_writer import (
    _generate_fallback_markdown,
    generate_report,
)
from contract_af.agents.synthesizer import synthesize_findings
from contract_af.models import (
    AdversaryResult,
    AnatomyResult,
    ClauseAnalysisResult,
    CombinationRisk,
    ContractReport,
    CoverageAssessment,
    Exploitation,
    FalsePositive,
    Finding,
    HiddenTrap,
    IntakeResult,
    NegotiationPlan,
    Party,
    RankedFinding,
    RiskProfile,
    Section,
    Severity,
    SynthesisResult,
)
from contract_af.scoring import (
    SEVERITY_WEIGHTS,
    compute_risk_score,
    is_enforceable,
)


# ---------------------------------------------------------------------------
# Helpers: realistic fixtures
# ---------------------------------------------------------------------------


def _make_finding(
    *,
    id: str = "f-1",
    clause_ref: str = "5.1",
    category: str = "ip",
    severity: Severity = Severity.HIGH,
    description: str = "Broad IP assignment clause.",
    reasoning: str = "Assigns all work product to provider.",
    remediation: str = "Narrow scope to service-related work.",
) -> Finding:
    return Finding(
        id=id,
        clause_ref=clause_ref,
        clause_text="All Work Product shall be the sole property of Provider.",
        category=category,
        severity=severity,
        description=description,
        reasoning=reasoning,
        remediation=remediation,
    )


def _make_anatomy(section_numbers: list[str] | None = None) -> AnatomyResult:
    nums = section_numbers or ["1", "2", "3", "4", "5"]
    return AnatomyResult(
        sections=[Section(number=n, title=f"Section {n}") for n in nums],
        defined_terms=[],
        cross_references=[],
    )


def _make_analysis_result(
    sections_analyzed: list[str],
    findings: list[Finding] | None = None,
    coverage_notes: list[str] | None = None,
) -> ClauseAnalysisResult:
    return ClauseAnalysisResult(
        findings=findings or [],
        sections_analyzed=sections_analyzed,
        coverage_notes=coverage_notes or [],
    )


def _make_adversary(
    *,
    false_positive_ids: list[str] | None = None,
    hidden_traps: list[HiddenTrap] | None = None,
    exploitation_finding_ids: list[str] | None = None,
) -> AdversaryResult:
    return AdversaryResult(
        false_positives=[
            FalsePositive(
                finding_id=fid,
                reason="Not actually risky.",
                evidence="Industry standard clause.",
            )
            for fid in (false_positive_ids or [])
        ],
        hidden_traps=hidden_traps or [],
        exploitation_scenarios=[
            Exploitation(
                finding_id=fid,
                scenario="Opposing party exploits this clause.",
                impact="Significant financial risk.",
            )
            for fid in (exploitation_finding_ids or [])
        ],
    )


def _make_intake(
    *,
    contract_type: str = "saas_agreement",
    jurisdiction: str = "Delaware, USA",
) -> IntakeResult:
    return IntakeResult(
        contract_type=contract_type,
        parties=[
            Party(name="Acme Cloud Inc.", role="provider", entity_type="corporation"),
            Party(name="TechStart LLC", role="customer", entity_type="llc"),
        ],
        your_role="customer",
        jurisdiction=jurisdiction,
        governing_law="Delaware",
        deal_structure="SaaS subscription with annual renewal.",
        complexity="standard",
        confident=True,
    )


def _make_synthesis(
    findings: list[RankedFinding] | None = None,
    overall_risk: Severity = Severity.HIGH,
) -> SynthesisResult:
    if findings is None:
        f = _make_finding()
        findings = [
            RankedFinding(
                finding=f,
                composite_score=9.1,
                rank=1,
                negotiation_strategy="Request narrower IP scope.",
            )
        ]
    return SynthesisResult(
        findings=findings,
        negotiation_strategy=NegotiationPlan(
            priorities=["Narrow IP assignment"],
            fallback_positions=["Limit to service-related work"],
            deal_breakers=["Perpetual IP assignment"],
        ),
        overall_risk_profile=RiskProfile(
            overall_risk=overall_risk,
            category_scores={"ip": 9.1},
            deal_recommendation="high_risk_review",
        ),
        executive_summary="This contract presents HIGH risk due to broad IP assignment.",
    )


# ===========================================================================
# Scoring Tests (pure Python, no mocks)
# ===========================================================================


class TestSeverityWeights:
    """Base severity weights are correct."""

    def test_critical_weight(self):
        assert SEVERITY_WEIGHTS[Severity.CRITICAL] == 10.0

    def test_high_weight(self):
        assert SEVERITY_WEIGHTS[Severity.HIGH] == 7.0

    def test_medium_weight(self):
        assert SEVERITY_WEIGHTS[Severity.MEDIUM] == 4.0

    def test_low_weight(self):
        assert SEVERITY_WEIGHTS[Severity.LOW] == 2.0

    def test_info_weight(self):
        assert SEVERITY_WEIGHTS[Severity.INFO] == 0.5


class TestComputeRiskScore:
    """Deterministic scoring logic."""

    def test_base_score_no_multipliers(self):
        finding = _make_finding(severity=Severity.HIGH)
        score = compute_risk_score(finding)
        assert score == 7.0

    def test_combination_risk_multiplier(self):
        finding = _make_finding(clause_ref="5.1")
        combo = CombinationRisk(
            clause_refs=["5.1", "9.1"],
            description="IP + indemnity interaction.",
            severity=Severity.HIGH,
            investigation_result="Broad assignment combined with one-sided indemnity.",
        )
        score = compute_risk_score(finding, combination_risks=[combo])
        # HIGH=7.0 * 1.5 = 10.5
        assert score == 10.5

    def test_exploitability_multiplier(self):
        finding = _make_finding(id="f-1")
        adversary = _make_adversary(exploitation_finding_ids=["f-1"])
        score = compute_risk_score(finding, adversary_result=adversary)
        # HIGH=7.0 * 1.3 = 9.1
        assert score == 9.1

    def test_jurisdiction_discount_california_non_compete(self):
        finding = _make_finding(category="non_compete", severity=Severity.HIGH)
        score = compute_risk_score(finding, jurisdiction="California, USA")
        # HIGH=7.0 * 0.3 = 2.1
        assert score == 2.1

    def test_combined_multipliers_stack(self):
        finding = _make_finding(id="f-1", clause_ref="11.1", category="non_compete")
        adversary = _make_adversary(exploitation_finding_ids=["f-1"])
        combo = CombinationRisk(
            clause_refs=["11.1", "14.1"],
            description="Non-compete + survival interaction.",
            severity=Severity.HIGH,
            investigation_result="Survives termination.",
        )
        score = compute_risk_score(
            finding,
            adversary_result=adversary,
            combination_risks=[combo],
            jurisdiction="California, USA",
        )
        # HIGH=7.0 * 1.5 (combo) * 1.3 (exploit) * 0.3 (CA non-compete) = 4.095 -> 4.09
        assert score == 4.09

    def test_no_combination_match_no_multiplier(self):
        finding = _make_finding(clause_ref="5.1")
        combo = CombinationRisk(
            clause_refs=["9.1", "10.1"],
            description="Unrelated combination.",
            severity=Severity.HIGH,
            investigation_result="N/A.",
        )
        score = compute_risk_score(finding, combination_risks=[combo])
        assert score == 7.0

    def test_no_exploitation_match_no_multiplier(self):
        finding = _make_finding(id="f-1")
        adversary = _make_adversary(exploitation_finding_ids=["f-99"])
        score = compute_risk_score(finding, adversary_result=adversary)
        assert score == 7.0


class TestIsEnforceable:
    """Jurisdiction-based enforceability checks."""

    def test_california_non_compete_unenforceable(self):
        finding = _make_finding(category="non_compete")
        assert is_enforceable(finding, "California, USA") is False

    def test_delaware_non_compete_enforceable(self):
        finding = _make_finding(category="non_compete")
        assert is_enforceable(finding, "Delaware, USA") is True

    def test_regular_clause_always_enforceable(self):
        finding = _make_finding(category="ip")
        assert is_enforceable(finding, "California, USA") is True

    def test_north_dakota_non_compete_unenforceable(self):
        finding = _make_finding(category="non_compete")
        # Key in UNENFORCEABLE_PATTERNS is "north_dakota" (underscore)
        assert is_enforceable(finding, "north_dakota") is False

    def test_oklahoma_non_compete_unenforceable(self):
        finding = _make_finding(category="non_compete")
        assert is_enforceable(finding, "Oklahoma") is False

    def test_case_insensitive_jurisdiction(self):
        finding = _make_finding(category="non_compete")
        assert is_enforceable(finding, "CALIFORNIA") is False


# ===========================================================================
# Coverage Gate Tests (async, mock app.ai)
# ===========================================================================


class TestCoverageGate:
    """Coverage gate .ai() call and iteration logic."""

    @pytest.mark.asyncio
    async def test_sufficient_coverage_all_analyzed(self, mock_app):
        anatomy = _make_anatomy(["1", "2", "3"])
        results = [_make_analysis_result(["1", "2", "3"])]

        mock_app.ai.return_value = CoverageAssessment(
            is_sufficient=True,
            coverage_ratio=1.0,
        )

        assessment = await assess_coverage(mock_app, anatomy, results)
        assert assessment.is_sufficient is True
        assert assessment.coverage_ratio == 1.0

    @pytest.mark.asyncio
    async def test_gaps_found_sections_to_analyze(self, mock_app):
        anatomy = _make_anatomy(["1", "2", "3", "4", "5"])
        results = [_make_analysis_result(["1", "2"])]

        mock_app.ai.return_value = CoverageAssessment(
            is_sufficient=False,
            coverage_ratio=0.4,
            sections_to_analyze=["3", "4", "5"],
        )

        assessment = await assess_coverage(mock_app, anatomy, results)
        assert assessment.is_sufficient is False
        assert len(assessment.sections_to_analyze) <= 3  # MAX_NEW_ANALYSTS cap
        assert assessment.coverage_ratio == 0.4

    @pytest.mark.asyncio
    async def test_max_iterations_forces_sufficient(self, mock_app):
        anatomy = _make_anatomy(["1", "2", "3"])
        results = [_make_analysis_result(["1"])]

        assessment = await assess_coverage(mock_app, anatomy, results, iteration=MAX_ITERATIONS)

        assert assessment.is_sufficient is True
        # app.ai should NOT be called at max iterations
        mock_app.ai.assert_not_called()

    @pytest.mark.asyncio
    async def test_coverage_ratio_computed_correctly(self, mock_app):
        anatomy = _make_anatomy(["1", "2", "3", "4"])
        results = [
            _make_analysis_result(["1", "2"]),
            _make_analysis_result(["3"]),
        ]

        mock_app.ai.return_value = CoverageAssessment(
            is_sufficient=True,
            coverage_ratio=0.0,  # will be overwritten by _compute_coverage_ratio
        )

        assessment = await assess_coverage(mock_app, anatomy, results)
        # 3 out of 4 sections analyzed
        assert assessment.coverage_ratio == 0.75

    @pytest.mark.asyncio
    async def test_sections_to_analyze_capped(self, mock_app):
        anatomy = _make_anatomy(["1", "2", "3", "4", "5", "6", "7", "8"])
        results = [_make_analysis_result(["1"])]

        mock_app.ai.return_value = CoverageAssessment(
            is_sufficient=False,
            coverage_ratio=0.0,
            sections_to_analyze=["2", "3", "4", "5", "6", "7", "8"],
        )

        assessment = await assess_coverage(mock_app, anatomy, results)
        # Capped at MAX_NEW_ANALYSTS = 3
        assert len(assessment.sections_to_analyze) == 3


class TestComputeCoverageRatio:
    """Unit tests for the pure function _compute_coverage_ratio."""

    def test_all_analyzed(self):
        anatomy = _make_anatomy(["1", "2", "3"])
        results = [_make_analysis_result(["1", "2", "3"])]
        assert _compute_coverage_ratio(anatomy, results) == 1.0

    def test_none_analyzed(self):
        anatomy = _make_anatomy(["1", "2", "3"])
        results = [_make_analysis_result([])]
        assert _compute_coverage_ratio(anatomy, results) == 0.0

    def test_partial_coverage(self):
        anatomy = _make_anatomy(["1", "2", "3", "4"])
        results = [_make_analysis_result(["1", "3"])]
        assert _compute_coverage_ratio(anatomy, results) == 0.5

    def test_empty_anatomy(self):
        anatomy = _make_anatomy([])
        results = [_make_analysis_result([])]
        # Division by max(0, 1) = 1 -> 0/1 = 0.0
        assert _compute_coverage_ratio(anatomy, results) == 0.0


# ===========================================================================
# Synthesizer Tests (async, mock app.call)
# ===========================================================================


class TestSynthesizer:
    """Risk synthesizer: filtering, scoring, ranking, and profiling."""

    @pytest.mark.asyncio
    async def test_false_positives_removed(self, mock_app):
        findings = [
            _make_finding(id="f-1"),
            _make_finding(id="f-2", clause_ref="9.1", category="liability"),
        ]
        adversary = _make_adversary(false_positive_ids=["f-2"])

        mock_app.call.return_value = {"strategy": "Negotiate.", "summary": "Summary."}

        result = await synthesize_findings(mock_app, findings, adversary, [], "Delaware")

        finding_ids = [rf.finding.id for rf in result.findings]
        assert "f-1" in finding_ids
        assert "f-2" not in finding_ids

    @pytest.mark.asyncio
    async def test_hidden_traps_added(self, mock_app):
        findings = [_make_finding(id="f-1")]
        trap = HiddenTrap(
            clause_refs=["12.1"],
            description="Perpetual license is hidden IP grab.",
            exploitation_scenario="Provider uses all customer feedback forever.",
            severity=Severity.CRITICAL,
        )
        adversary = _make_adversary(hidden_traps=[trap])

        mock_app.call.return_value = {
            "strategy": "Remove clause.",
            "priorities": ["Remove perpetual license"],
            "fallback_positions": [],
            "deal_breakers": [],
            "summary": "Critical risk.",
        }

        result = await synthesize_findings(mock_app, findings, adversary, [], "Delaware")

        categories = [rf.finding.category for rf in result.findings]
        assert "hidden_trap" in categories

    @pytest.mark.asyncio
    async def test_findings_sorted_by_score_descending(self, mock_app):
        findings = [
            _make_finding(id="f-low", severity=Severity.LOW, clause_ref="15.1"),
            _make_finding(id="f-crit", severity=Severity.CRITICAL, clause_ref="5.1"),
            _make_finding(id="f-med", severity=Severity.MEDIUM, clause_ref="3.1"),
        ]
        adversary = _make_adversary()

        mock_app.call.return_value = {
            "strategy": "Negotiate.",
            "priorities": [],
            "fallback_positions": [],
            "deal_breakers": [],
            "summary": "Summary.",
        }

        result = await synthesize_findings(mock_app, findings, adversary, [], "Delaware")

        scores = [rf.composite_score for rf in result.findings]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_negotiation_strategy_only_for_high_scores(self, mock_app):
        findings = [
            _make_finding(id="f-high", severity=Severity.HIGH),
            _make_finding(id="f-low", severity=Severity.LOW, clause_ref="15.1"),
        ]
        adversary = _make_adversary()

        call_count = 0

        async def track_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {
                "strategy": "Negotiate this.",
                "priorities": [],
                "fallback_positions": [],
                "deal_breakers": [],
                "summary": "Summary.",
            }

        mock_app.call = AsyncMock(side_effect=track_calls)

        result = await synthesize_findings(mock_app, findings, adversary, [], "Delaware")

        # LOW finding (score=2.0) should get static text, not LLM call
        low_finding = next(rf for rf in result.findings if rf.finding.id == "f-low")
        assert "Low priority" in low_finding.negotiation_strategy

    @pytest.mark.asyncio
    async def test_risk_profile_critical_threshold(self, mock_app):
        findings = [
            _make_finding(id="f-1", severity=Severity.CRITICAL, clause_ref="5.1"),
        ]
        combo = CombinationRisk(
            clause_refs=["5.1", "9.1"],
            description="IP + indemnity.",
            severity=Severity.CRITICAL,
            investigation_result="Dangerous combo.",
        )
        adversary = _make_adversary(exploitation_finding_ids=["f-1"])

        mock_app.call.return_value = {
            "strategy": "Walk away.",
            "priorities": ["Remove clause"],
            "fallback_positions": [],
            "deal_breakers": ["IP assignment"],
            "summary": "Critical risk.",
        }

        result = await synthesize_findings(mock_app, findings, adversary, [combo], "Delaware")

        # CRITICAL=10 * 1.5 (combo) * 1.3 (exploit) = 19.5 >= 13
        assert result.overall_risk_profile.overall_risk == Severity.CRITICAL
        assert result.overall_risk_profile.deal_recommendation == "walk_away"

    @pytest.mark.asyncio
    async def test_risk_profile_high_threshold(self, mock_app):
        findings = [
            _make_finding(id="f-1", severity=Severity.HIGH),
        ]
        adversary = _make_adversary(exploitation_finding_ids=["f-1"])

        mock_app.call.return_value = {
            "strategy": "Negotiate.",
            "priorities": [],
            "fallback_positions": [],
            "deal_breakers": [],
            "summary": "High risk.",
        }

        result = await synthesize_findings(mock_app, findings, adversary, [], "Delaware")

        # HIGH=7.0 * 1.3 (exploit) = 9.1 >= 9
        assert result.overall_risk_profile.overall_risk == Severity.HIGH

    @pytest.mark.asyncio
    async def test_risk_profile_medium_threshold(self, mock_app):
        findings = [
            _make_finding(id="f-1", severity=Severity.HIGH),
        ]
        adversary = _make_adversary()

        mock_app.call.return_value = {
            "strategy": "Negotiate.",
            "priorities": [],
            "fallback_positions": [],
            "deal_breakers": [],
            "summary": "Medium risk.",
        }

        result = await synthesize_findings(mock_app, findings, adversary, [], "Delaware")

        # HIGH=7.0 (no multipliers) >= 5 but < 9
        assert result.overall_risk_profile.overall_risk == Severity.MEDIUM
        assert result.overall_risk_profile.deal_recommendation == "proceed_with_changes"


# ===========================================================================
# Report Writer Tests (async, mock app.call)
# ===========================================================================


class TestReportWriter:
    """Report generation in markdown and structured JSON."""

    @pytest.mark.asyncio
    async def test_markdown_report_contains_sections(self, mock_app):
        synthesis = _make_synthesis()
        intake = _make_intake()

        mock_app.call.side_effect = [
            {
                "markdown": (
                    "# Executive Summary\nHigh risk.\n"
                    "## Findings\n### 1. IP Assignment\n"
                    "## Negotiation Playbook\nNarrow IP scope."
                )
            },
            {"playbook": "## Negotiation Playbook\nNarrow IP scope."},
        ]

        report = await generate_report(mock_app, synthesis, intake)

        assert "Executive Summary" in report.risk_report_md
        assert "Findings" in report.risk_report_md
        assert "Negotiation Playbook" in report.negotiation_playbook

    @pytest.mark.asyncio
    async def test_structured_json_required_fields(self, mock_app):
        synthesis = _make_synthesis()
        intake = _make_intake()

        mock_app.call.side_effect = [
            {"markdown": "# Report\nContent."},
            {"playbook": "Playbook content."},
        ]

        report = await generate_report(mock_app, synthesis, intake)

        json_data = report.structured_json
        assert json_data["contract_type"] == "saas_agreement"
        assert "findings" in json_data
        assert "overall_risk" in json_data
        assert "parties" in json_data
        assert json_data["finding_count"] == len(synthesis.findings)

    @pytest.mark.asyncio
    async def test_structured_json_finding_fields(self, mock_app):
        synthesis = _make_synthesis()
        intake = _make_intake()

        mock_app.call.side_effect = [
            {"markdown": "# Report"},
            {"playbook": ""},
        ]

        report = await generate_report(mock_app, synthesis, intake)

        finding_json = report.structured_json["findings"][0]
        required_keys = {
            "rank",
            "severity",
            "clause_ref",
            "category",
            "description",
            "remediation",
            "composite_score",
        }
        assert required_keys.issubset(finding_json.keys())

    @pytest.mark.asyncio
    async def test_fallback_markdown_on_harness_failure(self, mock_app):
        synthesis = _make_synthesis()
        intake = _make_intake()

        # First call returns non-dict (harness failure), second returns playbook
        mock_app.call.side_effect = [
            "raw string instead of dict",
            {"playbook": ""},
        ]

        report = await generate_report(mock_app, synthesis, intake)

        # Should use fallback markdown
        assert "Contract Review Report" in report.risk_report_md
        assert "Executive Summary" in report.risk_report_md
        assert "Findings" in report.risk_report_md

    @pytest.mark.asyncio
    async def test_report_metadata(self, mock_app):
        synthesis = _make_synthesis()
        intake = _make_intake()

        mock_app.call.side_effect = [
            {"markdown": "# Report"},
            {"playbook": ""},
        ]

        report = await generate_report(mock_app, synthesis, intake)

        assert report.metadata["finding_count"] == 1
        assert report.metadata["overall_risk"] == "high"


class TestFallbackMarkdown:
    """Fallback markdown generation (pure Python)."""

    def test_generates_valid_markdown(self):
        synthesis = _make_synthesis()
        intake = _make_intake()

        md = _generate_fallback_markdown(synthesis, intake)

        assert md.startswith("# Contract Review Report: Saas Agreement")
        assert "## Executive Summary" in md
        assert "## Findings" in md
        assert "HIGH" in md.upper()

    def test_includes_all_findings(self):
        f1 = _make_finding(id="f-1", clause_ref="5.1")
        f2 = _make_finding(
            id="f-2",
            clause_ref="9.1",
            category="liability",
            severity=Severity.CRITICAL,
        )
        ranked = [
            RankedFinding(
                finding=f1,
                composite_score=9.1,
                rank=1,
                negotiation_strategy="Narrow scope.",
            ),
            RankedFinding(
                finding=f2,
                composite_score=13.0,
                rank=2,
                negotiation_strategy="Remove clause.",
            ),
        ]
        synthesis = _make_synthesis(findings=ranked, overall_risk=Severity.CRITICAL)
        intake = _make_intake()

        md = _generate_fallback_markdown(synthesis, intake)

        assert "5.1" in md
        assert "9.1" in md
        assert "**Score:** 9.1" in md
        assert "**Score:** 13.0" in md

    def test_includes_remediation_and_negotiation(self):
        synthesis = _make_synthesis()
        intake = _make_intake()

        md = _generate_fallback_markdown(synthesis, intake)

        assert "**Remediation:**" in md
        assert "**Negotiation:**" in md

    def test_overall_risk_and_recommendation_shown(self):
        synthesis = _make_synthesis()
        intake = _make_intake()

        md = _generate_fallback_markdown(synthesis, intake)

        assert "**Overall Risk:** HIGH" in md
        assert "**Recommendation:** high_risk_review" in md
