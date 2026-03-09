# MAUD Benchmark: LLM Judge Evaluation

**Contract:** Collectors Universe, Inc. / Investment Group (Merger Agreement)  
**Benchmark:** MAUD v1 (ABA 2021 Public Target Deal Points Study)  
**Ground Truth:** 69 scorable questions (from 129 total annotations)  
**Judge:** Claude Opus 4 (acting as LLM judge)  
**Date:** 2026-03-08

---

## Scoring Methodology

Per MAUD question, each run is scored 0-3:

- **3 (Full):** Correct answer explicitly stated or clearly derivable with specific clause-level support.
- **2 (Partial):** Directionally correct and on-topic, but missing MAUD-critical specificity.
- **1 (Mentioned):** Topic discussed but vague, speculative, incomplete, or mismatched to the exact MAUD datapoint.
- **0 (Absent):** No usable answer to the exact MAUD question.

Important judge rule used here: these outputs are risk-finding reports (not direct MAUD extraction outputs), so many scores are 1 when a topic is discussed but the exact MAUD label is not directly answered.

## Executive Summary

Kimi K2.5 v1 is the strongest of the three on MAUD-style issue spotting coverage, but still weak on precise MAUD datapoint extraction. It covers most MAE/no-shop/fiduciary-out themes, yet often as negotiation advice or missing-text caveats rather than direct answers. Kimi K2.5 v2 is narrower and more speculative, with lower practical answerability despite many findings. Gemini 3 Flash completes but is dominated by structural "coverage gap" findings, leading to very low MAUD answer precision. Overall winner: **Kimi v1** on coverage and usable signal; none of the three is strong as a direct MAUD extractor without a targeted answer-normalization layer.

## Overall Scores

| Metric | Kimi K2.5 v1 | Kimi K2.5 v2 | Gemini 3 Flash |
|--------|-------------:|-------------:|---------------:|
| Total Score (out of 207) | 79 | 39 | 15 |
| Full Answers (3) | 0 | 0 | 0 |
| Partial Answers (2) | 20 | 0 | 0 |
| Mentioned Only (1) | 39 | 39 | 15 |
| Absent (0) | 10 | 30 | 54 |
| Coverage % (score >= 1) | 85.5% | 56.5% | 21.7% |
| Accuracy % (score >= 2) | 29.0% | 0.0% | 0.0% |

---

## Per-Question Evaluation

### Category: Deal Consideration, Bringdown, and MAE Core (Q1-Q11)

| # | Question | Expected Answer | Kimi v1 | Kimi v2 | Gemini | Notes |
|---|---|---|---:|---:|---:|---|
| 1 | Type of Consideration | All Cash | 0 | 0 | 0 | No run explicitly identifies "All Cash" / $92.00 consideration. |
| 2 | General R&W Bringdown Timing | At Closing Only | 1 | 0 | 0 | v1 discusses closing bringdown mechanics generally (e.g., Findings 55/171), but not exact timing label. |
| 3 | General R&W Bringdown Standard | MAE standard | 1 | 1 | 0 | v1/v2 repeatedly discuss MAE-qualified bringdown; neither gives explicit MAUD phrasing. |
| 4 | Cap R&W Bringdown Standard | Accurate in all respects w/ de minimis exception | 1 | 1 | 0 | v1/v2 mention capitalization bringdown and de minimis concepts but not exact rule. |
| 5 | Fundamental R&Ws Bringdown | Accurate in all respects | 1 | 1 | 0 | Both Kimi runs discuss fundamental reps as stricter than general reps; still advisory not extractive. |
| 6 | Materiality/MAE Scrape Applies To | General R&Ws + Specified R&Ws only | 1 | 0 | 0 | v1 mentions materiality scrapes and bringdown structure; not scoped exactly to MAUD answer set. |
| 7 | MAE includes ability to consummate? | No | 1 | 1 | 0 | v1/v2 discuss consummation/closing-ability framing under MAE but not explicit yes/no resolution. |
| 8 | Ability-to-consummate subject to carveouts? | No | 1 | 1 | 0 | Mentioned in Kimi narratives around MAE/termination mechanics; still inferential. |
| 9 | MAE references "prospects"? | No | 0 | 0 | 0 | No explicit prospects analysis in any run. |
| 10 | MAE forward-looking standard? | Yes | 1 | 1 | 0 | v1/v2 use forward-looking MAE risk language but do not explicitly label this MAUD datapoint. |
| 11 | FLS (MAE) applies to | business and operation of Target | 1 | 1 | 0 | Both Kimi runs discuss business/operations scope; still not direct MAUD extraction. |

### Category: MAE Carveouts and Pandemic/Disproportionate Impact (Q12-Q42)

