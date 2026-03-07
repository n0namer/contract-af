"""Clause analyst agent — analyzes a single ClauseCluster with adaptive depth.

Uses .harness() for document navigation, reference following, and meta-prompting.
Implements the inner control loop with budget caps per the architecture guide.
"""

from __future__ import annotations

import asyncio
import re
import uuid

from contract_af.models import (
    AnatomyResult,
    ClauseAnalysisResult,
    ClauseCluster,
    Depth,
    EscalationTrigger,
    Finding,
    IntakeResult,
    Severity,
)

MAX_REF_FOLLOWS = 3
MAX_SUB_AGENTS = 2


async def analyze_cluster(
    app,
    cluster: ClauseCluster,
    anatomy: AnatomyResult,
    intake: IntakeResult,
    contract_text: str,
    findings_queue: asyncio.Queue | None = None,
) -> ClauseAnalysisResult:
    """Analyze a clause cluster with inner loop adaptation.

    Dispatches a .harness() call to analyze assigned sections, then adaptively
    follows references, escalates depth on trigger, and spawns sub-agents for
    complex discoveries (meta-prompting pattern).
    """
    findings: list[Finding] = []
    sections_followed: list[str] = []
    sub_agents_spawned = 0
    ref_follows = 0
    depth_used = cluster.initial_depth

    # Get section texts for this cluster
    section_texts = _get_section_texts(contract_text, cluster.sections)

    # Build context from anatomy (string per archei rules — LLM consumes this)
    context = _build_analysis_context(anatomy, intake, cluster)

    # Primary analysis via harness
    result = await app.call(
        "contract-af.clause_analyst",
        input={
            "sections": section_texts,
            "context": context,
            "depth": depth_used.value,
            "cluster_name": cluster.name,
            "jurisdiction_rules": cluster.jurisdiction_rules,
        },
    )

    # Parse findings from harness response
    raw_findings = result.get("findings", []) if isinstance(result, dict) else []
    for rf in raw_findings:
        finding = _parse_finding(rf, cluster.name)
        findings.append(finding)
        if findings_queue is not None:
            await findings_queue.put(finding)

    # --- Inner loop: follow out-of-scope references ---
    refs_to_follow = (
        result.get("references_to_follow", []) if isinstance(result, dict) else []
    )
    for ref in refs_to_follow[:MAX_REF_FOLLOWS]:
        ref_text = _get_section_texts(contract_text, [ref])
        if not ref_text:
            continue

        sections_followed.append(ref)
        ref_follows += 1

        ref_result = await app.call(
            "contract-af.clause_analyst",
            input={
                "sections": ref_text,
                "context": (
                    f"Following reference from {cluster.name} analysis. "
                    f"Original finding context: {context}"
                ),
                "depth": "standard",
                "cluster_name": cluster.name,
            },
        )
        ref_findings = (
            ref_result.get("findings", []) if isinstance(ref_result, dict) else []
        )
        for rf in ref_findings:
            finding = _parse_finding(rf, cluster.name)
            findings.append(finding)
            if findings_queue is not None:
                await findings_queue.put(finding)

    # --- Escalation check ---
    should_escalate = _check_escalation(findings, cluster)
    if should_escalate and depth_used != cluster.escalated_depth:
        depth_used = cluster.escalated_depth

        escalated = await app.call(
            "contract-af.clause_analyst",
            input={
                "sections": section_texts,
                "context": (
                    f"ESCALATED ANALYSIS at {depth_used.value} depth. "
                    f"Previous findings: {[f.description for f in findings]}"
                ),
                "depth": depth_used.value,
                "cluster_name": cluster.name,
            },
        )
        esc_findings = (
            escalated.get("findings", []) if isinstance(escalated, dict) else []
        )
        existing_ids = {f.id for f in findings}
        for rf in esc_findings:
            finding = _parse_finding(rf, cluster.name)
            if finding.id not in existing_ids:
                findings.append(finding)
                if findings_queue is not None:
                    await findings_queue.put(finding)

    # --- Meta-prompting: spawn sub-agents for complex discoveries ---
    deep_dives = (
        result.get("deep_dives_needed", []) if isinstance(result, dict) else []
    )
    for dive in deep_dives[:MAX_SUB_AGENTS]:
        sub_agents_spawned += 1
        dive_result = await app.call(
            "contract-af.definition_impact_analyzer",
            input={
                "prompt": dive.get("prompt", ""),
                "sections": dive.get("sections", []),
                "contract_text": contract_text,
            },
        )
        dive_findings = (
            dive_result.get("findings", []) if isinstance(dive_result, dict) else []
        )
        for rf in dive_findings:
            finding = _parse_finding(rf, cluster.name)
            findings.append(finding)
            if findings_queue is not None:
                await findings_queue.put(finding)

    # Early exit: no findings from a cluster with 3+ sections
    early_exit = len(findings) == 0 and len(cluster.sections) >= 3

    return ClauseAnalysisResult(
        findings=findings,
        sections_analyzed=cluster.sections,
        sections_followed=sections_followed,
        sub_agents_spawned=sub_agents_spawned,
        depth_used=depth_used,
        early_exit=early_exit,
        coverage_notes=(
            result.get("coverage_notes", []) if isinstance(result, dict) else []
        ),
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _parse_finding(raw: dict, category: str) -> Finding:
    """Parse a raw finding dict into a Finding model."""
    return Finding(
        id=f"f-{uuid.uuid4().hex[:8]}",
        clause_ref=raw.get("clause_ref", ""),
        clause_text=raw.get("clause_text", ""),
        category=category,
        severity=Severity(raw.get("severity", "medium")),
        description=raw.get("description", ""),
        reasoning=raw.get("reasoning", ""),
        remediation=raw.get("remediation", ""),
        confidence=raw.get("confidence", 0.8),
    )


def _get_section_texts(
    contract_text: str, section_numbers: list[str]
) -> dict[str, str]:
    """Extract section text by section number from the contract.

    Uses a regex-based approach to locate section headings like:
      "1. Title", "1.1 Title", "Section 5.3(a)" etc.
    Returns a mapping of section number -> extracted text.
    Sections without a match return empty strings (defensive).
    """
    if not contract_text or not section_numbers:
        return {}

    result: dict[str, str] = {}

    for section_num in section_numbers:
        escaped = re.escape(section_num)
        # Match patterns: "1. Title", "1.1 Title", "Section 1.1", "SECTION 1.1"
        pattern = (
            rf"(?:^|\n)"
            rf"(?:(?:Section|SECTION|Article|ARTICLE)\s+)?"
            rf"({escaped})"
            rf"[\.\s\)]"
        )
        match = re.search(pattern, contract_text)
        if match is None:
            result[section_num] = ""
            continue

        start = match.start()

        # Find next section heading to bound the extraction
        next_section = re.search(
            r"\n(?:(?:Section|SECTION|Article|ARTICLE)\s+)?\d+[\.\s\)]",
            contract_text[match.end() :],
        )
        if next_section is not None:
            end = match.end() + next_section.start()
        else:
            end = len(contract_text)

        result[section_num] = contract_text[start:end].strip()

    return result


def _build_analysis_context(
    anatomy: AnatomyResult,
    intake: IntakeResult,
    cluster: ClauseCluster,
) -> str:
    """Build a natural-language context string for the clause analyst harness.

    Per archei rules: data consumed by an LLM agent flows as a string,
    not structured JSON.
    """
    parts: list[str] = []

    # Contract overview
    parts.append(
        f"Contract type: {intake.contract_type}. "
        f"Parties: {', '.join(p.name + ' (' + p.role + ')' for p in intake.parties)}. "
        f"Your role: {intake.your_role}. "
        f"Jurisdiction: {intake.jurisdiction}. "
        f"Governing law: {intake.governing_law}. "
        f"Complexity: {intake.complexity}."
    )

    # Relevant defined terms
    cluster_sections_set = set(cluster.sections)
    relevant_terms = [
        dt
        for dt in anatomy.defined_terms
        if dt.section_ref in cluster_sections_set
    ]
    if relevant_terms:
        term_lines = [
            f'  - "{dt.term}" (defined in {dt.section_ref}): {dt.definition_text}'
            for dt in relevant_terms
        ]
        parts.append("Relevant defined terms:\n" + "\n".join(term_lines))

    # Cross-references touching this cluster
    relevant_xrefs = [
        cr
        for cr in anatomy.cross_references
        if cr.from_section in cluster_sections_set
        or cr.to_section in cluster_sections_set
    ]
    if relevant_xrefs:
        xref_lines = [
            f"  - {cr.from_section} -> {cr.to_section} ({cr.relationship_type})"
            for cr in relevant_xrefs
        ]
        parts.append("Cross-references:\n" + "\n".join(xref_lines))

    # Risk signals from anatomy
    relevant_risks = [
        rs for rs in anatomy.risk_surface if rs.section in cluster_sections_set
    ]
    if relevant_risks:
        risk_lines = [
            f"  - {rs.section}: {rs.signal_type} — {rs.description}"
            for rs in relevant_risks
        ]
        parts.append("Risk signals from anatomy:\n" + "\n".join(risk_lines))

    # Jurisdiction-specific rules
    if cluster.jurisdiction_rules:
        parts.append(
            "Jurisdiction-specific rules:\n"
            + "\n".join(f"  - {r}" for r in cluster.jurisdiction_rules)
        )

    return "\n\n".join(parts)


def _check_escalation(findings: list[Finding], cluster: ClauseCluster) -> bool:
    """Check whether the escalation trigger for this cluster is met."""
    trigger = cluster.escalation_trigger

    if trigger == EscalationTrigger.NEVER:
        return False

    if trigger == EscalationTrigger.ANY_CRITICAL:
        return any(f.severity == Severity.CRITICAL for f in findings)

    if trigger == EscalationTrigger.MULTIPLE_HIGH:
        high_count = sum(
            1
            for f in findings
            if f.severity in (Severity.HIGH, Severity.CRITICAL)
        )
        return high_count >= 2

    return False
