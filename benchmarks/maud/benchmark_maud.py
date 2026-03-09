"""MAUD benchmark comparison for Contract-AF.

Compares contract-af output against MAUD v1 ground-truth annotations
to compute question-level accuracy via regex/keyword matching.

Usage (from project root):
    python3 benchmarks/maud/benchmark_maud.py benchmarks/maud/results/result_kimi_v2.json
    python3 benchmarks/maud/benchmark_maud.py benchmarks/maud/results/result_kimi_v2.json benchmarks/maud/results/result_kimi.json

Requires:
    benchmarks/maud/contract_63_ground_truth.json  (ground truth, resolved automatically)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# ---------------------------------------------------------------------------
# MAUD question → keyword matchers
# ---------------------------------------------------------------------------
# Each entry: (question_key_suffix, expected_answer_summary, search_terms)
# search_terms are lowercased substrings that should appear in pipeline output
# if the system correctly identified the answer.

MAUD_QUESTIONS: list[tuple[str, str, list[str]]] = [
    # Consideration
    (
        "Type of Consideration-Answer",
        "All Cash",
        ["all cash", "$92.00", "cash", "per share merger consideration"],
    ),
    # R&W Bringdown
    (
        'Accuracy of Target "General" R&W: Bringdown Standard Answer',
        "MAE standard",
        ["mae standard", "material adverse effect", "mae"],
    ),
    (
        "Accuracy of Target Capitalization R&W (outstanding shares): Bringdown Standard Answer",
        "de minimis exception",
        ["de minimis", "de-minimis"],
    ),
    (
        "Accuracy of Fundamental Target R&Ws: Bringdown Standard",
        "Accurate in all respects",
        ["accurate in all respects", "all respects"],
    ),
    # Materiality Scrape
    (
        "Materiality/MAE Scrape applies to",
        "General R&Ws, Specified R&Ws",
        ["materiality scrape", "without giving effect", "materiality"],
    ),
    # Covenant Condition
    (
        "Compliance with Target Covenant Closing Condition-Answer",
        "Each Covenant",
        ["each covenant", "each of its obligations", "all material respects"],
    ),
    # No MAE R&W
    ('Agreement includes "Back-Door" MAE-Answer', "No", ["back-door", "backdoor"]),
    # MAE Forward Looking
    (
        "FLS (MAE) Standard-Answer",
        '"Would" (reasonably) be expected to',
        ["would reasonably be expected", "would be expected", "reasonably be expected"],
    ),
    # MAE applies to Target+Subs
    (
        "MAE applies to Target and subsidiaries (MAE)-Answer",
        "taken as a whole",
        ["taken as a whole"],
    ),
    # MAE carveouts
    (
        "General political and/or social conditions (Y/N)",
        "Yes",
        ["political", "political conditions", "social conditions"],
    ),
    (
        'General political and/or social conditions:  subject to "disproportionate impact" modifier',
        "Yes",
        ["disproportionate", "disproportionately"],
    ),
    (
        "General economic and financial conditions (Y/N)",
        "Yes",
        ["economic", "financial conditions", "financial markets"],
    ),
    (
        'General economic and financial conditions: subject to "disproportionate impact" modifier',
        "Yes",
        ["disproportionate", "disproportionately"],
    ),
    ("Changes in Target's industry (Y/N)", "Yes", ["industry", "industries in which"]),
    (
        'Change in Target\'s industry: subject to "disproportionate impact" modifier',
        "Yes",
        ["disproportionate", "disproportionately"],
    ),
    ("Change in law (Y/N)", "Yes", ["change in law", "changes in law", "change in applicable law"]),
    (
        'Change in law:  subject to "disproportionate impact" modifier',
        "Yes",
        ["disproportionate", "disproportionately"],
    ),
    (
        "Changes in GAAP or other accounting principles (Y/N)",
        "Yes",
        ["gaap", "accounting principles", "accounting standards"],
    ),
    (
        'Changes in GAAP or other accounting principles:  subject to "disproportionate impact" modifier',
        "Yes",
        ["disproportionate", "disproportionately"],
    ),
    (
        "Announcement, pendency or consummation of deal (Y/N)",
        "Yes",
        ["announcement", "pendency", "consummation"],
    ),
    (
        "Failure to meet projections (Y/N)",
        "Yes",
        ["projections", "forecasts", "estimates", "fail to meet"],
    ),
    (
        "Changes in market price/trading volume of Target's securities or credit rating (Y/N)",
        "Yes",
        ["market price", "trading volume", "credit rating", "securities"],
    ),
    (
        'War, terrorism, natural disasters, "acts of God" or force majeure-Answer (Y/N)',
        "Yes",
        ["war", "terrorism", "natural disaster", "force majeure", "acts of god"],
    ),
    (
        "Pandemic or other public health event-Answer (Y/N)",
        "Yes",
        ["pandemic", "public health", "covid"],
    ),
    (
        "Pandemic or other public health event: Specific reference to COVID-19",
        "Yes",
        ["covid-19", "covid", "coronavirus", "sars-cov"],
    ),
    (
        'Pandemic or other public health event:  subject to "disproportionate impact" modifier',
        "Yes",
        ["disproportionate", "disproportionately"],
    ),
    (
        "Actions required under transaction agreement-Answer (Y/N)",
        "Yes",
        ["required by this agreement", "expressly required", "required under"],
    ),
    (
        "Actions taken with consent or approval of Buyer-Answer (Y/N)",
        "Yes",
        ["consent", "approval of parent", "approved in writing"],
    ),
    # Knowledge
    (
        "Knowledge Definition-Answer",
        "Constructive knowledge",
        ["constructive knowledge", "reasonable inquiry", "direct reports"],
    ),
    # No-Shop
    (
        "Liability standard for no-shop breach by Target Non-D&O Representatives",
        "Strict liability",
        ["strict liability", "shall not", "shall direct", "commercially reasonable efforts"],
    ),
    # Fiduciary exception
    (
        "Fiduciary exception:  Board determination standard-Answer (no-shop)",
        '"Inconsistent" with fiduciary duties',
        ["inconsistent", "fiduciary duties", "fiduciary"],
    ),
    (
        "Fiduciary exception: Board determination trigger (no shop)-Answer",
        "Superior Offer or likely to result in",
        ["superior offer", "superior proposal", "reasonably likely", "reasonably expected"],
    ),
    # COR
    (
        "COR permitted in response to Superior Offer",
        "Yes",
        ["change of recommendation", "cor", "superior proposal", "superior offer"],
    ),
    (
        "COR permitted in response to Intervening Event",
        "Yes",
        ["intervening event", "change of recommendation"],
    ),
    # COR Matching Rights
    (
        "Initial matching rights period (COR)-Answer",
        "4 calendar days",
        [
            "ninety-six hours",
            "96 hours",
            "four calendar days",
            "4 calendar days",
            "96-hour",
            "notice period",
        ],
    ),
    (
        "Additional matching rights period for modifications (COR)-Answer",
        "3 days",
        ["three days", "3 days", "three business days", "3 business days"],
    ),
    # Superior Proposal
    ("Definition includes stock deals-Answer", ">50%", ["fifty percent", "50%", "more than fifty"]),
    # Intervening Event knowledge
    (
        "Definition contains knowledge requirement - answer",
        "Not known and not reasonably foreseeable",
        ["not reasonably foreseeable", "not foreseeable", "foreseeable"],
    ),
    # FTR
    (
        "FTR Triggers-Answer",
        "Superior Offer",
        ["superior offer", "superior proposal", "alternative acquisition"],
    ),
    # FTR matching rights
    (
        "Initial matching rights period (FTR)-Answer",
        "4 calendar days",
        ["ninety-six hours", "96 hours", "four calendar days", "4 calendar days", "notice period"],
    ),
    # Tail Period
    (
        "Tail Period Length-Answer",
        "within 12 months",
        ["twelve months", "12 months", "twelve-month", "12-month"],
    ),
    # Termination Fee
    (
        "Specific Performance-Answer",
        '"entitled to" specific performance',
        ["entitled to", "specific performance", "injunction"],
    ),
    # Antitrust
    (
        "General Antitrust Efforts Standard-Answer",
        "Commercially reasonable efforts",
        ["commercially reasonable", "reasonable efforts"],
    ),
    (
        "Limitations on Antitrust Efforts-Answer",
        "No obligation to divest",
        ["no obligation", "not be required", "no event shall", "divest", "divestiture"],
    ),
    # Ordinary course
    (
        "Ordinary course efforts standard-Answer",
        "Flat covenant (no efforts)",
        ["ordinary course", "conduct its business"],
    ),
    (
        "Buyer consent requirement (ordinary course)-Answer",
        "Not unreasonably withheld",
        ["not to be unreasonably withheld", "unreasonably withheld", "not unreasonably"],
    ),
    (
        "Ordinary Course Covenant includes carve-out for Pandemic responses-Answer (Y/N)",
        "Yes",
        ["pandemic", "covid", "public health"],
    ),
    # Negative covenant
    (
        "Buyer consent requirement (negative interim covenant)-Answer",
        "Not unreasonably withheld",
        ["not to be unreasonably withheld", "unreasonably withheld", "not unreasonably"],
    ),
]


def _normalize(text: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _flatten_result(result: dict) -> str:
    """Flatten all text fields from a contract-af result into a single searchable string."""
    parts: list[str] = []

    # Top-level text fields
    for key in ("executive_summary", "risk_report_md", "negotiation_playbook"):
        val = result.get(key, "")
        if val:
            parts.append(str(val))

    # Structured JSON
    structured = result.get("structured_json", result)

    # Findings
    for finding in structured.get("findings", []):
        for field in (
            "category",
            "description",
            "reasoning",
            "remediation",
            "clause_text",
            "clause_ref",
        ):
            val = finding.get(field, "")
            if val:
                parts.append(str(val))

    # Combination risks
    for cr in structured.get("combination_risks", []):
        for field in ("description", "investigation_result", "combined_risk_description"):
            val = cr.get(field, "")
            if val:
                parts.append(str(val))

    # Adversary result
    adversary = structured.get("adversary_result", {}) or {}
    for scenario in adversary.get("exploitation_scenarios", []):
        for field in ("scenario", "impact"):
            val = scenario.get(field, "")
            if val:
                parts.append(str(val))
    for fp in adversary.get("false_positives", []):
        for field in ("reason", "evidence"):
            val = fp.get(field, "")
            if val:
                parts.append(str(val))
    for trap in adversary.get("hidden_traps", []):
        for field in ("description", "exploitation_scenario"):
            val = trap.get(field, "")
            if val:
                parts.append(str(val))

    return _normalize(" ".join(parts))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 benchmark_maud.py <result.json> [result2.json ...]")
        sys.exit(1)

    result_paths = [Path(p) for p in sys.argv[1:]]
    gt_path = SCRIPT_DIR / "contract_63_ground_truth.json"

    for p in result_paths:
        if not p.exists():
            print(f"ERROR: result file not found: {p}")
            sys.exit(1)
    if not gt_path.exists():
        print(f"ERROR: ground truth not found: {gt_path}")
        sys.exit(1)

    with open(gt_path) as f:
        ground_truth = json.load(f)

    results: list[tuple[str, dict, str]] = []
    for rp in result_paths:
        with open(rp) as f:
            data = json.load(f)
        flat = _flatten_result(data)
        results.append((rp.name, data, flat))

    total_questions = len(MAUD_QUESTIONS)

    print("=" * 100)
    print("MAUD BENCHMARK: Contract-AF vs Ground Truth")
    print("=" * 100)
    print(f"Contract        : {ground_truth.get('contract_name', '?')}")
    print(f"Ground truth    : {gt_path}")
    print(f"Questions scored : {total_questions}")
    for name, data, _ in results:
        meta = data.get("metadata", {})
        structured = data.get("structured_json", data)
        findings = structured.get("findings", [])
        print(f"\n  {name}:")
        print(f"    Elapsed      : {meta.get('elapsed_seconds', '?')}s")
        print(f"    Findings     : {len(findings)}")
        print(f"    Clusters     : {meta.get('clusters_analyzed', '?')}")
        print(f"    Combo risks  : {meta.get('combination_risks', '?')}")

    # Score each question for each result
    all_scores: list[dict[str, bool]] = [{} for _ in results]

    print()
    print("─" * 100)

    header = f"{'MAUD Question':<65s} | {'Expected':<25s}"
    for name, _, _ in results:
        short = name[:15]
        header += f" | {short:<8s}"
    print(header)
    print("─" * 100)

    for q_key, expected, search_terms in MAUD_QUESTIONS:
        # Check ground truth has this question
        gt_answer = ground_truth.get("questions", {}).get(q_key, "")
        if gt_answer == "(None entered)":
            continue

        row = f"{q_key[:65]:<65s} | {expected[:25]:<25s}"

        for i, (name, data, flat_text) in enumerate(results):
            matched = any(term in flat_text for term in search_terms)
            all_scores[i][q_key] = matched
            symbol = "✓" if matched else "✗"
            row += f" | {symbol:<8s}"

        print(row)

    # Summary
    print()
    print("=" * 100)
    print("SCORE SUMMARY")
    print("=" * 100)

    scored_questions = [
        q
        for q, _, _ in MAUD_QUESTIONS
        if ground_truth.get("questions", {}).get(q, "") != "(None entered)"
    ]
    total_scored = len(scored_questions)

    for i, (name, data, _) in enumerate(results):
        answered = sum(1 for q in scored_questions if all_scores[i].get(q, False))
        missed = total_scored - answered
        pct = answered / total_scored * 100 if total_scored else 0
        print(f"\n  {name}:")
        print(f"    Answered : {answered}/{total_scored} ({pct:.0f}%)")
        print(f"    Missed   : {missed}/{total_scored}")

        # List missed questions
        missed_qs = [q for q in scored_questions if not all_scores[i].get(q, False)]
        if missed_qs:
            print(f"    Missed questions:")
            for mq in missed_qs:
                expected = next((e for k, e, _ in MAUD_QUESTIONS if k == mq), "?")
                print(f"      ✗ {mq}: {expected}")

    # Write machine-readable results
    benchmark_out = {
        "benchmark": "MAUD v1 (Collectors Universe)",
        "contract": ground_truth.get("contract_name", "?"),
        "total_questions_scored": total_scored,
        "results": {},
    }
    for i, (name, _, _) in enumerate(results):
        answered = sum(1 for q in scored_questions if all_scores[i].get(q, False))
        benchmark_out["results"][name] = {
            "answered": answered,
            "total": total_scored,
            "accuracy": round(answered / total_scored, 4) if total_scored else 0,
            "missed": [q for q in scored_questions if not all_scores[i].get(q, False)],
        }

    out_path = SCRIPT_DIR / "results" / "benchmark_scores.json"
    with open(out_path, "w") as f:
        json.dump(benchmark_out, f, indent=2)
    print(f"\nScores written to: {out_path}")

    print()
    print("=" * 100)
    for i, (name, _, _) in enumerate(results):
        answered = sum(1 for q in scored_questions if all_scores[i].get(q, False))
        pct = answered / total_scored * 100 if total_scored else 0
        print(f"FINAL: {name} → {answered}/{total_scored} ({pct:.0f}%)")
    print("=" * 100)


if __name__ == "__main__":
    main()