| # | Question | Expected Answer | Kimi v1 | Kimi v2 | Gemini | Notes |
|---|---|---|---:|---:|---:|---|
| 12 | General political/social conditions | Yes | 2 | 1 | 0 | v1 explicitly discusses standard carveout sets including political conditions (Findings 30/132). |
| 13 | Political/social subject to dispro impact | Yes | 2 | 1 | 0 | v1 repeatedly references disproportionality in MAE carveouts (Finding 1). |
| 14 | General economic/financial conditions | Yes | 2 | 1 | 0 | v1 states macroeconomic carveouts in proposed MAE language (Finding 30). |
| 15 | Economic/financial subject to dispro impact | Yes | 2 | 1 | 0 | v1 mentions disproportionate effect qualifier on macro carveouts (Findings 1/30). |
| 16 | Industry changes | Yes | 2 | 1 | 0 | v1 includes industry-wide changes in carveout discussion (Findings 30/132). |
| 17 | Industry changes subject to dispro impact | Yes | 2 | 1 | 0 | v1 directly addresses disproportionate-effect structure. |
| 18 | Change in law | Yes | 2 | 1 | 0 | v1 lists changes in law among carveouts (Finding 30). |
| 19 | Change in law subject to dispro impact | Yes | 2 | 1 | 0 | v1 associates dispro qualifier with carveouts generally. |
| 20 | GAAP/accounting changes | Yes | 2 | 1 | 0 | v1 includes GAAP changes in MAE carveout proposals (Finding 30). |
| 21 | GAAP changes subject to dispro impact | Yes | 1 | 0 | 0 | v1 mentions dispro broadly, but GAAP+dispro link is not explicit in final finding text. |
| 22 | Announcement/pendency/consummation | Yes | 1 | 0 | 0 | v1 touches signing/pendency effects but not explicit APC carveout extraction. |
| 23 | APC subject to dispro impact | No | 1 | 0 | 0 | v1 references APC concept but does not clearly resolve dispro=no. |
| 24 | Failure to meet projections | Yes | 2 | 1 | 0 | v1 explicitly lists failures to meet projections in MAE carveout set (Finding 30). |
| 25 | Failure to meet projections subject to dispro impact | No | 1 | 0 | 0 | Mentioned only at high level; no exact MAUD polarity. |
| 26 | Market price/trading volume/credit rating | Yes | 1 | 0 | 0 | v1 discusses market-condition effects but not this exact securities metric. |
| 27 | Securities/credit rating subject to dispro impact | No | 1 | 0 | 0 | Same: directional mention only. |
| 28 | War/terrorism/acts of God | Yes | 2 | 0 | 1 | v1 includes war/terrorism in carveout set; Gemini mentions acts-of-God in covenant caveat. |
| 29 | Pandemic/public health event | Yes | 2 | 1 | 1 | v1 explicit pandemic carveout language; v2/gemini mention pandemic as risk context. |
| 30 | Specific COVID-19 reference | Yes | 2 | 0 | 1 | v1 explicitly says "COVID-19 or other pandemic" (Finding 30). |
| 31 | Pandemic-related government measures | Yes | 1 | 0 | 1 | v1 references pandemic generally; Gemini references emergency/COVID-response actions. |
| 32 | Pandemic subject to dispro impact | Yes | 2 | 0 | 0 | v1 ties disproportionality to carveouts including pandemic effects. |
| 33 | Actions required under agreement | Yes | 1 | 0 | 0 | v1 includes transaction-required action carveout in proposed MAE package. |
| 34 | Actions with Buyer consent | Yes | 1 | 0 | 0 | v1 references buyer-requested/action carveout concept (Finding 30). |
| 35 | Target stockholder proceedings | Yes | 0 | 0 | 0 | No run gives explicit treatment. |
| 36 | Acts cured before closing | No | 0 | 0 | 0 | No explicit answer. |
| 37 | Matters on disclosure schedules | No | 1 | 0 | 0 | v1 mentions schedule-based carveout logic, but polarity is unclear vs MAUD. |
| 38 | Actions taken by Buyer | No | 1 | 0 | 0 | v1 references buyer-caused effects in carveout framing. |
| 39 | Relational language present? | Yes | 1 | 0 | 0 | v1 mentions carveout relational drafting concerns; not exact extraction. |
| 40 | Relational language dropdown | "Resulting from" | 1 | 0 | 0 | v1 discusses relational carveout wording but does not quote exact token with confidence. |
| 41 | Relational language applies to | All MAE carveouts | 0 | 0 | 0 | None explicitly maps scope across all carveouts. |
| 42 | Other carveouts subject to dispro impact | No | 1 | 0 | 0 | v1 touches dispro scope ambiguity (Finding 1), but not exact MAUD conclusion. |

