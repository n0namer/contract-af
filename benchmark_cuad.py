"""CUAD benchmark comparison for Contract-AF.

Compares contract-af output against CUAD v1 ground-truth annotations
to compute clause-type-level precision, recall, and F1.

Usage:
    python3 benchmark_cuad.py exampl/cuad_result.json

Requires:
    tests/fixtures/cuad_dova_annotations.json  (ground truth)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# CUAD clause type → contract-af category mapping
# ---------------------------------------------------------------------------
# CUAD uses specific clause type names; contract-af uses free-form categories.
# We map CUAD types to likely contract-af category keywords for fuzzy matching.

CUAD_TO_AF_KEYWORDS: dict[str, list[str]] = {
    "Affiliate License-Licensee": ["license", "affiliate", "sublicense"],
    "Agreement Date": ["date", "effective", "agreement date"],
    "Anti-Assignment": ["assignment", "anti-assignment", "transfer", "non-transferable"],
    "Audit Rights": ["audit", "inspection", "review rights"],
    "Cap On Liability": [
        "liability cap",
        "limitation of liability",
        "cap on liability",
        "damages cap",
    ],
    "Change Of Control": ["change of control", "acquisition", "merger"],
    "Competitive Restriction Exception": [
        "competitive",
        "non-compete exception",
        "restriction exception",
    ],
    "Covenant Not To Sue": ["covenant", "not to sue", "non-contest"],
    "Document Name": ["document name", "agreement title"],
    "Effective Date": ["effective date", "commencement"],
    "Exclusivity": ["exclusivity", "exclusive", "co-exclusive"],
    "Expiration Date": ["expiration", "term", "duration", "termination date"],
    "Governing Law": ["governing law", "jurisdiction", "applicable law", "choice of law"],
    "Insurance": ["insurance", "coverage", "liability insurance"],
    "Ip Ownership Assignment": [
        "ip ownership",
        "intellectual property",
        "ip assignment",
        "work product",
    ],
    "License Grant": ["license grant", "license", "right to use"],
    "Liquidated Damages": ["liquidated damages", "penalty", "termination fee"],
    "Minimum Commitment": ["minimum commitment", "minimum", "sales force", "quarterly minimum"],
    "No-Solicit Of Employees": ["non-solicitation", "no-solicit", "employee solicitation"],
    "Non-Compete": ["non-compete", "competitive restriction", "restrictive covenant"],
    "Non-Transferable License": ["non-transferable", "transfer restriction"],
    "Parties": ["parties", "party", "counterpart"],
    "Revenue/Profit Sharing": [
        "revenue sharing",
        "profit sharing",
        "promotion fee",
        "royalty",
        "compensation",
    ],
    "Termination For Convenience": [
        "termination for convenience",
        "terminate for convenience",
        "voluntary termination",
    ],
    "Uncapped Liability": ["uncapped liability", "unlimited liability", "no cap"],
}


def _normalize(text: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _match_finding_to_cuad(finding: dict, cuad_types: list[str]) -> list[str]:
    """Return CUAD clause types that this finding likely covers."""
    matched: list[str] = []
    cat = _normalize(finding.get("category", ""))
    desc = _normalize(finding.get("description", ""))
    clause_ref = _normalize(finding.get("clause_ref", ""))
    reasoning = _normalize(finding.get("reasoning", ""))
    combined = f"{cat} {desc} {clause_ref} {reasoning}"

    for cuad_type in cuad_types:
        keywords = CUAD_TO_AF_KEYWORDS.get(cuad_type, [])
        for kw in keywords:
            if kw.lower() in combined:
                matched.append(cuad_type)
                break  # one keyword match is enough for this type

    return matched


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 benchmark_cuad.py <result.json>")
        sys.exit(1)

    result_path = Path(sys.argv[1])
    annotations_path = Path("tests/fixtures/cuad_dova_annotations.json")

    if not result_path.exists():
        print(f"ERROR: result file not found: {result_path}")
        sys.exit(1)
    if not annotations_path.exists():
        print(f"ERROR: annotations file not found: {annotations_path}")
        sys.exit(1)

    # Load data
    with open(result_path) as f:
        result = json.load(f)
    with open(annotations_path) as f:
        annotations = json.load(f)

    cuad_types = list(annotations["annotations"].keys())
    total_annotated = len(cuad_types)

    # Extract findings from contract-af output
    structured = result.get("structured_json", result)
    findings = structured.get("findings", [])

    print("=" * 70)
    print("CUAD BENCHMARK: Contract-AF vs Ground Truth")
    print("=" * 70)
    print(f"Ground truth clause types : {total_annotated}")
    print(f"Contract-AF findings      : {len(findings)}")
    print()

    if not findings:
        print("NO FINDINGS — Contract-AF returned 0 findings.")
        print("Precision: N/A | Recall: 0.00 | F1: 0.00")
        print()
        print("All CUAD clause types are MISSED:")
        for ct in cuad_types:
            spans = annotations["annotations"][ct]
            print(f"  ✗ {ct} ({len(spans)} annotation(s))")
        sys.exit(0)

    # Match findings → CUAD types
    detected_cuad_types: set[str] = set()
    finding_matches: list[tuple[dict, list[str]]] = []

    for finding in findings:
        matches = _match_finding_to_cuad(finding, cuad_types)
        finding_matches.append((finding, matches))
        detected_cuad_types.update(matches)

    # Compute metrics
    true_positives = len(detected_cuad_types)
    false_negatives = total_annotated - true_positives
    # False positives = findings that don't match any CUAD type
    unmatched_findings = [f for f, m in finding_matches if not m]
    false_positives = len(unmatched_findings)

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0
    )
    recall = true_positives / total_annotated if total_annotated > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print("─" * 70)
    print("METRICS (clause-type level)")
    print("─" * 70)
    print(f"  True Positives  (CUAD types detected)     : {true_positives}/{total_annotated}")
    print(f"  False Negatives (CUAD types missed)        : {false_negatives}")
    print(f"  False Positives (findings w/o CUAD match)  : {false_positives}")
    print()
    print(f"  Precision : {precision:.2%}")
    print(f"  Recall    : {recall:.2%}")
    print(f"  F1 Score  : {f1:.2%}")
    print()

    # Detail: which CUAD types were detected
    print("─" * 70)
    print("CUAD CLAUSE TYPE COVERAGE")
    print("─" * 70)
    for ct in cuad_types:
        spans = annotations["annotations"][ct]
        status = "✓" if ct in detected_cuad_types else "✗"
        print(f"  {status} {ct:<40s} ({len(spans)} annotation(s))")

    # Detail: finding → CUAD mapping
    print()
    print("─" * 70)
    print("FINDING → CUAD MAPPING")
    print("─" * 70)
    for i, (finding, matches) in enumerate(finding_matches, 1):
        cat = finding.get("category", "?")
        sev = finding.get("severity", "?")
        ref = finding.get("clause_ref", "?")
        match_str = ", ".join(matches) if matches else "(no CUAD match)"
        print(f"  [{i:2d}] {sev:<8s} | {cat:<35s} | ref={ref}")
        print(f"       → {match_str}")

    # Unmatched findings
    if unmatched_findings:
        print()
        print("─" * 70)
        print(f"UNMATCHED FINDINGS ({len(unmatched_findings)} — not in CUAD ground truth)")
        print("─" * 70)
        for f in unmatched_findings:
            print(f"  • {f.get('category', '?')}: {f.get('description', '?')[:100]}")

    # Summary
    print()
    print("=" * 70)
    print(
        f"FINAL: P={precision:.2%}  R={recall:.2%}  F1={f1:.2%}  "
        f"({true_positives}/{total_annotated} CUAD types detected, "
        f"{len(findings)} total findings)"
    )
    print("=" * 70)

    # Write machine-readable results
    benchmark_out = {
        "benchmark": "CUAD v1 (Dova Promotion Agreement)",
        "ground_truth_types": total_annotated,
        "contract_af_findings": len(findings),
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "false_positives": false_positives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "detected_types": sorted(detected_cuad_types),
        "missed_types": sorted(set(cuad_types) - detected_cuad_types),
    }
    out_path = result_path.parent / "cuad_benchmark_scores.json"
    with open(out_path, "w") as f:
        json.dump(benchmark_out, f, indent=2)
    print(f"\nScores written to: {out_path}")


if __name__ == "__main__":
    main()
