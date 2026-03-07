"""Contract-AF agent implementations."""

from contract_af.agents.adversary import SENTINEL, review_as_adversary
from contract_af.agents.anatomy import analyze_structure
from contract_af.agents.clause_analyst import analyze_cluster
from contract_af.agents.coverage import assess_coverage
from contract_af.agents.cross_ref import resolve_cross_references
from contract_af.agents.gap_analyst import analyze_gaps
from contract_af.agents.intake import classify_contract
from contract_af.agents.planner import create_analysis_plan
from contract_af.agents.report_writer import generate_report
from contract_af.agents.synthesizer import synthesize_findings

__all__ = [
    "SENTINEL",
    "analyze_cluster",
    "analyze_gaps",
    "analyze_structure",
    "assess_coverage",
    "classify_contract",
    "create_analysis_plan",
    "generate_report",
    "resolve_cross_references",
    "review_as_adversary",
    "synthesize_findings",
]
