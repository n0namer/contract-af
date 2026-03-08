#!/usr/bin/env python3
"""Extract data from cuad_result.json and cuad_dova_annotations.json for comparison."""

import json
from collections import Counter

with open("cuad_result.json") as f:
    result = json.load(f)

with open("../tests/fixtures/cuad_dova_annotations.json") as f:
    annotations = json.load(f)

# --- Result summary ---
findings = result["structured_json"]["findings"]
combo_risks = result["structured_json"]["combination_risks"]
adversary = result["structured_json"]["adversary_result"]
metadata = result["metadata"]

print("=" * 80)
print("CONTRACT-AF PIPELINE OUTPUT SUMMARY")
print("=" * 80)
print(f"Total findings: {metadata['total_findings']}")
print(f"Clusters analyzed: {metadata['clusters_analyzed']}")
print(f"Combination risks: {metadata['combination_risks']}")
print(f"Coverage iterations: {metadata['coverage_iterations']}")
print(f"Elapsed seconds: {metadata['elapsed_seconds']:.1f}")
print(f"Terminated early: {metadata['terminated_early']}")
print(f"Termination reason: {metadata['termination_reason']}")
print()

# Category breakdown
cats = Counter(f["category"] for f in findings)
print("FINDINGS BY CATEGORY:")
for cat, count in cats.most_common():
    print(f"  {cat}: {count}")
print()

# Severity breakdown
sevs = Counter(f["severity"] for f in findings)
print("FINDINGS BY SEVERITY:")
for sev, count in sevs.most_common():
    print(f"  {sev}: {count}")
print()

# --- CUAD annotations ---
print("=" * 80)
print("CUAD GROUND TRUTH ANNOTATIONS")
print("=" * 80)
ann = annotations["annotations"]
print(f"Total clause types annotated: {len(ann)}")
for clause_type, spans in ann.items():
    print(f"  {clause_type}: {len(spans)} annotation(s)")
print()

# --- Keyword matching ---
# Map CUAD clause types to likely contract-af finding keywords
CUAD_KEYWORDS = {
    "Affiliate License-Licensee": ["affiliate", "license", "sub-license", "sublicense"],
    "Agreement Date": ["effective date", "september 26", "agreement date"],
    "Anti-Assignment": [
        "assignment",
        "assigned",
        "transferred",
        "non-assignable",
        "non-transferable",
    ],
    "Audit Rights": ["audit", "inspection", "books of account", "records"],
    "Cap On Liability": [
        "liability",
        "limitation of liability",
        "cap",
        "shall not exceed",
        "consequential damages",
    ],
    "Change Of Control": ["change of control", "assign", "affiliate", "merger", "acquisition"],
    "Competitive Restriction Exception": [
        "competitive restriction",
        "exception",
        "notwithstanding",
        "shall not apply",
    ],
    "Covenant Not To Sue": ["contest", "impair", "diminish", "ownership", "trademarks"],
    "Document Name": ["co-promotion agreement", "promotion agreement"],
    "Effective Date": ["effective date", "september 26"],
    "Exclusivity": ["exclusive", "co-exclusive", "exclusivity", "detail and promote"],
    "Expiration Date": ["term", "anniversary", "expiration", "four (4) year", "termination"],
    "Governing Law": ["governing law", "governed by", "internal laws", "jurisdiction"],
    "Insurance": ["insurance", "products liability coverage", "comprehensive general liability"],
    "Ip Ownership Assignment": [
        "ownership",
        "assign",
        "right, title and interest",
        "goodwill",
        "inventions",
        "intellectual property",
    ],
    "License Grant": ["license", "grant", "non-exclusive right", "right to use", "co-exclusive"],
    "Liquidated Damages": [
        "liquidated damages",
        "termination",
        "consideration",
        "promotion services",
    ],
    "Minimum Commitment": [
        "minimum",
        "at least one hundred",
        "100 sales",
        "quarterly minimum",
        "sales force size",
    ],
    "No-Solicit Of Employees": [
        "solicit",
        "hire",
        "employee",
        "consultant",
        "professional personnel",
    ],
    "Non-Compete": [
        "non-compete",
        "compete",
        "shall not",
        "directly or indirectly",
        "in the territory",
    ],
    "Non-Transferable License": ["non-transferable", "non-assignable", "non-delegable"],
    "Parties": ["dova", "valeant", "party", "parties"],
    "Revenue/Profit Sharing": [
        "promotion fee",
        "net sales",
        "percentage",
        "calendar quarter",
        "fee",
        "revenue",
    ],
    "Termination For Convenience": ["terminate", "convenience", "written notice"],
    "Uncapped Liability": ["shall not limit", "third party claims", "indemnify", "uncapped"],
}

