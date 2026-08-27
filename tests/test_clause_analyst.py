"""Tests for the clause analyst agent."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from contract_af.agents.clause_analyst import (
    MAX_REF_FOLLOWS,
    MAX_SUB_AGENTS,
    _build_analysis_context,
    _check_escalation,
    _get_section_texts,
    analyze_cluster,
)
from contract_af.models import (
    AnatomyResult,
    ClauseCluster,
    CrossRef,
    DefinedTerm,
    Depth,
    EscalationTrigger,
    Finding,
    IntakeResult,
    Party,
    RiskSignal,
    Section,
    Severity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def intake() -> IntakeResult:
    return IntakeResult(
        contract_type="saas_agreement",
        parties=[
            Party(name="Acme Cloud Inc.", role="provider", entity_type="corporation"),
            Party(name="TechStart LLC", role="customer", entity_type="llc"),
        ],
        your_role="customer",
        jurisdiction="California, USA",
        governing_law="Delaware",
        deal_structure="SaaS subscription with annual renewal",
        complexity="standard",
        confident=True,
    )


@pytest.fixture
def anatomy() -> AnatomyResult:
    return AnatomyResult(
        sections=[
            Section(number="5", title="Intellectual Property"),
            Section(number="5.1", title="Ownership"),
            Section(number="5.2", title="Assignment"),
            Section(number="8", title="Limitation of Liability"),
            Section(number="9", title="Indemnification"),
        ],
        defined_terms=[
            DefinedTerm(
                term="Work Product",
                definition_text="Any inventions conceived during the Term",
                section_ref="5",
                usage_count=3,
            ),
        ],
        cross_references=[
            CrossRef(
                from_section="5",
                to_section="1.4",
                relationship_type="as_defined_in",
            ),
        ],
        risk_surface=[
            RiskSignal(
                section="5",
                signal_type="broad_definition",
                description="Work Product definition is overly broad",
                severity=Severity.HIGH,
            ),
        ],
    )


@pytest.fixture
def cluster_standard() -> ClauseCluster:
    """Cluster with ANY_CRITICAL escalation trigger."""
    return ClauseCluster(
        name="ip_work_product",
        sections=["5", "5.1", "5.2"],
        initial_depth=Depth.STANDARD,
        escalation_trigger=EscalationTrigger.ANY_CRITICAL,
        escalated_depth=Depth.THOROUGH,
        jurisdiction_rules=["Cal. Lab. Code 2870 limits IP assignment"],
        priority=10,
    )


@pytest.fixture
def cluster_never_escalate() -> ClauseCluster:
    """Cluster that never escalates."""
    return ClauseCluster(
        name="miscellaneous",
        sections=["15", "15.1", "15.2"],
        initial_depth=Depth.SCAN,
        escalation_trigger=EscalationTrigger.NEVER,
        escalated_depth=Depth.STANDARD,
        priority=1,
    )


@pytest.fixture
def cluster_multiple_high() -> ClauseCluster:
    """Cluster with MULTIPLE_HIGH escalation trigger."""
    return ClauseCluster(
        name="liability",
        sections=["8", "9"],
        initial_depth=Depth.STANDARD,
        escalation_trigger=EscalationTrigger.MULTIPLE_HIGH,
        escalated_depth=Depth.THOROUGH,
        priority=8,
    )


@pytest.fixture
def contract_text() -> str:
    return (
        "5. INTELLECTUAL PROPERTY\n"
        "5.1 All Work Product shall be the sole property of Provider.\n"
        "5.2 Customer hereby assigns all right, title, and interest.\n"
        "\n"
        "8. LIMITATION OF LIABILITY\n"
        "8.1 Provider's aggregate liability shall not exceed fees paid.\n"
        "\n"
        "9. INDEMNIFICATION\n"
        "9.1 Customer shall indemnify Provider against all claims.\n"
        "\n"
        "15. MISCELLANEOUS\n"
        "15.1 Entire Agreement.\n"
        "15.2 Amendments.\n"
        "15.3 Notices.\n"
    )


def _make_raw_finding(
    severity: str = "high",
    clause_ref: str = "5.1",
    description: str = "Broad IP assignment",
) -> dict:
    return {
        "clause_ref": clause_ref,
        "clause_text": "All Work Product shall be the sole property of Provider.",
        "severity": severity,
        "description": description,
        "reasoning": "Overly broad definition captures unrelated inventions.",
        "remediation": "Limit to inventions using Provider resources.",
        "confidence": 0.9,
    }


# ---------------------------------------------------------------------------
# 1. Standard analysis — harness returns findings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_standard_analysis(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """Primary harness call returns findings that appear in ClauseAnalysisResult."""
    mock_app.call.return_value = {
        "findings": [_make_raw_finding()],
        "references_to_follow": [],
        "deep_dives_needed": [],
        "coverage_notes": ["Reviewed all IP sections"],
    }

    result = await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text
    )

    assert len(result.findings) == 1
    assert result.findings[0].severity == Severity.HIGH
    assert result.findings[0].category == "ip_work_product"
    assert result.sections_analyzed == ["5", "5.1", "5.2"]
    assert result.coverage_notes == ["Reviewed all IP sections"]
    assert result.early_exit is False
    assert result.depth_used == Depth.STANDARD
    mock_app.call.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Reference following — analyst follows refs up to MAX_REF_FOLLOWS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reference_following(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """When harness returns references_to_follow, analyst follows them."""
    primary_response = {
        "findings": [_make_raw_finding()],
        "references_to_follow": ["8", "9"],
        "deep_dives_needed": [],
        "coverage_notes": [],
    }
    ref_response = {
        "findings": [
            _make_raw_finding(
                severity="medium",
                clause_ref="8.1",
                description="Liability cap is standard",
            )
        ],
    }
    mock_app.call.side_effect = [primary_response, ref_response, ref_response]

    result = await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text
    )

    # 1 from primary + 1 from each of 2 refs = 3
    assert len(result.findings) == 3
    assert result.sections_followed == ["8", "9"]
    # 1 primary + 2 ref calls = 3
    assert mock_app.call.call_count == 3


# ---------------------------------------------------------------------------
# 3. Reference cap — more than MAX_REF_FOLLOWS refs are truncated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reference_cap(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """Only first MAX_REF_FOLLOWS references are followed."""
    refs = ["8", "9", "15", "15.1", "15.2"]
    assert len(refs) > MAX_REF_FOLLOWS

    primary_response = {
        "findings": [],
        "references_to_follow": refs,
        "deep_dives_needed": [],
        "coverage_notes": [],
    }
    ref_response = {"findings": []}
    # primary + MAX_REF_FOLLOWS ref calls
    mock_app.call.side_effect = [primary_response] + [ref_response] * MAX_REF_FOLLOWS

    result = await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text
    )

    # 1 primary + MAX_REF_FOLLOWS ref calls
    assert mock_app.call.call_count == 1 + MAX_REF_FOLLOWS
    assert len(result.sections_followed) <= MAX_REF_FOLLOWS


# ---------------------------------------------------------------------------
# 4. Depth escalation — critical finding + ANY_CRITICAL trigger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_depth_escalation_any_critical(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """Critical finding with ANY_CRITICAL trigger causes re-analysis at escalated depth."""
    primary_response = {
        "findings": [_make_raw_finding(severity="critical")],
        "references_to_follow": [],
        "deep_dives_needed": [],
        "coverage_notes": [],
    }
    escalated_response = {
        "findings": [
            _make_raw_finding(
                severity="critical",
                clause_ref="5.2",
                description="Assignment clause is irrevocable",
            )
        ],
    }
    mock_app.call.side_effect = [primary_response, escalated_response]

    result = await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text
    )

    assert result.depth_used == Depth.THOROUGH
    # 1 primary + 1 escalated = 2
    assert mock_app.call.call_count == 2
    # Verify the second call used the current direct-kwargs harness contract.
    escalated_kwargs = mock_app.call.call_args_list[1].kwargs
    assert escalated_kwargs["depth"] == "thorough"
    assert "ESCALATED ANALYSIS" in escalated_kwargs["context"]


# ---------------------------------------------------------------------------
# 5. No escalation on NEVER trigger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_escalation_on_never_trigger(
    mock_app, cluster_never_escalate, anatomy, intake, contract_text
):
    """NEVER escalation trigger prevents escalation even with critical findings."""
    mock_app.call.return_value = {
        "findings": [_make_raw_finding(severity="critical")],
        "references_to_follow": [],
        "deep_dives_needed": [],
        "coverage_notes": [],
    }

    result = await analyze_cluster(
        mock_app, cluster_never_escalate, anatomy, intake, contract_text
    )

    assert result.depth_used == Depth.SCAN  # stayed at initial depth
    mock_app.call.assert_called_once()  # no escalation call


# ---------------------------------------------------------------------------
# 6. Early exit — no findings from cluster with 3+ sections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_early_exit(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """No findings from a cluster with >= 3 sections sets early_exit=True."""
    assert len(cluster_standard.sections) >= 3

    mock_app.call.return_value = {
        "findings": [],
        "references_to_follow": [],
        "deep_dives_needed": [],
        "coverage_notes": [],
    }

    result = await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text
    )

    assert result.early_exit is True
    assert len(result.findings) == 0


@pytest.mark.asyncio
async def test_no_early_exit_with_findings(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """Findings present means early_exit is False even with 3+ sections."""
    mock_app.call.return_value = {
        "findings": [_make_raw_finding()],
        "references_to_follow": [],
        "deep_dives_needed": [],
        "coverage_notes": [],
    }

    result = await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text
    )

    assert result.early_exit is False


@pytest.mark.asyncio
async def test_no_early_exit_with_few_sections(
    mock_app, anatomy, intake, contract_text
):
    """No findings from a cluster with < 3 sections does NOT set early_exit."""
    small_cluster = ClauseCluster(
        name="governing_law",
        sections=["13"],
        initial_depth=Depth.SCAN,
        escalation_trigger=EscalationTrigger.NEVER,
    )
    mock_app.call.return_value = {
        "findings": [],
        "references_to_follow": [],
        "deep_dives_needed": [],
        "coverage_notes": [],
    }

    result = await analyze_cluster(
        mock_app, small_cluster, anatomy, intake, contract_text
    )

    assert result.early_exit is False


# ---------------------------------------------------------------------------
# 7. Meta-prompting — deep dives spawn sub-agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_meta_prompting_deep_dives(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """deep_dives_needed triggers sub-agent calls via definition_impact_analyzer."""
    primary_response = {
        "findings": [_make_raw_finding()],
        "references_to_follow": [],
        "deep_dives_needed": [
            {
                "prompt": "Analyze impact of Work Product definition on section 5.1",
                "sections": ["5", "5.1"],
            },
        ],
        "coverage_notes": [],
    }
    dive_response = {
        "findings": [
            _make_raw_finding(
                severity="critical",
                description="Work Product captures pre-existing IP",
            )
        ],
    }
    mock_app.call.side_effect = [primary_response, dive_response]

    result = await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text
    )

    assert result.sub_agents_spawned == 1
    # Verify sub-agent was called with definition_impact_analyzer
    second_call = mock_app.call.call_args_list[1]
    assert second_call[0][0] == "contract-af.definition_impact_analyzer"
    # Finding from dive is included (but escalation may also fire, adding more)
    assert any(
        f.description == "Work Product captures pre-existing IP"
        for f in result.findings
    )


# ---------------------------------------------------------------------------
# 8. Sub-agent cap — more than MAX_SUB_AGENTS dives are truncated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sub_agent_cap(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """Only first MAX_SUB_AGENTS deep dives are spawned."""
    dives = [
        {"prompt": f"Dive {i}", "sections": ["5"]}
        for i in range(5)
    ]
    assert len(dives) > MAX_SUB_AGENTS

    primary_response = {
        "findings": [],
        "references_to_follow": [],
        "deep_dives_needed": dives,
        "coverage_notes": [],
    }
    dive_response = {"findings": []}
    mock_app.call.side_effect = [primary_response] + [dive_response] * MAX_SUB_AGENTS

    result = await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text
    )

    assert result.sub_agents_spawned == MAX_SUB_AGENTS
    # 1 primary + MAX_SUB_AGENTS dives
    assert mock_app.call.call_count == 1 + MAX_SUB_AGENTS


# ---------------------------------------------------------------------------
# 9. Findings queue — findings are put on queue when provided
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_findings_queue(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """When findings_queue is provided, each finding is put on the queue."""
    mock_app.call.return_value = {
        "findings": [
            _make_raw_finding(description="Finding A"),
            _make_raw_finding(description="Finding B"),
        ],
        "references_to_follow": [],
        "deep_dives_needed": [],
        "coverage_notes": [],
    }

    queue: asyncio.Queue = asyncio.Queue()
    result = await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text,
        findings_queue=queue,
    )

    assert len(result.findings) == 2
    assert queue.qsize() == 2

    queued_a = await queue.get()
    queued_b = await queue.get()
    assert queued_a.description == "Finding A"
    assert queued_b.description == "Finding B"


@pytest.mark.asyncio
async def test_findings_queue_receives_ref_and_dive_findings(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """Queue also receives findings from reference follows and deep dives."""
    primary_response = {
        "findings": [_make_raw_finding(description="primary")],
        "references_to_follow": ["8"],
        "deep_dives_needed": [
            {"prompt": "check", "sections": ["5"]},
        ],
        "coverage_notes": [],
    }
    ref_response = {
        "findings": [_make_raw_finding(description="from ref")],
    }
    dive_response = {
        "findings": [_make_raw_finding(description="from dive")],
    }
    mock_app.call.side_effect = [primary_response, ref_response, dive_response]

    queue: asyncio.Queue = asyncio.Queue()
    await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text,
        findings_queue=queue,
    )

    descriptions = []
    while not queue.empty():
        f = await queue.get()
        descriptions.append(f.description)

    assert "primary" in descriptions
    assert "from ref" in descriptions
    assert "from dive" in descriptions


# ---------------------------------------------------------------------------
# 10. _build_analysis_context — returns string (archei rules)
# ---------------------------------------------------------------------------


class TestBuildAnalysisContext:
    """Test _build_analysis_context produces natural-language context."""

    def test_returns_string(self, anatomy, intake, cluster_standard):
        context = _build_analysis_context(anatomy, intake, cluster_standard)
        assert isinstance(context, str)

    def test_contains_contract_type(self, anatomy, intake, cluster_standard):
        context = _build_analysis_context(anatomy, intake, cluster_standard)
        assert "saas_agreement" in context

    def test_contains_parties(self, anatomy, intake, cluster_standard):
        context = _build_analysis_context(anatomy, intake, cluster_standard)
        assert "Acme Cloud Inc." in context
        assert "TechStart LLC" in context

    def test_contains_your_role(self, anatomy, intake, cluster_standard):
        context = _build_analysis_context(anatomy, intake, cluster_standard)
        assert "customer" in context

    def test_contains_jurisdiction(self, anatomy, intake, cluster_standard):
        context = _build_analysis_context(anatomy, intake, cluster_standard)
        assert "California" in context

    def test_contains_relevant_defined_terms(self, anatomy, intake, cluster_standard):
        context = _build_analysis_context(anatomy, intake, cluster_standard)
        assert "Work Product" in context

    def test_contains_cross_references(self, anatomy, intake, cluster_standard):
        context = _build_analysis_context(anatomy, intake, cluster_standard)
        assert "5" in context
        assert "1.4" in context

    def test_contains_risk_signals(self, anatomy, intake, cluster_standard):
        context = _build_analysis_context(anatomy, intake, cluster_standard)
        assert "broad_definition" in context

    def test_contains_jurisdiction_rules(self, anatomy, intake, cluster_standard):
        context = _build_analysis_context(anatomy, intake, cluster_standard)
        assert "Cal. Lab. Code 2870" in context

    def test_excludes_unrelated_terms(self, intake, cluster_standard):
        """Defined terms from other sections are not included."""
        anatomy_other = AnatomyResult(
            sections=[Section(number="13", title="Governing Law")],
            defined_terms=[
                DefinedTerm(
                    term="Unrelated Term",
                    definition_text="Something in section 13",
                    section_ref="13",
                ),
            ],
            cross_references=[],
        )
        context = _build_analysis_context(anatomy_other, intake, cluster_standard)
        assert "Unrelated Term" not in context


# ---------------------------------------------------------------------------
# 11. _check_escalation — tests for each EscalationTrigger type
# ---------------------------------------------------------------------------


class TestCheckEscalation:
    """Test _check_escalation for all EscalationTrigger variants."""

    def _finding(self, severity: Severity) -> Finding:
        return Finding(
            id="f-test",
            clause_ref="5.1",
            clause_text="test clause",
            category="test",
            severity=severity,
            description="test",
            reasoning="test",
            remediation="test",
        )

    # --- NEVER ---

    def test_never_with_no_findings(self, cluster_never_escalate):
        assert _check_escalation([], cluster_never_escalate) is False

    def test_never_with_critical_finding(self, cluster_never_escalate):
        findings = [self._finding(Severity.CRITICAL)]
        assert _check_escalation(findings, cluster_never_escalate) is False

    # --- ANY_CRITICAL ---

    def test_any_critical_with_no_findings(self, cluster_standard):
        assert _check_escalation([], cluster_standard) is False

    def test_any_critical_with_medium_finding(self, cluster_standard):
        findings = [self._finding(Severity.MEDIUM)]
        assert _check_escalation(findings, cluster_standard) is False

    def test_any_critical_with_high_finding(self, cluster_standard):
        findings = [self._finding(Severity.HIGH)]
        assert _check_escalation(findings, cluster_standard) is False

    def test_any_critical_with_critical_finding(self, cluster_standard):
        findings = [self._finding(Severity.CRITICAL)]
        assert _check_escalation(findings, cluster_standard) is True

    # --- MULTIPLE_HIGH ---

    def test_multiple_high_with_no_findings(self, cluster_multiple_high):
        assert _check_escalation([], cluster_multiple_high) is False

    def test_multiple_high_with_one_high(self, cluster_multiple_high):
        findings = [self._finding(Severity.HIGH)]
        assert _check_escalation(findings, cluster_multiple_high) is False

    def test_multiple_high_with_two_high(self, cluster_multiple_high):
        findings = [self._finding(Severity.HIGH), self._finding(Severity.HIGH)]
        assert _check_escalation(findings, cluster_multiple_high) is True

    def test_multiple_high_counts_critical_too(self, cluster_multiple_high):
        """CRITICAL counts as HIGH for MULTIPLE_HIGH trigger."""
        findings = [self._finding(Severity.HIGH), self._finding(Severity.CRITICAL)]
        assert _check_escalation(findings, cluster_multiple_high) is True

    def test_multiple_high_with_two_medium(self, cluster_multiple_high):
        findings = [self._finding(Severity.MEDIUM), self._finding(Severity.MEDIUM)]
        assert _check_escalation(findings, cluster_multiple_high) is False


# ---------------------------------------------------------------------------
# _get_section_texts — basic coverage
# ---------------------------------------------------------------------------


class TestGetSectionTexts:
    """Verify section text extraction from contract text."""

    def test_extracts_known_section(self, contract_text):
        result = _get_section_texts(contract_text, ["5"])
        assert "5" in result
        assert "INTELLECTUAL PROPERTY" in result["5"]

    def test_missing_section_returns_empty(self, contract_text):
        result = _get_section_texts(contract_text, ["99"])
        assert result.get("99") == ""

    def test_empty_contract_returns_empty_dict(self):
        assert _get_section_texts("", ["1"]) == {}

    def test_empty_sections_returns_empty_dict(self, contract_text):
        assert _get_section_texts(contract_text, []) == {}


# ---------------------------------------------------------------------------
# Escalation does not duplicate findings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalation_deduplicates_findings(
    mock_app, cluster_standard, anatomy, intake, contract_text
):
    """Escalated re-analysis does not duplicate findings already found."""
    raw = _make_raw_finding(severity="critical")
    primary_response = {
        "findings": [raw],
        "references_to_follow": [],
        "deep_dives_needed": [],
        "coverage_notes": [],
    }
    # Escalated returns same finding structure — but _parse_finding generates
    # new UUIDs, so deduplication relies on id set. Since IDs are random,
    # we verify that escalated findings with NEW ids are added.
    new_finding = _make_raw_finding(
        severity="critical", description="deeper insight"
    )
    escalated_response = {"findings": [new_finding]}

    mock_app.call.side_effect = [primary_response, escalated_response]

    result = await analyze_cluster(
        mock_app, cluster_standard, anatomy, intake, contract_text
    )

    # Both findings should appear (different UUIDs)
    assert len(result.findings) == 2
    descriptions = {f.description for f in result.findings}
    assert "Broad IP assignment" in descriptions
    assert "deeper insight" in descriptions


# ---------------------------------------------------------------------------
# MULTIPLE_HIGH escalation integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_high_escalation(
    mock_app, cluster_multiple_high, anatomy, intake, contract_text
):
    """Two HIGH findings trigger MULTIPLE_HIGH escalation."""
    primary_response = {
        "findings": [
            _make_raw_finding(severity="high", description="Liability cap too low"),
            _make_raw_finding(severity="high", description="No mutual indemnity"),
        ],
        "references_to_follow": [],
        "deep_dives_needed": [],
        "coverage_notes": [],
    }
    escalated_response = {
        "findings": [
            _make_raw_finding(severity="critical", description="Combined exposure"),
        ],
    }
    mock_app.call.side_effect = [primary_response, escalated_response]

    result = await analyze_cluster(
        mock_app, cluster_multiple_high, anatomy, intake, contract_text
    )

    assert result.depth_used == Depth.THOROUGH
    assert len(result.findings) == 3
    assert mock_app.call.call_count == 2