### Category: Knowledge + No-Shop/COR/FTR Mechanics (Q43-Q63)

| # | Question | Expected Answer | Kimi v1 | Kimi v2 | Gemini | Notes |
|---|---|---|---:|---:|---:|---|
| 43 | Knowledge Definition | Constructive knowledge | 1 | 1 | 1 | All runs discuss actual vs constructive knowledge risk; none extracts final label cleanly. |
| 44 | Knowledge limited to identified persons | Yes | 1 | 1 | 1 | Kimi and Gemini discuss named-officer knowledge formulations directionally. |
| 45 | Liability for no-shop breaches by representatives | Yes | 1 | 1 | 1 | Topic present in no-shop/termination-fee analyses; no clause-specific direct answer. |
| 46 | Representative includes beyond D&Os | Yes | 1 | 1 | 0 | Kimi runs discuss broad representative definitions; Gemini mostly gap-oriented. |
| 47 | Liability standard for non-D&O rep breaches | Strict liability | 0 | 0 | 0 | No run identifies strict-liability standard explicitly. |
| 48 | Fiduciary exception board standard (no-shop) | "Inconsistent" with fiduciary duties | 1 | 1 | 0 | Kimi runs discuss fiduciary-standard language generally, but not exact MAUD wording. |
| 49 | COR only with fiduciary determination? | No | 1 | 1 | 0 | Kimi runs discuss multiple COR paths (superior + intervening), implying not board-only. |
| 50 | COR permitted for Superior Offer | Yes | 2 | 1 | 1 | Kimi v1 repeatedly references superior-proposal COR pathway; v2/gemini mention generally. |
| 51 | COR standard (Superior Offer) | "Inconsistent" with fiduciary duties | 1 | 1 | 0 | Mentioned conceptually; no exact standard extraction. |
| 52 | COR permitted for Intervening Event | Yes | 2 | 1 | 1 | v1 explicitly references intervening-event fiduciary out mechanics; others partial. |
| 53 | COR standard (Intervening Event) | "Inconsistent" with fiduciary duties | 1 | 1 | 0 | Discussed but not MAUD-exact phrase. |
| 54 | Additional matching periods (COR) | Continuous matching right | 2 | 1 | 1 | v1 discusses repeated/multi-step matching mechanics as continuing process. |
| 55 | Definition has knowledge requirement | Not known and not reasonably foreseeable at signing | 1 | 1 | 0 | Kimi runs mention knowledge/foreseeability in intervening-event definitions, not exact text. |
| 56 | Knowledge persons include target management? | No | 1 | 1 | 0 | Kimi runs discuss narrowing to named officers; no direct final yes/no extraction. |
| 57 | Intervening event must occur after signing? | May occur prior to signing | 1 | 1 | 0 | Both Kimi runs discuss timing/foreseeability mechanics but not exact MAUD answer. |
| 58 | Intervening-event definition has materiality standard? | Yes | 1 | 1 | 0 | Mentioned as materiality-linked in Kimi discussions. |
| 59 | FTR triggers | Superior Offer | 1 | 0 | 0 | v1 references superior-proposal termination/FTR path; still not explicit datapoint extraction. |
| 60 | Limitations on FTR exercise | Material no-shop breach resulting in Superior Offer | 1 | 0 | 0 | v1 notes no-shop-linked fee/termination constraints only directionally. |
| 61 | Additional matching periods (FTR) | Continuous matching right | 0 | 0 | 0 | Not explicitly extracted in any run. |
| 62 | Acquisition Proposal must be publicly disclosed? | No | 0 | 0 | 0 | No explicit answer. |
| 63 | Acquisition Proposal must still be pending? | No | 0 | 0 | 0 | No explicit answer. |

### Category: Ordinary Course, Antitrust Efforts, Specific Performance (Q64-Q69)

| # | Question | Expected Answer | Kimi v1 | Kimi v2 | Gemini | Notes |
|---|---|---|---:|---:|---:|---|
| 64 | Includes "consistent with past practice" | Yes | 2 | 1 | 1 | v1 explicitly references "ordinary course consistent with past practice" (Finding 187). |
| 65 | OC covenant carveout for pandemic responses | Yes | 1 | 1 | 1 | All runs mention pandemic/emergency carveout recommendations; none gives exact clause extraction. |
| 66 | Negative interim covenant carveout for pandemic responses | No | 0 | 0 | 0 | No run clearly differentiates ordinary-course vs negative interim covenant treatment. |
| 67 | General antitrust efforts standard | Commercially reasonable efforts | 1 | 1 | 1 | All runs discuss efforts standards (reasonable/commercially reasonable), but not extracted as definitive final standard. |
| 68 | Limitation on antitrust efforts | No obligation to divest/take actions | 1 | 1 | 1 | Runs discuss divestiture/hell-or-high-water limitations directionally; not exact quote-based extraction. |
| 69 | Specific Performance | "entitled to" specific performance | 2 | 1 | 1 | v1 has repeated specific-performance analysis (Findings 92-99) but not exact MAUD phrase quote; others mention only generally. |

