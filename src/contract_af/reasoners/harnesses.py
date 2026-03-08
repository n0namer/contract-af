"""Individual harness/AI reasoner wrappers — called by agent implementations."""

from __future__ import annotations

import json as _json
from typing import Any

from pydantic import BaseModel, Field

from . import router

_runtime_router: Any = router


_MAX_CONTRACT_CHARS = 30_000  # ~7500 tokens — fits .ai() context comfortably


def _truncate(text: str, limit: int = _MAX_CONTRACT_CHARS) -> str:
    """Truncate long text for .ai() calls to avoid context overflow."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n\n[... middle truncated for context limit ...]\n\n" + text[-half:]


def _to_dict(result: Any, default: dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, BaseModel):
        return result.model_dump()
    if isinstance(result, dict):
        return result
    return default


@router.reasoner()
async def intake_harness(
    document: str,
    partial_intake: dict[str, Any],
    user_context: str = "",
) -> dict[str, Any]:
    """Deep intake classification when .ai() lacks confidence."""

    class IntakeHarnessResult(BaseModel):
        contract_type: str
        parties: list[dict[str, Any]] = Field(default_factory=list)
        your_role: str = ""
        jurisdiction: str = ""
        governing_law: str = ""
        deal_structure: str = ""
        complexity: str = "standard"
        confident: bool = True

    prompt = (
        "You are a senior legal intake analyst performing deep classification.\n\n"
        "A quick-pass classifier was unable to confidently classify this contract. "
        "You now have the FULL contract text. Your job:\n"
        "1. Read the full document to identify contract_type, all parties, jurisdiction, "
        "governing_law, and deal_structure.\n"
        "2. Resolve every uncertain field from the partial_intake provided.\n"
        "3. Set confident=true — you have the complete document, so you SHOULD be able "
        "to determine all fields. Only set confident=false if the document is genuinely "
        "unreadable or is not actually a contract.\n\n"
        "IMPORTANT: Do NOT copy confident=false from the partial_intake. "
        "Re-evaluate confidence based on your own full-document analysis."
    )

    result = await _runtime_router.ai(
        system=prompt,
        user=_json.dumps(
            {
                "document": _truncate(document),
                "partial_intake": partial_intake,
                "user_context": user_context,
            },
            default=str,
        ),
        schema=IntakeHarnessResult,
    )
    return _to_dict(result, partial_intake)


@router.reasoner()
async def anatomist(
    document_text: str,
    intake: dict[str, Any],
    reason: str = "",
) -> dict[str, Any]:
    """AI-driven structural parsing of the full contract document."""

    class AnatomistResult(BaseModel):
        sections: list[dict[str, Any]] = Field(default_factory=list)
        defined_terms: list[dict[str, Any]] = Field(default_factory=list)
        cross_references: list[dict[str, Any]] = Field(default_factory=list)
        exhibits: list[dict[str, Any]] = Field(default_factory=list)
        key_dates: list[dict[str, Any]] = Field(default_factory=list)
        risk_surface: list[dict[str, Any]] = Field(default_factory=list)

    result = await _runtime_router.ai(
        system=(
            "You are a contract anatomist. Parse the FULL document and extract its "
            "complete structural map.\n\n"
            "Extract ALL of the following:\n\n"
            "1. sections — every section and article header:\n"
            "   {number: '1', title: 'DEFINITIONS', subsections: ['1.1', '1.2']}\n"
            "   Include ALL levels (articles, major sections, subsections).\n"
            "   Wire subsections to their parent via the subsections array.\n\n"
            "2. defined_terms — every defined term (quoted capitalized phrases):\n"
            "   {term: 'Affiliate', definition_text: 'means...', "
            "section_ref: '1.1', usage_count: 5}\n\n"
            "3. cross_references — inter-section references:\n"
            "   {from_section: '13.1', to_section: '1.1', "
            "relationship_type: 'as_defined_in'}\n"
            "   Types: as_defined_in, subject_to, notwithstanding, references\n\n"
            "4. exhibits — schedules, appendices, annexes:\n"
            "   {label: 'Exhibit A', title: 'Statement of Work', "
            "modifies_sections: ['3', '4']}\n\n"
            "5. key_dates — effective dates, term lengths, renewal dates:\n"
            "   {date: 'November 17, 2021', description: 'Effective Date', "
            "section_ref: 'preamble'}\n\n"
            "6. risk_surface — structural risk signals:\n"
            "   {section: '13', signal_type: 'heavy_cross_refs', "
            "description: '...', severity: 'high'}\n"
            "   signal_type: heavy_cross_refs, broad_definition, unusual_length, "
            "nested_conditions\n"
            "   severity: critical, high, medium, low\n\n"
            "Be EXHAUSTIVE with sections and defined terms. "
            "Every section header in the document must appear in your output."
        ),
        user=_json.dumps(
            {
                "document_text": document_text,
                "intake": intake,
            },
            default=str,
        ),
        schema=AnatomistResult,
    )
    return _to_dict(
        result,
        {
            "sections": [],
            "defined_terms": [],
            "cross_references": [],
            "exhibits": [],
            "key_dates": [],
            "risk_surface": [],
        },
    )


@router.reasoner()
async def clause_analyst(
    sections: dict[str, str],
    context: str,
    depth: str,
    cluster_name: str,
    jurisdiction_rules: list[str] | None = None,
) -> dict[str, Any]:
    """Analyze clause sections for risks."""

    class ClauseAnalysis(BaseModel):
        findings: list[dict[str, Any]] = Field(default_factory=list)
        references_to_follow: list[str] = Field(default_factory=list)
        deep_dives_needed: list[dict[str, Any]] = Field(default_factory=list)
        coverage_notes: list[str] = Field(default_factory=list)

    result = await _runtime_router.ai(
        system=(
            "You are a senior legal contract risk analyst. Analyze the provided clause "
            "sections for:\n"
            "- One-sided or unfavorable terms\n"
            "- Missing standard protections (liability caps, IP ownership, termination rights)\n"
            "- Broad or ambiguous language that creates exposure\n"
            "- Unusual obligations or restrictions\n"
            "- Liability and indemnification risks\n"
            "- Data protection and confidentiality gaps\n\n"
            "For EACH risk found, return a finding with:\n"
            "  clause_ref: the section number where the risk appears\n"
            "  clause_text: the exact problematic clause text (quote it)\n"
            "  severity: critical|high|medium|low\n"
            "  description: what the risk is\n"
            "  reasoning: why this is problematic\n"
            "  remediation: recommended fix or negotiation position\n"
            "  confidence: 0.0-1.0\n\n"
            "You MUST report at least one finding per section if ANY risk exists. "
            "Do NOT return empty findings unless the sections are truly risk-free boilerplate."
        ),
        user=_json.dumps(
            {
                "sections": sections,
                "context": context,
                "depth": depth,
                "cluster_name": cluster_name,
                "jurisdiction_rules": jurisdiction_rules or [],
            },
            default=str,
        ),
        schema=ClauseAnalysis,
    )
    return _to_dict(
        result,
        {
            "findings": [],
            "references_to_follow": [],
            "deep_dives_needed": [],
            "coverage_notes": [],
        },
    )


@router.reasoner()
async def definition_impact_analyzer(
    prompt: str,
    sections: list[str],
    contract_text: str,
) -> dict[str, Any]:
    """Deep-dive on definition impacts (meta-prompting target)."""

    class DefinitionImpact(BaseModel):
        findings: list[dict[str, Any]] = Field(default_factory=list)

    result = await _runtime_router.ai(
        system=(
            "You are a legal definition-impact specialist. Evaluate how defined terms "
            "change obligations, scope, and risk outcomes in the provided sections."
        ),
        user=_json.dumps(
            {
                "prompt": prompt,
                "sections": sections,
                "contract_text": _truncate(contract_text),
            },
            default=str,
        ),
        schema=DefinitionImpact,
    )
    return _to_dict(result, {"findings": []})


@router.reasoner()
async def adversary_reviewer(
    finding: dict[str, Any] | None = None,
    contract_type: str = "",
    opposing_role: str = "",
    contract_text: str = "",
    prompt: str = "",
    survival_sections: list[str] | None = None,
) -> dict[str, Any]:
    """Review from opposing party's perspective."""

    class AdversaryReview(BaseModel):
        is_false_positive: bool = False
        false_positive_reason: str = ""
        evidence: str = ""
        exploitation_scenario: str = ""
        impact: str = ""
        hidden_traps: list[dict[str, Any]] = Field(default_factory=list)
        uncovered_sections_with_traps: list[str] = Field(default_factory=list)

    result = await _runtime_router.ai(
        system=(
            "You are an adversarial contract reviewer acting for the opposing party. "
            "Identify false positives, exploit paths, and hidden traps that can be used "
            "against the user's role."
        ),
        user=_json.dumps(
            {
                "finding": finding,
                "contract_type": contract_type,
                "opposing_role": opposing_role,
                "contract_text": _truncate(contract_text),
                "prompt": prompt,
                "survival_sections": survival_sections or [],
            },
            default=str,
        ),
        schema=AdversaryReview,
    )
    return _to_dict(
        result,
        {
            "is_false_positive": False,
            "false_positive_reason": "",
            "evidence": "",
            "exploitation_scenario": "",
            "impact": "",
            "hidden_traps": [],
            "uncovered_sections_with_traps": [],
        },
    )


