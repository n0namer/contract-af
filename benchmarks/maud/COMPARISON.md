# MAUD Benchmark: Contract-AF Model Comparison

**Contract:** Collectors Universe, Inc. / Investment Group (Merger Agreement)  
**Benchmark:** MAUD v1 (ABA 2021 Public Target Deal Points Study)  
**Ground Truth:** 129 expert-labeled M&A questions  
**Date:** 2026-03-08

---

## Pipeline Summary

| Metric | Kimi K2.5 | Gemini 3 Flash Preview |
|--------|-----------|----------------------|
| **Wall clock** | 1,817s (30.3m) | 1,822s (30.4m) |
| **Total findings** | 485 | 207 |
| **Substantive findings** | 278 | 44 |
| **Coverage gap findings** | 207 | 163 |
| **Clusters analyzed** | 21 | 25 |
| **Combination risks** | 29 | 0 |
| **Adversary scenarios** | 15 exploitation, 11 false-pos, 63 hidden traps | None |
| **Result size** | 488 KB | 100 KB |
| **Completed fully?** | No (1800s timeout) | Yes |
| **Executive summary** | "Analysis terminated early" | Full summary |
| **Negotiation playbook** | Not generated (timeout) | 2,814 chars |
| **Risk report** | Not generated (timeout) | 6,133 chars |

---

## MAUD Question Coverage (42 Key Questions Scored)

Scoring method: regex search over all pipeline output (findings, executive summary,
adversary results, combination risks, playbook, report) for answer-specific terms
matching the MAUD ground truth.

| MAUD Question | Expected Answer | Kimi | Gemini |
|---------------|----------------|------|--------|
| Type of Consideration | All Cash | ✓ | ✗ |
| Accuracy of General R&W Bringdown Standard | MAE standard | ✓ | ✓ |
| Accuracy of Capitalization R&W | de minimis exception | ✓ | ✓ |
| Accuracy of Fundamental R&Ws | Accurate in all respects | ✓ | ✗ |
| Materiality Scrape | General R&Ws, Specified R&Ws | ✓ | ✓ |
| Compliance with Covenant Condition | Each Covenant | ✓ | ✓ |
| No MAE R&W as of Specified Date | No | ✓ | ✗ |
| MAE applies to Target+Subs taken as whole | "taken as a whole" | ✗ | ✗ |
| MAE Forward Looking Standard | "Would reasonably be expected to" | ✓ | ✓ |
| General political conditions carveout | Yes + disproportionate | ✓ | ✗ |
| General economic conditions carveout | Yes + disproportionate | ✓ | ✗ |
| Industry changes carveout | Yes + disproportionate | ✗ | ✗ |
| Change in law carveout | Yes + disproportionate | ✓ | ✗ |
| GAAP changes carveout | Yes + disproportionate | ✓ | ✓ |
| Announcement/Pendency carveout | Yes, A/P/C | ✓ | ✗ |
| Failure to meet projections carveout | Yes | ✓ | ✓ |
| Market price/trading volume carveout | Yes | ✓ | ✗ |
| War/terrorism/natural disaster carveout | Yes + disproportionate | ✓ | ✗ |
| Pandemic carveout | Yes + COVID + disproportionate | ✓ | ✓ |
| Actions required under agreement carveout | Yes | ✓ | ✓ |
| Actions with buyer consent carveout | Yes | ✓ | ✓ |
| Knowledge Definition | Constructive knowledge | ✓ | ✓ |
| No-Shop provision | Yes with strict liability for reps | ✓ | ✓ |
| Fiduciary exception standard | "Inconsistent" with fiduciary duties | ✓ | ✗ |
| Fiduciary trigger | Superior Offer or likely to result in | ✓ | ✗ |
| COR in response to Superior Offer | Yes | ✓ | ✓ |
| COR in response to Intervening Event | Yes | ✓ | ✓ |
| COR matching rights initial period | 4 calendar days / 96 hours | ✓ | ✗ |
| COR matching rights modifications | 3 days continuous | ✓ | ✓ |
| Superior Proposal Definition | >50% voting/assets | ✓ | ✗ |
| Intervening Event - knowledge requirement | Not known and not reasonably foreseeable | ✓ | ✗ |
| FTR Triggers | Superior Offer | ✓ | ✓ |
| FTR matching rights | 4 calendar days | ✗ | ✗ |
| Tail Period | 12 months | ✓ | ✓ |
| Termination Fee trigger | Superior Offer | ✓ | ✓ |
| General Antitrust Efforts | Commercially reasonable efforts | ✓ | ✗ |
| Antitrust limitations | No obligation to divest | ✓ | ✓ |
| Specific Performance | "Entitled to" specific performance | ✓ | ✓ |
| Ordinary Course standard | Flat covenant (no efforts) | ✓ | ✓ |
| Buyer consent for ordinary course | Not unreasonably withheld | ✗ | ✓ |
| Ordinary course pandemic carveout | Yes | ✓ | ✗ |
| Negative covenant buyer consent | Not unreasonably withheld | ✓ | ✓ |