---

## Category-Level Analysis

### 1) Deal mechanics / bringdown framework

- **Best:** Kimi v1
- **Observation:** Kimi v1 surfaces most relevant mechanics themes, but tends to frame as negotiation advice rather than direct answer extraction.
- **Gap:** None of the runs cleanly outputs exact MAUD categorical labels (e.g., "At Closing Only", "All Cash").

### 2) MAE definition + carveouts (including disproportionate impact)

- **Best:** Kimi v1 by a wide margin.
- **Observation:** v1 repeatedly identifies MAE carveout architecture and disproportionality modifiers; this is the strongest MAUD-adjacent region.
- **Gap:** Exact yes/no polarity on specific carveout sub-questions (especially APC, credit-rating dispro, schedules/actions-by-buyer carveouts) is often not directly resolved.

### 3) Pandemic/COVID carveouts

- **Best:** Kimi v1.
- **Observation:** v1 explicitly references COVID-19 and pandemic carveouts; v2/gemini mention pandemic mostly as generic risk advice.
- **Gap:** Government-response and disproportionality sub-elements are inconsistently explicit.

### 4) Knowledge definition and no-shop representative liability

- **Best:** Tie between Kimi v1 and v2 on topical mention.
- **Observation:** All runs discuss knowledge standards; Kimi runs mention actual-vs-constructive framing frequently.
- **Gap:** The exact MAUD answer "Constructive knowledge" is never cleanly extracted as final answer.

### 5) COR / Intervening Event / matching rights / FTR

- **Best:** Kimi v1.
- **Observation:** v1 has substantial coverage of superior offer, intervening event, and matching-right mechanics.
- **Gap:** Many datapoints remain interpretive (1-point) because outputs are diagnostic, not exact doctrinal extraction.

### 6) Ordinary course and pandemic interim covenants

- **Best:** Kimi v1.
- **Observation:** Strong mention of "ordinary course consistent with past practice" and covenant restrictiveness.
- **Gap:** Negative-interim-pandemic carveout polarity (No) is not cleanly answered by any run.

### 7) Antitrust efforts and limitations

- **Best:** Kimi v1 (slightly).
- **Observation:** All runs discuss efforts standards and divestiture burden.
- **Gap:** Exact MAUD benchmark answer pairing ("commercially reasonable efforts" + explicit no-divest obligation) is not presented as direct extractive output.

### 8) Specific performance

- **Best:** Kimi v1.
- **Observation:** v1 deeply analyzes asymmetry and remedy structure.
- **Gap:** Exact phrase-level extraction ("entitled to") is not directly surfaced.

---

## Qualitative Assessment

### Kimi K2.5 v1 (485 findings)

- **Strengths:** Broad thematic coverage, especially MAE carveouts, fiduciary-out dynamics, and specific performance. Best at surfacing legally meaningful risk contours.
- **Weaknesses:** Frequently speculative due to "missing section" framing; many findings are recommendations instead of extraction answers.
- **Net:** Best among three for MAUD-adjacent issue coverage, but still not benchmark-grade for direct structured question answering.

### Kimi K2.5 v2 (296 findings)

- **Strengths:** Strong emphasis on no-shop/Change-of-Recommendation interaction and remedy asymmetry.
- **Weaknesses:** Lower breadth than v1, many inferred/assumed statements, and weak clause-grounded final answers.
- **Net:** More concentrated but less useful than v1 for MAUD scoring; many topics mentioned without answer resolution.

### Gemini 3 Flash Preview (196 findings)

- **Strengths:** Completed run; clear documentation of structural coverage gaps and drafting-risk themes.
- **Weaknesses:** Over-indexed to "section missing" diagnostics; very limited exact MAUD datapoint extraction.
- **Net:** Useful as a red-flag scanner for document completeness, weak as a MAUD answer engine.

---

## Verdict

For MAUD-style M&A analysis, **Kimi v1 is the clear winner** among these three runs on usable benchmark signal. However, none of the runs is currently operating as a true MAUD extractor; they behave more like risk-issue analyzers with partial overlap. If the goal is leaderboard-style MAUD performance, the pipeline needs a dedicated normalization stage that maps findings into exact MAUD schema answers (yes/no/categorical), with explicit clause citation and polarity resolution. As-is, Contract-AF demonstrates strong agentic legal reasoning coverage (especially in v1), but limited extraction precision for strict benchmark scoring.
