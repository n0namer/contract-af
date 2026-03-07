"""Tests for Phase 3: Analysis planner (create_analysis_plan)."""

from __future__ import annotations

import pytest

from contract_af.agents.planner import create_analysis_plan
from contract_af.models import (
    AnalysisPlan,
    AnatomyResult,
    ClauseCluster,
    CrossRef,
    DefinedTerm,
    Depth,
    EscalationTrigger,
    IntakeResult,
    Party,
    RiskSignal,
    Section,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers
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
        deal_structure="SaaS subscription for project management platform",
        complexity="standard",
        confident=True,
    )


def _make_anatomy(
    section_numbers: list[str] | None = None,
) -> AnatomyResult:
    numbers = section_numbers or ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
    return AnatomyResult(
        sections=[
            Section(number=n, title=f"Section {n}") for n in numbers
        ],
        defined_terms=[
            DefinedTerm(
                term="Customer Data",
                definition_text="All data submitted by Customer",
                section_ref="1",
                usage_count=5,
            ),
            DefinedTerm(
                term="Work Product",
                definition_text="Any inventions conceived during the Term",
                section_ref="1",
                usage_count=3,
            ),
        ],
        cross_references=[
            CrossRef(
                from_section="5",
                to_section="1",
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


def _make_plan(
    *,
    cluster_sections: list[list[str]] | None = None,
    skipped: list[str] | None = None,
) -> AnalysisPlan:
    """Build an AnalysisPlan from section groupings."""
    sections = cluster_sections or [["1", "2"], ["3", "4", "5"], ["6", "7", "8"]]
    clusters = [
        ClauseCluster(
            name=f"cluster_{i}",
            sections=secs,
            initial_depth=Depth.STANDARD,
            escalation_trigger=EscalationTrigger.ANY_CRITICAL,
            priority=len(sections) - i,
        )
        for i, secs in enumerate(sections)
    ]
    return AnalysisPlan(
        clusters=clusters,
        skipped_sections=skipped or [],
        unassigned_sections=[],
    )


# ---------------------------------------------------------------------------
# Happy path — all sections assigned
# ---------------------------------------------------------------------------


async def test_happy_path_all_sections_assigned(mock_app):
    """When .ai() assigns all sections to clusters, unassigned_sections is empty."""
    intake = _make_intake()
    anatomy = _make_anatomy(["1", "2", "3", "4", "5"])
    plan = _make_plan(
        cluster_sections=[["1", "2", "3"], ["4", "5"]],
        skipped=[],
    )
    mock_app.ai.return_value = plan

    result = await create_analysis_plan(mock_app, intake, anatomy)

    assert isinstance(result, AnalysisPlan)
    assert result.unassigned_sections == []
    assert len(result.clusters) == 2

    # Verify all anatomy sections are covered
    assigned = set()
    for cluster in result.clusters:
        assigned.update(cluster.sections)
    assert assigned == {"1", "2", "3", "4", "5"}


# ---------------------------------------------------------------------------
# Unassigned sections computed
# ---------------------------------------------------------------------------


async def test_unassigned_sections_filled_in(mock_app):
    """When .ai() doesn't assign all sections, unassigned_sections is computed."""
    intake = _make_intake()
    anatomy = _make_anatomy(["1", "2", "3", "4", "5", "6"])

    # Plan only covers sections 1-4, leaves 5 and 6 unassigned
    plan = _make_plan(
        cluster_sections=[["1", "2"], ["3", "4"]],
        skipped=[],
    )
    mock_app.ai.return_value = plan

    result = await create_analysis_plan(mock_app, intake, anatomy)

    assert result.unassigned_sections == ["5", "6"]


async def test_unassigned_accounts_for_skipped(mock_app):
    """Skipped sections are not counted as unassigned."""
    intake = _make_intake()
    anatomy = _make_anatomy(["1", "2", "3", "4", "5", "6"])

    # Sections 1-4 in clusters, section 5 skipped, section 6 unassigned
    plan = _make_plan(
        cluster_sections=[["1", "2"], ["3", "4"]],
        skipped=["5"],
    )
    mock_app.ai.return_value = plan

    result = await create_analysis_plan(mock_app, intake, anatomy)

    assert result.unassigned_sections == ["6"]
    assert "5" not in result.unassigned_sections


# ---------------------------------------------------------------------------
# Skipped sections tracked
# ---------------------------------------------------------------------------


async def test_skipped_sections_preserved(mock_app):
    """Boilerplate sections marked as skipped are preserved in the output."""
    intake = _make_intake()
    anatomy = _make_anatomy(["1", "2", "3", "13", "14", "15"])

    plan = _make_plan(
        cluster_sections=[["1", "2", "3"]],
        skipped=["13", "14", "15"],
    )
    mock_app.ai.return_value = plan

    result = await create_analysis_plan(mock_app, intake, anatomy)

    assert sorted(result.skipped_sections) == ["13", "14", "15"]
    assert result.unassigned_sections == []


# ---------------------------------------------------------------------------
# Immutability — original plan not mutated
# ---------------------------------------------------------------------------


async def test_plan_immutability(mock_app):
    """create_analysis_plan returns a new plan; the .ai() result is not mutated."""
    intake = _make_intake()
    anatomy = _make_anatomy(["1", "2", "3", "4"])

    original_plan = _make_plan(
        cluster_sections=[["1", "2"]],
        skipped=[],
    )
    mock_app.ai.return_value = original_plan

    result = await create_analysis_plan(mock_app, intake, anatomy)

    # The returned plan has unassigned sections filled in
    assert result.unassigned_sections == ["3", "4"]
    # The original plan object was NOT mutated (immutable update via model_copy)
    assert original_plan.unassigned_sections == []