print("=" * 80)
print("CLAUSE-BY-CLAUSE COMPARISON")
print("=" * 80)

for clause_type, gt_spans in ann.items():
    print(f"\n{'─' * 70}")
    print(f"CUAD CLAUSE TYPE: {clause_type}")
    print(f"Ground Truth Annotations: {len(gt_spans)}")
    for i, span in enumerate(gt_spans[:2]):  # Show first 2 spans
        truncated = span[:150] + "..." if len(span) > 150 else span
        print(f"  GT[{i + 1}]: {truncated}")

    # Find matching findings
    keywords = CUAD_KEYWORDS.get(clause_type, [clause_type.lower().replace("_", " ").split()])
    if isinstance(keywords, list) and isinstance(keywords[0], list):
        keywords = keywords[0]

    matching = []
    for f in findings:
        text = (
            f.get("description", "")
            + " "
            + f.get("clause_text", "")
            + " "
            + f.get("reasoning", "")
            + " "
            + f.get("clause_ref", "")
        ).lower()
        for kw in keywords:
            if kw.lower() in text:
                matching.append(f)
                break

    if matching:
        # Deduplicate by id
        seen = set()
        unique = []
        for m in matching:
            if m["id"] not in seen:
                seen.add(m["id"])
                unique.append(m)
        matching = unique

        print(f"  CONTRACT-AF MATCHES: {len(matching)} finding(s)")
        # Show top 3 by confidence
        for m in sorted(matching, key=lambda x: x.get("confidence", 0), reverse=True)[:3]:
            print(
                f"    [{m['severity'].upper()}] (conf={m.get('confidence', '?')}) [{m['category']}] ref={m['clause_ref']}"
            )
            desc = m.get("description", "")[:150]
            print(f"      {desc}")
    else:
        print(f"  CONTRACT-AF MATCHES: NONE FOUND")

    print(f"  STATUS: {'✅ COVERED' if matching else '❌ NOT DIRECTLY COVERED'}")

# --- Additional risks found by contract-af ---
print(f"\n{'=' * 80}")
print("ADDITIONAL RISK CATEGORIES (Contract-AF found, not in CUAD)")
print("=" * 80)
af_categories = set(cats.keys())
cuad_mapped_categories = set()
# The contract-af categories are broader thematic clusters, not 1:1 with CUAD
for cat in sorted(af_categories):
    print(f"  {cat}: {cats[cat]} findings")

print(f"\n{'=' * 80}")
print("ADVERSARY LAYER SUMMARY")
print("=" * 80)
print(f"Exploitation scenarios: {len(adversary.get('exploitation_scenarios', []))}")
print(f"False positives identified: {len(adversary.get('false_positives', []))}")
print(f"Hidden traps: {len(adversary.get('hidden_traps', []))}")
combos = adversary.get("combination_risks", [])
print(f"Combination risks in adversary: {len(combos)}")

print(f"\n{'=' * 80}")
print("COMBINATION RISKS (Top-Level)")
print("=" * 80)
print(f"Total combination risks: {len(combo_risks)}")
for cr in combo_risks[:5]:
    desc = cr.get("combined_risk_description", cr.get("description", ""))[:200]
    refs = cr.get("finding_ids", cr.get("clause_refs", []))
    print(f"  Refs: {refs}")
    print(f"  {desc}")
    print()
