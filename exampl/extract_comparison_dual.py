#!/usr/bin/env python3
"""Extract and compare dual Contract-AF result runs.

This script compares two run outputs (Kimi and Gemini by default) and prints:
- Pipeline execution metrics
- Finding quality and duplication metrics
- Output completeness metrics
- Category and CUAD clause-type coverage
- Adversarial analysis quality metrics
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


CUAD_KEYWORDS: dict[str, list[str]] = {
    "Affiliate License-Licensee": ["affiliate", "license", "sub-license", "sublicense"],
    "Agreement Date": ["effective date", "agreement date", "september 26"],
    "Anti-Assignment": ["assignment", "assigned", "transferred", "non-assignable"],
    "Audit Rights": ["audit", "inspection", "books", "records"],
    "Cap On Liability": ["liability", "limitation of liability", "consequential damages"],
    "Change Of Control": ["change of control", "affiliate", "merger", "acquisition"],
    "Competitive Restriction Exception": ["restriction", "exception", "notwithstanding"],
    "Covenant Not To Sue": ["contest", "impair", "ownership", "trademarks"],
    "Document Name": ["co-promotion agreement", "promotion agreement"],
    "Effective Date": ["effective date", "september 26"],
    "Exclusivity": ["exclusive", "co-exclusive", "exclusivity"],
    "Expiration Date": ["term", "anniversary", "expiration", "termination"],
    "Governing Law": ["governing law", "governed by", "jurisdiction"],
    "Insurance": ["insurance", "products liability", "comprehensive general liability"],
    "Ip Ownership Assignment": [
        "ownership",
        "assign",
        "right, title and interest",
        "intellectual property",
    ],
    "License Grant": ["license", "grant", "right to use", "non-exclusive"],
    "Liquidated Damages": ["liquidated damages", "promotion services"],
    "Minimum Commitment": ["minimum", "sales representatives", "quarterly minimum"],
    "No-Solicit Of Employees": ["solicit", "hire", "employee", "consultant"],
    "Non-Compete": ["non-compete", "compete", "in the territory"],
    "Non-Transferable License": ["non-transferable", "non-assignable", "non-delegable"],
    "Parties": ["dova", "valeant", "party", "parties"],
    "Revenue/Profit Sharing": ["promotion fee", "net sales", "calendar quarter", "fee"],
    "Termination For Convenience": ["terminate", "convenience", "written notice"],
    "Uncapped Liability": ["shall not limit", "third party claims", "indemnify", "uncapped"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dual-model Contract-AF comparison extractor")
    parser.add_argument(
        "--model-a-path",
        default="cuad_result_kimi-k2.5.json",
        help="Path to model A result JSON (default: Kimi result)",
    )
    parser.add_argument(
        "--model-a-name",
        default="Kimi-K2.5",
        help="Display name for model A",
    )
    parser.add_argument(
        "--model-b-path",
        default="cuad_result_gemini-3-flash-preview.json",
        help="Path to model B result JSON (default: Gemini result)",
    )
    parser.add_argument(
        "--model-b-name",
        default="Gemini-3-Flash-Preview",
        help="Display name for model B",
    )
    parser.add_argument(
        "--cuad-annotations-path",
        default="../tests/fixtures/cuad_dova_annotations.json",
        help="Path to CUAD ground truth annotation JSON",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_populated(value: Any) -> bool:
    return bool(norm_text(value))


def count_words(value: Any) -> int:
    text = norm_text(value)
    if not text:
        return 0
    return len(re.findall(r"\S+", text))


def finding_blob(finding: dict[str, Any]) -> str:
    fields = [
        finding.get("category", ""),
        finding.get("description", ""),
        finding.get("reasoning", ""),
        finding.get("remediation", ""),
        finding.get("clause_text", ""),
        finding.get("clause_ref", ""),
    ]
    return " ".join(norm_text(field).lower() for field in fields)


def looks_stub_finding(finding: dict[str, Any]) -> bool:
    description = norm_text(finding.get("description"))
    reasoning = norm_text(finding.get("reasoning"))
    remediation = norm_text(finding.get("remediation"))
    clause_text = norm_text(finding.get("clause_text"))
    has_any_body = any([description, reasoning, remediation, clause_text])

    if not has_any_body:
        return True

    if description and len(description) < 20 and not reasoning and not remediation:
        return True

    return False


def severity_breakdown(findings: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for finding in findings:
        severity = norm_text(finding.get("severity", "unknown")).lower() or "unknown"
        counts[severity] += 1
    return counts


def confidence_stats(findings: list[dict[str, Any]]) -> tuple[int, float]:
    values: list[float] = []
    for finding in findings:
        confidence = finding.get("confidence")
        if isinstance(confidence, (int, float)):
            values.append(float(confidence))
    return len(values), (mean(values) if values else 0.0)


def duplication_stats(findings: list[dict[str, Any]]) -> tuple[int, int, list[tuple[str, int]]]:
    desc_counter: Counter[str] = Counter()
    desc_ref_counter: Counter[str] = Counter()

    for finding in findings:
        desc = re.sub(r"\s+", " ", norm_text(finding.get("description")).lower())
        ref = re.sub(r"\s+", " ", norm_text(finding.get("clause_ref")).lower())
        if desc:
            desc_counter[desc] += 1
        key = f"{desc}@@{ref}"
        if desc or ref:
            desc_ref_counter[key] += 1

    repeated_desc = sum(count - 1 for count in desc_counter.values() if count > 1)
    repeated_desc_ref = sum(count - 1 for count in desc_ref_counter.values() if count > 1)
    top_repeats = [(text, count) for text, count in desc_counter.most_common(8) if count > 1]
    return repeated_desc, repeated_desc_ref, top_repeats


def cuad_coverage(
    findings: list[dict[str, Any]], annotations: dict[str, list[str]]
) -> tuple[int, int, list[str]]:
    matched: list[str] = []
    for clause_type in annotations:
        keywords = CUAD_KEYWORDS.get(clause_type, [clause_type.lower()])
        found = False
        for finding in findings:
            blob = finding_blob(finding)
            if any(keyword.lower() in blob for keyword in keywords):
                found = True
                break
        if found:
            matched.append(clause_type)
    return len(matched), len(annotations), sorted(matched)


def annotation_span_quote_coverage(
    findings: list[dict[str, Any]], annotations: dict[str, list[str]]
) -> tuple[int, int, float]:
    span_total = 0
    span_hit = 0

    lower_clauses: list[str] = [
        norm_text(finding.get("clause_text")).lower() for finding in findings
    ]
    lower_blobs: list[str] = [finding_blob(finding) for finding in findings]

    for spans in annotations.values():
        for span in spans:
            text = norm_text(span)
            if not text:
                continue
            span_total += 1
            probe = text.lower()[:80]
            if any(probe and probe in clause for clause in lower_clauses) or any(
                probe and probe in blob for blob in lower_blobs
            ):
                span_hit += 1

    rate = (span_hit / span_total * 100.0) if span_total else 0.0
    return span_hit, span_total, rate


def adversary_metrics(result: dict[str, Any]) -> dict[str, Any]:
    adversary = result.get("structured_json", {}).get("adversary_result", {}) or {}
    scenarios = adversary.get("exploitation_scenarios", []) or []
    false_positives = adversary.get("false_positives", []) or []
    hidden_traps = adversary.get("hidden_traps", []) or []
    adversary_combos = adversary.get("combination_risks", []) or []

    scenario_populated = sum(
        1
        for item in scenarios
        if is_populated(item.get("scenario")) and is_populated(item.get("impact"))
    )
    trap_populated = sum(
        1
        for item in hidden_traps
        if is_populated(item.get("description")) and is_populated(item.get("exploitation_scenario"))
    )
    fp_populated = sum(
        1
        for item in false_positives
        if is_populated(item.get("reason")) and is_populated(item.get("evidence"))
    )

    scenario_words = [
        count_words(item.get("scenario"))
        for item in scenarios
        if is_populated(item.get("scenario"))
    ]
    impact_words = [
        count_words(item.get("impact")) for item in scenarios if is_populated(item.get("impact"))
    ]
    fp_words = [
        count_words(item.get("reason"))
        for item in false_positives
        if is_populated(item.get("reason"))
    ]

    return {
        "scenarios_total": len(scenarios),
        "scenarios_populated": scenario_populated,
        "false_positives_total": len(false_positives),
        "false_positives_populated": fp_populated,
        "hidden_traps_total": len(hidden_traps),
        "hidden_traps_populated": trap_populated,
        "adversary_combo_risks": len(adversary_combos),
        "avg_scenario_words": mean(scenario_words) if scenario_words else 0.0,
        "avg_impact_words": mean(impact_words) if impact_words else 0.0,
        "avg_false_positive_reason_words": mean(fp_words) if fp_words else 0.0,
    }


def compute_metrics(result: dict[str, Any], annotations: dict[str, list[str]]) -> dict[str, Any]:
    metadata = result.get("metadata", {}) or {}
    structured = result.get("structured_json", {}) or {}
    findings = structured.get("findings", []) or []
    combination_risks = structured.get("combination_risks", []) or []

    stub_count = sum(1 for finding in findings if looks_stub_finding(finding))
    substantive_count = len(findings) - stub_count
    severity = severity_breakdown(findings)
    confidence_count, confidence_avg = confidence_stats(findings)

    with_clause_text = sum(1 for finding in findings if is_populated(finding.get("clause_text")))
    with_clause_ref = sum(1 for finding in findings if is_populated(finding.get("clause_ref")))
    with_reasoning = sum(1 for finding in findings if is_populated(finding.get("reasoning")))
    with_remediation = sum(1 for finding in findings if is_populated(finding.get("remediation")))

    repeated_desc, repeated_desc_ref, top_repeats = duplication_stats(findings)
    matched_types, total_types, matched_type_names = cuad_coverage(findings, annotations)
    span_hit, span_total, span_rate = annotation_span_quote_coverage(findings, annotations)

    elapsed_seconds = float(metadata.get("elapsed_seconds", 0.0) or 0.0)
    findings_per_minute = (len(findings) / (elapsed_seconds / 60.0)) if elapsed_seconds else 0.0

    return {
        "terminated_early": bool(metadata.get("terminated_early", False)),
        "termination_reason": norm_text(metadata.get("termination_reason")),
        "elapsed_seconds": elapsed_seconds,
        "clusters_analyzed": int(metadata.get("clusters_analyzed", 0) or 0),
        "coverage_iterations": int(metadata.get("coverage_iterations", 0) or 0),
        "metadata_combo_risks": int(metadata.get("combination_risks", 0) or 0),
        "top_level_combo_risks": len(combination_risks),
        "metadata_total_findings": int(metadata.get("total_findings", 0) or 0),
        "metadata_finding_count": int(metadata.get("finding_count", 0) or 0),
        "structured_finding_count": int(structured.get("finding_count", 0) or 0),
        "findings_count": len(findings),
        "findings_per_minute": findings_per_minute,
        "unique_categories": len(
            {
                norm_text(finding.get("category"))
                for finding in findings
                if norm_text(finding.get("category"))
            }
        ),
        "stub_count": stub_count,
        "substantive_count": substantive_count,
        "severity": dict(severity),
        "confidence_count": confidence_count,
        "confidence_avg": confidence_avg,
        "with_clause_text": with_clause_text,
        "with_clause_ref": with_clause_ref,
        "with_reasoning": with_reasoning,
        "with_remediation": with_remediation,
        "repeated_description_count": repeated_desc,
        "repeated_description_ref_count": repeated_desc_ref,
        "top_repeated_descriptions": top_repeats,
        "executive_summary_chars": len(norm_text(result.get("executive_summary"))),
        "executive_summary_words": count_words(result.get("executive_summary")),
        "risk_report_chars": len(norm_text(result.get("risk_report_md"))),
        "risk_report_words": count_words(result.get("risk_report_md")),
        "negotiation_playbook_chars": len(norm_text(result.get("negotiation_playbook"))),
        "negotiation_playbook_words": count_words(result.get("negotiation_playbook")),
        "cuad_types_matched": matched_types,
        "cuad_types_total": total_types,
        "cuad_types_coverage_pct": (matched_types / total_types * 100.0) if total_types else 0.0,
        "cuad_type_names_matched": matched_type_names,
        "annotation_spans_hit": span_hit,
        "annotation_spans_total": span_total,
        "annotation_span_hit_pct": span_rate,
        "adversary": adversary_metrics(result),
        "overall_risk": norm_text(
            metadata.get("overall_risk")
            or structured.get("overall_risk")
            or structured.get("overall_risk_profile", {}).get("overall_risk")
        ),
        "deal_recommendation": norm_text(
            structured.get("deal_recommendation")
            or structured.get("overall_risk_profile", {}).get("deal_recommendation")
        ),
    }


def fmt_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def print_table(
    title: str, rows: list[tuple[str, Any, Any]], left_name: str, right_name: str
) -> None:
    print("\n" + "=" * 106)
    print(title)
    print("=" * 106)
    label_width = max([len("Metric")] + [len(label) for label, _, _ in rows])
    left_width = max(len(left_name), 18)
    right_width = max(len(right_name), 18)
    print(f"{'Metric':<{label_width}} | {left_name:<{left_width}} | {right_name:<{right_width}}")
    print("-" * (label_width + left_width + right_width + 6))
    for label, left, right in rows:
        print(
            f"{label:<{label_width}} | {fmt_value(left):<{left_width}} | {fmt_value(right):<{right_width}}"
        )


def print_top_repeats(name: str, repeats: list[tuple[str, int]]) -> None:
    print(f"\nTop repeated descriptions ({name}):")
    if not repeats:
        print("  - none")
        return
    for text, count in repeats[:5]:
        short = text[:110] + "..." if len(text) > 110 else text
        print(f"  - x{count}: {short}")


def print_summary(
    left_name: str, right_name: str, left: dict[str, Any], right: dict[str, Any]
) -> None:
    print("\n" + "=" * 106)
    print("EXECUTIVE COMPARISON SUMMARY")
    print("=" * 106)

    faster = left_name if left["elapsed_seconds"] < right["elapsed_seconds"] else right_name
    fuller = left_name
    if (
        right["executive_summary_chars"]
        + right["risk_report_chars"]
        + right["negotiation_playbook_chars"]
        > left["executive_summary_chars"]
        + left["risk_report_chars"]
        + left["negotiation_playbook_chars"]
    ):
        fuller = right_name

    cleaner = left_name if left["stub_count"] < right["stub_count"] else right_name
    broader = left_name if left["findings_count"] > right["findings_count"] else right_name

    print(f"- Faster pipeline: {faster}")
    print(f"- More complete final deliverables: {fuller}")
    print(f"- Lower stub/noise profile: {cleaner}")
    print(f"- Greater raw finding volume: {broader}")


def main() -> None:
    args = parse_args()

    model_a_path = Path(args.model_a_path)
    model_b_path = Path(args.model_b_path)
    annotations_path = Path(args.cuad_annotations_path)

    model_a = read_json(model_a_path)
    model_b = read_json(model_b_path)
    annotations = read_json(annotations_path).get("annotations", {})

    metrics_a = compute_metrics(model_a, annotations)
    metrics_b = compute_metrics(model_b, annotations)

    print("=" * 106)
    print("DUAL MODEL COMPARISON: CONTRACT-AF RUN ANALYSIS")
    print("=" * 106)
    print(f"Model A: {args.model_a_name} ({model_a_path})")
    print(f"Model B: {args.model_b_name} ({model_b_path})")
    print(f"CUAD Ground Truth: {annotations_path}")

    print_table(
        "A) PIPELINE EXECUTION METRICS",
        [
            ("elapsed_seconds", metrics_a["elapsed_seconds"], metrics_b["elapsed_seconds"]),
            ("terminated_early", metrics_a["terminated_early"], metrics_b["terminated_early"]),
            ("clusters_analyzed", metrics_a["clusters_analyzed"], metrics_b["clusters_analyzed"]),
            (
                "coverage_iterations",
                metrics_a["coverage_iterations"],
                metrics_b["coverage_iterations"],
            ),
            (
                "metadata_combination_risks",
                metrics_a["metadata_combo_risks"],
                metrics_b["metadata_combo_risks"],
            ),
            (
                "top_level_combination_risks",
                metrics_a["top_level_combo_risks"],
                metrics_b["top_level_combo_risks"],
            ),
            ("findings_count", metrics_a["findings_count"], metrics_b["findings_count"]),
            (
                "findings_per_minute",
                metrics_a["findings_per_minute"],
                metrics_b["findings_per_minute"],
            ),
            (
                "metadata_total_findings",
                metrics_a["metadata_total_findings"],
                metrics_b["metadata_total_findings"],
            ),
            (
                "metadata_finding_count",
                metrics_a["metadata_finding_count"],
                metrics_b["metadata_finding_count"],
            ),
            (
                "structured_finding_count",
                metrics_a["structured_finding_count"],
                metrics_b["structured_finding_count"],
            ),
        ],
        args.model_a_name,
        args.model_b_name,
    )

    print_table(
        "B) FINDING QUALITY ANALYSIS",
        [
            ("substantive_count", metrics_a["substantive_count"], metrics_b["substantive_count"]),
            ("stub_count", metrics_a["stub_count"], metrics_b["stub_count"]),
            (
                "stub_rate_pct",
                (metrics_a["stub_count"] / metrics_a["findings_count"] * 100.0)
                if metrics_a["findings_count"]
                else 0.0,
                (metrics_b["stub_count"] / metrics_b["findings_count"] * 100.0)
                if metrics_b["findings_count"]
                else 0.0,
            ),
            ("confidence_count", metrics_a["confidence_count"], metrics_b["confidence_count"]),
            ("confidence_avg", metrics_a["confidence_avg"], metrics_b["confidence_avg"]),
            ("with_reasoning", metrics_a["with_reasoning"], metrics_b["with_reasoning"]),
            ("with_remediation", metrics_a["with_remediation"], metrics_b["with_remediation"]),
            ("with_clause_text", metrics_a["with_clause_text"], metrics_b["with_clause_text"]),
            ("with_clause_ref", metrics_a["with_clause_ref"], metrics_b["with_clause_ref"]),
            (
                "repeated_description_count",
                metrics_a["repeated_description_count"],
                metrics_b["repeated_description_count"],
            ),
            (
                "repeated_description_ref_count",
                metrics_a["repeated_description_ref_count"],
                metrics_b["repeated_description_ref_count"],
            ),
        ],
        args.model_a_name,
        args.model_b_name,
    )

    print_table(
        "Severity distribution (critical/high/medium/low/unknown)",
        [
            (
                "critical",
                metrics_a["severity"].get("critical", 0),
                metrics_b["severity"].get("critical", 0),
            ),
            ("high", metrics_a["severity"].get("high", 0), metrics_b["severity"].get("high", 0)),
            (
                "medium",
                metrics_a["severity"].get("medium", 0),
                metrics_b["severity"].get("medium", 0),
            ),
            ("low", metrics_a["severity"].get("low", 0), metrics_b["severity"].get("low", 0)),
            (
                "unknown",
                metrics_a["severity"].get("unknown", 0),
                metrics_b["severity"].get("unknown", 0),
            ),
        ],
        args.model_a_name,
        args.model_b_name,
    )

    print_table(
        "C) OUTPUT COMPLETENESS",
        [
            (
                "executive_summary_present",
                metrics_a["executive_summary_chars"] > 0,
                metrics_b["executive_summary_chars"] > 0,
            ),
            (
                "executive_summary_words",
                metrics_a["executive_summary_words"],
                metrics_b["executive_summary_words"],
            ),
            (
                "risk_report_present",
                metrics_a["risk_report_chars"] > 0,
                metrics_b["risk_report_chars"] > 0,
            ),
            ("risk_report_words", metrics_a["risk_report_words"], metrics_b["risk_report_words"]),
            (
                "negotiation_playbook_present",
                metrics_a["negotiation_playbook_chars"] > 0,
                metrics_b["negotiation_playbook_chars"] > 0,
            ),
            (
                "negotiation_playbook_words",
                metrics_a["negotiation_playbook_words"],
                metrics_b["negotiation_playbook_words"],
            ),
            ("overall_risk", metrics_a["overall_risk"], metrics_b["overall_risk"]),
            (
                "deal_recommendation",
                metrics_a["deal_recommendation"],
                metrics_b["deal_recommendation"],
            ),
        ],
        args.model_a_name,
        args.model_b_name,
    )

    print_table(
        "D) CATEGORY + CUAD 25-TYPE COVERAGE",
        [
            ("unique_categories", metrics_a["unique_categories"], metrics_b["unique_categories"]),
            (
                "cuad_types_matched",
                metrics_a["cuad_types_matched"],
                metrics_b["cuad_types_matched"],
            ),
            ("cuad_types_total", metrics_a["cuad_types_total"], metrics_b["cuad_types_total"]),
            (
                "cuad_types_coverage_pct",
                metrics_a["cuad_types_coverage_pct"],
                metrics_b["cuad_types_coverage_pct"],
            ),
            (
                "annotation_span_quote_hits",
                metrics_a["annotation_spans_hit"],
                metrics_b["annotation_spans_hit"],
            ),
            (
                "annotation_span_quote_total",
                metrics_a["annotation_spans_total"],
                metrics_b["annotation_spans_total"],
            ),
            (
                "annotation_span_quote_hit_pct",
                metrics_a["annotation_span_hit_pct"],
                metrics_b["annotation_span_hit_pct"],
            ),
        ],
        args.model_a_name,
        args.model_b_name,
    )

    print_table(
        "E) ADVERSARIAL ANALYSIS QUALITY",
        [
            (
                "exploitation_scenarios_total",
                metrics_a["adversary"]["scenarios_total"],
                metrics_b["adversary"]["scenarios_total"],
            ),
            (
                "exploitation_scenarios_populated",
                metrics_a["adversary"]["scenarios_populated"],
                metrics_b["adversary"]["scenarios_populated"],
            ),
            (
                "false_positives_total",
                metrics_a["adversary"]["false_positives_total"],
                metrics_b["adversary"]["false_positives_total"],
            ),
            (
                "false_positives_populated",
                metrics_a["adversary"]["false_positives_populated"],
                metrics_b["adversary"]["false_positives_populated"],
            ),
            (
                "hidden_traps_total",
                metrics_a["adversary"]["hidden_traps_total"],
                metrics_b["adversary"]["hidden_traps_total"],
            ),
            (
                "hidden_traps_populated",
                metrics_a["adversary"]["hidden_traps_populated"],
                metrics_b["adversary"]["hidden_traps_populated"],
            ),
            (
                "adversary_combination_risks",
                metrics_a["adversary"]["adversary_combo_risks"],
                metrics_b["adversary"]["adversary_combo_risks"],
            ),
            (
                "avg_scenario_words",
                metrics_a["adversary"]["avg_scenario_words"],
                metrics_b["adversary"]["avg_scenario_words"],
            ),
            (
                "avg_impact_words",
                metrics_a["adversary"]["avg_impact_words"],
                metrics_b["adversary"]["avg_impact_words"],
            ),
            (
                "avg_false_positive_reason_words",
                metrics_a["adversary"]["avg_false_positive_reason_words"],
                metrics_b["adversary"]["avg_false_positive_reason_words"],
            ),
        ],
        args.model_a_name,
        args.model_b_name,
    )

    print(f"\n{args.model_a_name} matched CUAD types:")
    print("  " + ", ".join(metrics_a["cuad_type_names_matched"]))
    print(f"\n{args.model_b_name} matched CUAD types:")
    print("  " + ", ".join(metrics_b["cuad_type_names_matched"]))

    print_top_repeats(args.model_a_name, metrics_a["top_repeated_descriptions"])
    print_top_repeats(args.model_b_name, metrics_b["top_repeated_descriptions"])

    if metrics_a["termination_reason"] or metrics_b["termination_reason"]:
        print("\nTermination notes:")
        print(f"  - {args.model_a_name}: {metrics_a['termination_reason'] or 'none'}")
        print(f"  - {args.model_b_name}: {metrics_b['termination_reason'] or 'none'}")

    print_summary(args.model_a_name, args.model_b_name, metrics_a, metrics_b)


if __name__ == "__main__":
    main()