### Score Summary

| | Kimi K2.5 | Gemini 3 Flash Preview |
|---|-----------|----------------------|
| **Answered** | 38/42 (90%) | 23/42 (55%) |
| **Missed** | 4/42 | 19/42 |

---

## Topic Coverage (30 High-Level MAUD Topics)

| | Kimi | Gemini |
|---|------|--------|
| **Topics mentioned** | 30/30 (100%) | 26/30 (87%) |
| **Gemini missed** | — | General economic conditions, Industry changes, Announcement/Pendency, Change in law carveouts |

---

## Analysis

### Kimi K2.5 Strengths
- **Deep clause extraction**: Kimi quoted specific contract language (e.g., "$92.00", "ninety-six hours", "fifty percent") enabling precise answer matching
- **MAE carveout granularity**: Identified 10+ individual MAE carveouts with disproportionate impact modifiers — exactly what MAUD tests
- **Adversary layer**: 15 exploitation scenarios, 63 hidden traps, 11 false-positive challenges — no equivalent in Gemini
- **Combination risks**: 29 interaction effects identified (e.g., MAE ambiguity × uncapped liability = compounding risk)
- **Volume**: 485 findings vs 207 — more surface area for answer coverage

### Kimi K2.5 Weaknesses
- **Timeout**: Hit 1800s wall-clock limit, no executive summary/playbook/report generated
- **Empty findings**: ~20 findings with blank descriptions (categories 11-25 in "Definitions and Agreement Structure")
- **No final deliverables**: Missing the polished outputs a client would actually read

### Gemini 3 Flash Preview Strengths
- **Complete pipeline**: Full executive summary, negotiation playbook (2.8K chars), risk report (6.1K chars)
- **Actionable playbook**: Phased negotiation strategy with specific talk tracks
- **Novel insights**: Identified 10b-5 anti-fraud representation risk (uncommon in private M&A) — a genuinely sophisticated finding
- **Clean output**: 44 substantive findings, each with reasoning and remediation

### Gemini 3 Flash Preview Weaknesses
- **Shallow on MAE carveouts**: Missed most individual carveout categories that MAUD specifically tests
- **No adversary layer**: Zero exploitation scenarios or false-positive challenges
- **No combination risks**: Missed all interaction effects between findings
- **Missing specifics**: Didn't extract exact dollar amounts, time periods, or percentage thresholds
- **Fiduciary details**: Missed the "inconsistent with fiduciary duties" standard and matching rights periods

### Questions Both Missed
- **MAE applies to Target+Subs "taken as a whole"**: Neither extracted this specific qualifier
- **Industry changes carveout with disproportionate impact**: Neither identified this specific carveout
- **FTR matching rights period**: Neither connected the 96-hour notice period to the FTR context specifically

---

## Verdict

**Kimi is the better analyst. Gemini is the better communicator.**

For a benchmark like MAUD that tests *understanding and judgment* of specific M&A provisions:
- Kimi scores **90%** — it reads the contract deeply enough to answer expert-level questions
- Gemini scores **55%** — it identifies high-level risks but misses the granular details that M&A lawyers care about

For a production use case where a client needs a readable report:
- Gemini delivers a complete, actionable package (summary + playbook + report)
- Kimi delivers raw intelligence that needs post-processing

**Ideal architecture**: Use Kimi as the hunter/analyst layer, Gemini as the report-generation layer. Feed Kimi's 485 findings into Gemini for synthesis and client-facing output.

---

## Comparison with CUAD Benchmark (Phase 1)

| Metric | CUAD (Dova Promotion) | MAUD (Collectors Universe) |
|--------|----------------------|---------------------------|
| Contract type | Promotion agreement | Merger agreement |
| Contract size | ~50K chars | ~300K chars |
| Benchmark focus | Span extraction (41 clause types) | M&A judgment (92+ question categories) |
| Kimi findings | 601 | 485 |
| Gemini findings | 186 | 207 |
| Kimi timeout? | Yes (2756s) | Yes (1817s) |
| Gemini complete? | Yes (1137s) | Yes (1822s) |

The pattern is consistent: Kimi hunts deeper but times out; Gemini finishes but with less depth. MAUD amplifies this gap because it tests *specific legal judgment* rather than *clause identification*.
