"""Phase 3: Analysis planning with .ai().

Takes the intake classification and document anatomy, then produces an
AnalysisPlan that groups sections into thematic clusters with assigned
analysis depth and escalation triggers.
"""

from __future__ import annotations

from typing import Any

from contract_af.models import AnalysisPlan, AnatomyResult, IntakeResult

PLANNER_PROMPT = """Given this contract's structure and classification, create an analysis plan.
Group sections into thematic clusters. Assign analysis depth based on risk signals.
Set escalation triggers for high-risk clusters. Mark boilerplate as skipped."""


async def create_analysis_plan(
    app: Any,
    intake: IntakeResult,
    anatomy: AnatomyResult,
) -> AnalysisPlan:
    """Create an analysis plan from intake classification and anatomy.

    Parameters
    ----------
    app:
        AgentField application instance exposing ``.ai()``.
    intake:
        Phase 1 classification result.
    anatomy:
        Phase 2 document anatomy result.

    Returns
    -------
    AnalysisPlan
        Cluster assignments, skipped sections, and unassigned sections.
    """
    import json as _json

    plan: AnalysisPlan = await app.ai(
        system=PLANNER_PROMPT,
        user=_json.dumps(
            {
                "intake": intake.model_dump(),
                "anatomy": anatomy.model_dump(),
            },
            default=str,
        ),
        schema=AnalysisPlan,
    )

    # Validate: every section must be accounted for (assigned or skipped).
    all_section_numbers = {s.number for s in anatomy.sections}

    assigned: set[str] = set()
    for cluster in plan.clusters:
        assigned.update(cluster.sections)
    assigned.update(plan.skipped_sections)

    # Immutable update: create a new plan with unassigned sections filled in.
    unassigned = sorted(all_section_numbers - assigned)
    plan = plan.model_copy(update={"unassigned_sections": unassigned})

    return plan
