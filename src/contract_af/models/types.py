"""Data models for all Contract-AF pipeline phases."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# === Enums ===


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Depth(str, Enum):
    SCAN = "scan"
    STANDARD = "standard"
    THOROUGH = "thorough"


class EscalationTrigger(str, Enum):
    ANY_CRITICAL = "any_critical_finding"
    MULTIPLE_HIGH = "multiple_high"
    NEVER = "never"


# === Phase 1: Intake ===


class Party(BaseModel):
    name: str
    role: str  # "provider", "customer", "employer", "employee", etc.
    entity_type: str  # "corporation", "llc", "individual", etc.


class IntakeResult(BaseModel):
    contract_type: str  # "saas_agreement", "employment", "nda", "safe", etc.
    parties: list[Party]
    your_role: str  # which party you are
    jurisdiction: str  # "California, USA", "England & Wales", etc.
    governing_law: str
    deal_structure: str  # one-line summary
    complexity: str  # "simple", "standard", "complex"
    confident: bool  # did .ai() get enough signal from first pages?


# === Phase 2: Anatomy ===


class Section(BaseModel):
    number: str  # "1", "1.1", "5.3(a)"
    title: str
    page_range: tuple[int, int] | None = None
    subsections: list[str] = Field(default_factory=list)


class DefinedTerm(BaseModel):
    term: str  # "Work Product", "Confidential Information"
    definition_text: str
    section_ref: str  # where defined
    usage_count: int = 0


class CrossRef(BaseModel):
    from_section: str
    to_section: str
    relationship_type: str  # "references", "subject_to", "as_defined_in", "notwithstanding"


class Exhibit(BaseModel):
    label: str  # "Exhibit A", "Schedule 1"
    title: str
    pages: tuple[int, int] | None = None
    modifies_sections: list[str] = Field(default_factory=list)


class KeyDate(BaseModel):
    date: str
    description: str
    section_ref: str


class RiskSignal(BaseModel):
    section: str
    signal_type: str  # "heavy_cross_refs", "broad_definition", "unusual_length", "nested_conditions"
    description: str
    severity: Severity = Severity.MEDIUM


class AnatomyResult(BaseModel):
    sections: list[Section]
    defined_terms: list[DefinedTerm]
    cross_references: list[CrossRef]
    exhibits: list[Exhibit] = Field(default_factory=list)
    key_dates: list[KeyDate] = Field(default_factory=list)
    risk_surface: list[RiskSignal] = Field(default_factory=list)


# === Phase 3: Analysis Plan ===


class ClauseCluster(BaseModel):
    name: str  # "ip_work_product", "liability_indemnity", etc.
    sections: list[str]  # assigned section numbers
    initial_depth: Depth
    escalation_trigger: EscalationTrigger
    escalated_depth: Depth = Depth.THOROUGH
    jurisdiction_rules: list[str] = Field(default_factory=list)
    priority: int = 0


class AnalysisPlan(BaseModel):
    clusters: list[ClauseCluster]
    skipped_sections: list[str] = Field(default_factory=list)  # boilerplate
    unassigned_sections: list[str] = Field(default_factory=list)
    jurisdiction_rules: list[str] = Field(default_factory=list)


# === Phase 4: Findings ===


class Finding(BaseModel):
    id: str
    clause_ref: str  # section number
    clause_text: str  # actual clause text
    category: str  # "ip", "liability", "non_compete", etc.
    severity: Severity
    description: str  # rich text description (string per archei rules)
    reasoning: str  # why this is a risk
    remediation: str  # what to do about it
    confidence: float = 1.0  # 0.0-1.0


class ClauseAnalysisResult(BaseModel):
    findings: list[Finding]
    sections_analyzed: list[str]
    sections_followed: list[str] = Field(default_factory=list)  # out-of-scope refs followed
    sub_agents_spawned: int = 0
    depth_used: Depth = Depth.STANDARD
    early_exit: bool = False
    coverage_notes: list[str] = Field(default_factory=list)


# === Phase 5: Review Layer ===


class FalsePositive(BaseModel):
    finding_id: str
    reason: str
    evidence: str


class HiddenTrap(BaseModel):
    clause_refs: list[str]
    description: str
    exploitation_scenario: str
    severity: Severity


class Exploitation(BaseModel):
    finding_id: str
    scenario: str  # how opposing party would use this clause
    impact: str


class AdversaryResult(BaseModel):
    false_positives: list[FalsePositive] = Field(default_factory=list)
    hidden_traps: list[HiddenTrap] = Field(default_factory=list)
    exploitation_scenarios: list[Exploitation] = Field(default_factory=list)
    uncovered_sections_with_traps: list[str] = Field(default_factory=list)


class CombinationRisk(BaseModel):
    clause_refs: list[str]
    description: str
    severity: Severity
    investigation_result: str  # rich text from deep-dive sub-agent


class GapResult(BaseModel):
    missing_clauses: list[str]  # clause types expected but not found
    verified_absent: list[str]  # confirmed not in document under any name
    found_elsewhere: list[dict[str, str]] = Field(default_factory=list)  # [{expected, actual_section}]


# === Phase 5.5: Coverage ===


class CoverageAssessment(BaseModel):
    is_sufficient: bool
    coverage_ratio: float  # 0.0-1.0
    sections_to_analyze: list[str] = Field(default_factory=list)
    sections_to_deepen: list[str] = Field(default_factory=list)
    iteration: int = 0  # max 2


# === Phase 6: Synthesis ===


class RankedFinding(BaseModel):
    finding: Finding
    composite_score: float
    rank: int
    negotiation_strategy: str  # rich text: what to ask, counter, fallback


class NegotiationPlan(BaseModel):
    priorities: list[str]  # ordered list of negotiation priorities
    fallback_positions: list[str]
    deal_breakers: list[str]


class RiskProfile(BaseModel):
    overall_risk: Severity
    category_scores: dict[str, float]  # {"ip": 8.5, "liability": 6.2, ...}
    deal_recommendation: str  # "proceed_with_changes", "high_risk_review", "walk_away"


class SynthesisResult(BaseModel):
    findings: list[RankedFinding]
    negotiation_strategy: NegotiationPlan
    overall_risk_profile: RiskProfile
    executive_summary: str  # string per archei rules (consumed by Report Writer LLM)


# === Phase 7: Report ===


class ContractReport(BaseModel):
    executive_summary: str
    risk_report_md: str  # full markdown report
    negotiation_playbook: str  # per-finding negotiation language
    structured_json: dict  # API-friendly output
    metadata: dict = Field(default_factory=dict)  # cost, timing, agent count, etc.