@router.reasoner()
async def cross_ref_resolver(
    finding_a: dict[str, Any],
    finding_b: dict[str, Any],
    cross_references: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check cross-clause interactions between a pair of findings."""

    class CrossRefInteraction(BaseModel):
        has_interaction: bool = False
        severity: str = "high"
        description: str = ""
        investigation: str = ""
        deep_dive_prompt: str = ""

    result = await _runtime_router.ai(
        system=(
            "You are a cross-clause interaction analyst. Determine whether two findings "
            "interact to create additive or compounding legal risk."
        ),
        user=_json.dumps(
            {
                "finding_a": finding_a,
                "finding_b": finding_b,
                "cross_references": cross_references,
            },
            default=str,
        ),
        schema=CrossRefInteraction,
    )
    return _to_dict(result, {"has_interaction": False})


@router.reasoner()
async def combination_deep_dive(
    prompt: str,
    sections: list[str],
    contract_text: str,
) -> dict[str, Any]:
    """Deep-dive on critical clause combinations."""

    class CombinationDive(BaseModel):
        findings: list[dict[str, Any]] = Field(default_factory=list)

    result = await _runtime_router.ai(
        system=(
            "You are a legal combination-risk specialist. Investigate interactions among "
            "the referenced sections and return concrete combined-risk findings."
        ),
        user=_json.dumps(
            {
                "prompt": prompt,
                "sections": sections,
                "contract_text": _truncate(contract_text),
            },
            default=str,
        ),
        schema=CombinationDive,
    )
    return _to_dict(result, {"findings": []})


@router.reasoner()
async def gap_analyst(
    clause_type: str,
    aliases: list[str],
    contract_text: str,
    existing_sections: list[str],
) -> dict[str, Any]:
    """Verify clause absence in contract."""

    class GapVerification(BaseModel):
        found: bool = False
        found_in: str = ""

    result = await _runtime_router.ai(
        system=(
            "You are a contract completeness analyst. Verify whether the expected clause type "
            "is present under an alternate heading or genuinely absent."
        ),
        user=_json.dumps(
            {
                "clause_type": clause_type,
                "aliases": aliases,
                "existing_sections": existing_sections,
                "contract_text": _truncate(contract_text),
            },
            default=str,
        ),
        schema=GapVerification,
    )
    return _to_dict(result, {"found": False, "found_in": ""})


@router.reasoner()
async def risk_synthesizer(
    task: str = "",
    finding_description: str = "",
    clause_text: str = "",
    severity: str = "",
    jurisdiction: str = "",
    top_findings: list[dict[str, Any]] | None = None,
    overall_risk: str = "",
    finding_count: int = 0,
    top_risks: list[str] | None = None,
    recommendation: str = "",
) -> dict[str, Any]:
    """Generate negotiation strategies and summaries."""

    class NegotiationStrategyResult(BaseModel):
        strategy: str = ""

    class NegotiationPlanResult(BaseModel):
        priorities: list[str] = Field(default_factory=list)
        fallback_positions: list[str] = Field(default_factory=list)
        deal_breakers: list[str] = Field(default_factory=list)

    class ExecutiveSummaryResult(BaseModel):
        summary: str = ""

    payload = {
        "task": task,
        "finding_description": finding_description,
        "clause_text": clause_text,
        "severity": severity,
        "jurisdiction": jurisdiction,
        "top_findings": top_findings or [],
        "overall_risk": overall_risk,
        "finding_count": finding_count,
        "top_risks": top_risks or [],
        "recommendation": recommendation,
    }

    if task == "generate_negotiation_strategy":
        result = await _runtime_router.ai(
            system="Write concise negotiation strategy language for a specific finding.",
            user=_json.dumps(payload, default=str),
            schema=NegotiationStrategyResult,
        )
        return _to_dict(result, {"strategy": ""})

    if task == "generate_negotiation_plan":
        result = await _runtime_router.ai(
            system="Generate an ordered negotiation plan with priorities, fallback positions, and deal breakers.",
            user=_json.dumps(payload, default=str),
            schema=NegotiationPlanResult,
        )
        return _to_dict(result, {"priorities": [], "fallback_positions": [], "deal_breakers": []})

    if task == "generate_executive_summary":
        result = await _runtime_router.ai(
            system="Generate an executive summary of contract risk and recommendation.",
            user=_json.dumps(payload, default=str),
            schema=ExecutiveSummaryResult,
        )
        return _to_dict(result, {"summary": ""})

    return {}


@router.reasoner()
async def report_writer(
    task: str = "",
    executive_summary: str = "",
    findings: list[dict[str, Any]] | None = None,
    risk_profile: dict[str, Any] | None = None,
    contract_type: str = "",
    parties: list[dict[str, Any]] | None = None,
    negotiation_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate markdown reports and playbooks."""

    class MarkdownResult(BaseModel):
        markdown: str = ""

    class PlaybookResult(BaseModel):
        playbook: str = ""

    payload = {
        "task": task,
        "executive_summary": executive_summary,
        "findings": findings or [],
        "risk_profile": risk_profile or {},
        "contract_type": contract_type,
        "parties": parties or [],
        "negotiation_plan": negotiation_plan or {},
    }

    if task == "generate_markdown_report":
        result = await _runtime_router.ai(
            system=(
                "You are a legal report writer. Produce a structured markdown contract risk report "
                "with sections for summary, findings, and recommended actions."
            ),
            user=_json.dumps(payload, default=str),
            schema=MarkdownResult,
        )
        return _to_dict(result, {"markdown": ""})

    if task == "generate_negotiation_playbook":
        result = await _runtime_router.ai(
            system=(
                "You are a legal negotiator. Generate a practical negotiation playbook with "
                "talk tracks, fallback positions, and sequencing guidance."
            ),
            user=_json.dumps(payload, default=str),
            schema=PlaybookResult,
        )
        return _to_dict(result, {"playbook": ""})

    return {}
