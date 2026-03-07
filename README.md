<div align="center">

# Contract-AF

### AI-Native Legal Contract Risk Analyzer Built on [AgentField](https://github.com/Agent-Field/agentfield)

[![Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-16a34a?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-179%20passing-16a34a?style=for-the-badge)](#development)
[![Built with AgentField](https://img.shields.io/badge/Built%20with-AgentField-0A66C2?style=for-the-badge)](https://github.com/Agent-Field/agentfield)

<p>
  <a href="#what-you-get-back">Output</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#why-this-architecture">Why It Works</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#api">API</a> •
  <a href="#comparison">Comparison</a>
</p>

</div>

Other tools flag patterns. Contract-AF **reads like a lawyer**: it navigates the full document, traces definitions across sections, discovers combination risks between clauses, and reviews from the opposing party's perspective. Every finding ships with an exploitation scenario, a risk score, and a negotiation playbook. One API call, ~$0.40-$1.30 in LLM costs.

## What You Get Back

Upload a contract, get back four deliverables:

```jsonc
{
  // 1. Risk-ranked findings with exploitation scenarios
  "findings": [
    {
      "clause_ref": "8.3",
      "clause_text": "All Work Product shall be the sole property of Company.",
      "category": "ip_work_product",
      "severity": "critical",
      "risk_score": 0.92,
      "description": "Overbroad IP assignment — captures inventions unrelated to Company's business",
      "reasoning": "Definition of 'Work Product' (Section 1.15) includes 'whether or not related to Company's business'. Combined with Section 12.3's perpetual license, this eliminates all residual IP rights post-termination.",
      "exploitation_scenario": "Company could claim ownership of employee's personal side projects, open-source contributions, or prior inventions not listed in Exhibit B.",
      "remediation": "Limit to inventions conceived using Company's confidential information or resources",
      "negotiation_strategy": "Propose: 'Work Product related to Company's current or reasonably anticipated business'. Fallback: add a carve-out for personal projects outside working hours."
    }
  ],

  // 2. Executive summary
  "executive_summary": "High-risk employment agreement with 3 critical findings...",

  // 3. Full markdown risk report
  "risk_report_md": "# Contract Review Report\n\n## Critical Findings\n...",

  // 4. Negotiation playbook with priorities, fallbacks, deal-breakers
  "negotiation_playbook": "## Negotiation Playbook\n\n### Priority 1: IP Assignment..."
}
```

Every finding includes **where** the risk lives (clause reference + text), **why** it's dangerous (reasoning + exploitation scenario), **how bad** it is (deterministic risk score), and **what to do** (remediation + negotiation strategy with fallback positions). Not "this might be a problem." Contract-AF traces definitions, proves the interaction between clauses, and tells you exactly what to negotiate.

## How It Works

Contract-AF decomposes legal review into a **7-phase adaptive pipeline** — the same workflow a senior lawyer follows, but with 10-15+ specialized agents working in parallel. Each agent handles a narrow, well-defined task. The orchestrator manages context flow, parallelism, and adaptive depth.

### Architecture: 7-Phase Pipeline

```
                                    ┌─────────────────────────┐
                                    │   CONTRACT (PDF/DOCX/TXT)│
                                    │   + User Context         │
                                    └───────────┬─────────────┘
                                                │
                              ┌─────────────────▼──────────────────┐
                              │  Phase 1: INTAKE                    │
                              │  Fast classification — type,        │
                              │  parties, jurisdiction, complexity   │
                              │  (escalates to deep read if unsure) │
                              └─────────────────┬──────────────────┘
                                                │
                              ┌─────────────────▼──────────────────┐
                              │  Phase 2: ANATOMY                   │
                              │  Navigate full document — map        │
                              │  sections, defined terms, cross-     │
                              │  references, exhibits, risk signals  │
                              └─────────────────┬──────────────────┘
                                                │
                              ┌─────────────────▼──────────────────┐
                              │  Phase 3: ANALYSIS PLAN             │
                              │  Route sections to specialized       │
                              │  clusters, assign depth, set         │
                              │  escalation triggers                 │
                              └─────────────────┬──────────────────┘
                                                │
                    ┌───────────────────────────┼──────────────────────────┐
                    │                           │                          │
          ┌─────────▼──────┐       ┌────────────▼─────┐       ┌──────────▼───────┐
          │ Clause Analyst 1│       │ Clause Analyst 2  │       │ Clause Analyst N  │
          │ (IP/Work Product)│       │ (Liability/Indem) │       │ (Non-Compete)     │
          │                 │       │                   │       │                   │
          │ • Follow refs   │       │ • Escalate depth  │       │ • Early exit on   │
          │ • Spawn sub-    │       │ • Trace defs      │       │   no signal       │
          │   agents for    │       │                   │       │                   │
          │   deep dives    │       │                   │       │                   │
          └────────┬────────┘       └─────────┬─────────┘       └─────────┬─────────┘
                   │                          │                           │
                   └──────────────────────────┼───────────────────────────┘
                                              │
                                    ┌─────────▼──────────┐
                                    │  Findings Queue     │
                                    │  (streaming)        │
                                    └──┬──────────────┬───┘
                                       │              │
                    ┌──────────────────▼──┐    ┌──────▼──────────────────┐
                    │  Cross-Reference     │    │  Adversary Reviewer     │
                    │  Resolver            │    │                         │
                    │  Traces inter-clause │    │  Reviews from opposing  │
                    │  interactions,       │    │  party's perspective,   │
                    │  spawns deep-dives   │    │  flags false positives, │
                    │  for combinations    │    │  discovers hidden traps │
                    └──────────┬───────────┘    └──────────┬──────────────┘
                               │                           │
               ┌───────────────┼───────────────────────────┤
               │               │                           │
               │    ┌──────────▼────────────┐              │
               │    │  Gap Analyst           │              │
               │    │  Verifies missing       │              │
               │    │  clauses are truly      │              │
               │    │  absent (not buried)    │              │
               │    └──────────┬─────────────┘              │
               │               │                           │
               └───────────────┼───────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Coverage Gate       │        ◄── Loop back if gaps
                    │  Sufficient? ────────┼─── No ──► Spawn new analysts
                    │  (max 2 iterations)  │            (max 3 per round)
                    └──────────┬──────────┘
                               │ Yes
                    ┌──────────▼──────────┐
                    │  Phase 6: SYNTHESIS  │
                    │  Score risks (code), │
                    │  rank findings,      │
                    │  generate negotiation│
                    │  strategy (LLM)      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Phase 7: REPORT     │
                    │  Markdown, JSON,     │
                    │  negotiation playbook│
                    └─────────────────────┘
```

### Signal Cascade

| Phase | Purpose | Agents |
|---|---|---|
| **INTAKE** | Classify contract type, parties, jurisdiction | 1 (fast classifier, escalates to deep reader if unsure) |
| **ANATOMY** | Navigate full document, map structure and risk signals | 1 (document navigator) |
| **PLAN** | Route sections to specialized analyst clusters | 1 (planner) |
| **CLAUSE REVIEW** | Deep analysis per cluster — follow refs, escalate depth, spawn sub-agents | N parallel (typically 2-6) |
| **REVIEW LAYER** | Cross-ref interactions + adversary review + gap verification | 3 parallel (streaming consumers) |
| **COVERAGE GATE** | Check if analysis is sufficient, loop back if gaps remain | 1 (max 2 iterations) |
| **SYNTHESIS** | Deterministic scoring + LLM negotiation strategy | 1 |
| **REPORT** | Multi-format output generation | 1 |

## Why This Architecture

Most AI contract tools run one big prompt and hope the LLM gets it right. Contract-AF decomposes legal review into 10-15+ focused agents, each with a narrow task and bounded autonomy. The architecture encodes the review strategy — not the prompts (see [The Atomic Unit of Intelligence](https://www.santoshkumarradha.com/writing/atomic-unit-of-intelligence) for why this matters).

<details>
<summary><strong>Design patterns that make this work</strong></summary>

**1. Meta-prompting: agents that spawn agents**

This is the core architectural innovation. When a Clause Analyst discovers something worth investigating deeper — a broad definition, an unusual cross-reference, a clause that interacts with another — it doesn't just flag it. It uses its own intelligence to **craft a specific investigation prompt** and **spawn a child agent** at runtime.

```
IP Analyst reads Section 8.3: "All Work Product shall be sole property of Company."
    → Checks Definitions: "Work Product" includes "whether or not related to business"
    → Recognizes this is unusually broad
    → Crafts a targeted prompt: "Analyze the impact of this broad definition
       on Sections 5, 8, 12. Does it capture personal projects?"
    → Spawns a Definition Impact Analyzer with this specific prompt
    → Integrates the child's findings into its own output
```

The parent agent decides WHAT to investigate (intelligence, not script) and HOW to frame the investigation (crafts the prompt). The child agent has bounded autonomy — it reads the assigned sections and returns structured findings. This is fundamentally different from static dispatch where a fixed orchestrator routes to predetermined handlers.

**2. Adversarial tension: FIND vs. DISPROVE**

The pipeline structurally separates finding agents from disproving agents. Clause Analysts are incentivized to find risks. The Adversary Reviewer is incentivized to disprove them — to find false positives and re-read actual clause text (not just summaries) to spot what's actually standard practice for this contract type. This tension produces higher-confidence findings than asking a single model "is this risky?"

**3. Streaming pipeline: overlap instead of batch**

Phase 5 agents (Cross-Reference Resolver, Adversary Reviewer) don't wait for all Clause Analysts to finish. They consume findings from `asyncio.Queue` as they arrive. The Cross-Ref Resolver starts checking for inter-clause interactions as soon as two analysts have reported. This overlaps work and catches combination risks earlier.

**4. Three nested control loops**

| Loop | Scope | Trigger | Budget |
|---|---|---|---|
| **Inner** | Per Clause Analyst | Found out-of-scope reference / critical finding | Max 3 ref follows, 1 depth escalation |
| **Middle** | Cross-Ref + Adversary | Critical clause combination / hidden trap discovered | Max 3 sub-agent spawns |
| **Outer** | Coverage Gate | Analysis gaps after all agents complete | Max 2 re-analysis iterations, 3 new analysts each |

Each loop has hard budget caps. Without them, adaptive systems become unbounded cost sinks. With them, the system explores deeply where signal exists and moves on quickly where it doesn't.

**5. Deterministic scoring + LLM negotiation**

Risk scores are computed by code — not by asking an LLM to guess a number:

```python
score = SEVERITY_WEIGHTS[finding.severity]
if finding in combination_risks:   score *= 1.5   # combination multiplier
if finding in exploit_scenarios:   score *= 1.3   # exploitability multiplier
if not enforceable(jurisdiction):  score *= 0.3   # jurisdiction discount
```

California non-competes? Automatically discounted. Two clauses that interact to eliminate IP rights? Automatically boosted. The LLM's job is the part that requires intelligence — generating negotiation language, suggesting fallback positions, anticipating counterarguments.

**6. Graceful escalation**

Fast classification calls include a `confident` flag. When the first few pages don't contain enough metadata to classify the contract (unusual structure, exhibits before recitals, missing headers), the system automatically escalates to a deeper document-navigating agent. Cost: ~$0.05-$0.10 extra. Value: prevents a wrong classification from propagating through the entire pipeline.

</details>

### Agent Inventory

| Agent | Role | Dynamic Behavior |
|---|---|---|
| **Intake Classifier** | Classify contract type, parties, jurisdiction | Escalates to deep reader when `confident: false` |
| **Contract Anatomist** | Navigate full document, build structural map | Produces risk signals for downstream depth routing |
| **Analysis Planner** | Route sections to specialized clusters | Assigns escalation triggers per cluster |
| **Clause Analyst** (x N) | Deep analysis per cluster | **Inner loop:** follow refs (max 3), escalate depth, early exit. **Meta-prompting:** spawn sub-agents for definition impact analysis |
| **Cross-Ref Resolver** | Trace inter-clause interactions | **Streaming consumer.** Spawns deep-dive sub-agents for critical combinations (max 3) |
| **Adversary Reviewer** | Review from opposing party's perspective | **Streaming consumer.** Flags false positives, discovers hidden traps, spawns sub-agents for survival pattern analysis |
| **Gap Analyst** | Verify missing clauses are truly absent | Searches contract for clauses under alternative names/locations |
| **Coverage Assessor** | Check analysis sufficiency | **Outer loop:** triggers new analysts for uncovered sections |
| **Risk Synthesizer** | Score, rank, generate negotiation strategy | Programmatic scoring + LLM-generated negotiation language |
| **Report Writer** | Generate multi-format output | Markdown, JSON, negotiation playbook. Fallback generation if upstream fails |

**Typical run:** 10-15+ agent invocations for a standard contract. Complex contracts with many cross-references and coverage gaps can trigger 20-30+.

## Cost Estimate

| Contract Size | Budget Models | Mid-Tier Models | Premium Models |
|---|---|---|---|
| 20-page SaaS agreement | ~$0.20-$0.45 | ~$0.65-$1.30 | ~$2.00-$4.00 |
| 50-page enterprise license | ~$0.45-$0.90 | ~$1.20-$2.40 | ~$4.00-$7.00 |
| 100-page M&A agreement | ~$0.80-$1.50 | ~$2.00-$4.00 | ~$6.00-$12.00 |

Budget: Kimi K2.5, MiniMax. Mid-tier: GPT-4o-mini, Sonnet. Premium: Opus, GPT-4o. Any OpenRouter-compatible model works.

## Quick Start

```bash
pip install -e .[dev]
```

### CLI

```bash
# Analyze a contract
contract-af analyze my-contract.pdf --context "I am the customer"

# JSON output
contract-af analyze my-contract.docx --format json -o report.json

# Start the API server
contract-af serve --port 8000
```

### API

```bash
# Upload and start analysis
curl -X POST http://localhost:8000/analyze \
  -F "file=@my-contract.pdf" \
  -F "user_context=I am the customer, SaaS subscription"

# Response: {"job_id": "abc-123", "status": "running"}

# Poll for results
curl http://localhost:8000/analyze/abc-123

# Get markdown report
curl http://localhost:8000/analyze/abc-123/report
```

<details>
<summary><strong>API endpoints</strong></summary>

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness probe |
| `/analyze` | POST | Upload contract file (PDF, DOCX, TXT) + optional `user_context`. Returns `job_id` |
| `/analyze/{job_id}` | GET | Poll analysis status and results |
| `/analyze/{job_id}/report` | GET | Get markdown risk report for completed job |

**Supported formats:** `.pdf`, `.docx`, `.doc`, `.txt`, `.md`

</details>

## Comparison

| | Contract-AF | Harvey AI | Klarity | Spellbook |
|---|---|---|---|---|
| **Approach** | Multi-agent pipeline with adversarial verification | Single model, enterprise | ML extraction + rules | Single model, clause library |
| **Verified findings** | Adversarial review + exploitation scenarios | Not documented | Pattern-based extraction | Not documented |
| **Negotiation playbook** | Per-finding strategy with fallbacks | General guidance | Not included | Clause suggestions |
| **Cross-clause analysis** | Streaming cross-reference resolver with deep-dive sub-agents | Not documented | Not documented | Not documented |
| **Adaptive depth** | 3 nested control loops with budget caps | Fixed pass | Fixed pass | Fixed pass |
| **Open source** | Apache 2.0 | Proprietary | Proprietary | Proprietary |
| **Cost** | ~$0.40-$1.30/contract | ~$500-$2000/mo | ~$1000+/mo | ~$500+/mo |

**Where Contract-AF is strongest**: Adversarial verification, cross-clause interaction analysis, adaptive depth with meta-prompting, deterministic scoring, negotiation playbooks, and cost.

**Where others are stronger**: Harvey and Spellbook have enterprise integrations, clause libraries, and years of training on legal corpora. Klarity has purpose-built ML extraction for specific contract types. Contract-AF is newer and focused on depth of analysis over breadth of integrations.

## Supported Contract Types

Out of the box: SaaS agreements, employment contracts, NDAs, licensing agreements, service agreements, consulting agreements, partnership agreements.

The system adapts to any contract type — the Intake Classifier identifies the type, the Analysis Planner selects relevant clause categories, and the Gap Analyst checks for expected clauses based on that classification. Adding support for new contract types requires no code changes.

## Project Structure

```
src/contract_af/
├── agents/
│   ├── intake.py          # Phase 1: classification with fallback
│   ├── anatomy.py         # Phase 2: structural parsing
│   ├── planner.py         # Phase 3: analysis routing
│   ├── clause_analyst.py  # Phase 4: deep analysis with meta-prompting
│   ├── cross_ref.py       # Phase 5a: cross-reference resolver
│   ├── adversary.py       # Phase 5b: adversary reviewer
│   ├── gap_analyst.py     # Phase 5c: gap verification
│   ├── coverage.py        # Phase 5.5: coverage gate
│   ├── synthesizer.py     # Phase 6: scoring + strategy
│   └── report_writer.py   # Phase 7: multi-format output
├── models/
│   └── types.py           # All Pydantic models (IntakeResult, Finding, etc.)
├── pipeline/
│   ├── orchestrator.py    # 7-phase pipeline with streaming + coverage loop
│   └── scoring.py         # Deterministic risk scoring
├── utils/
│   └── document_loader.py # PDF, DOCX, TXT loader
├── api.py                 # FastAPI application
└── cli.py                 # CLI entry point
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest                    # 179 tests
ruff check src/ tests/
```

### Test Coverage

| Test File | Tests | Coverage |
|---|---|---|
| `test_intake.py` | 6 | Intake classifier + fallback patterns |
| `test_planner.py` | 5 | Analysis plan validation |
| `test_anatomy.py` | 45 | Section extraction, risk signals, harness fallback |
| `test_clause_analyst.py` | 39 | Inner loop, meta-prompting, budget caps |
| `test_review_layer.py` | 16 | Cross-ref, adversary, gap analysis |
| `test_synthesis_report.py` | 43 | Scoring, coverage gate, synthesis, report |
| `test_pipeline.py` | 6 | Full pipeline integration |
| `test_api.py` | 19 | FastAPI endpoints, CLI, document loader |

---

<div align="center">

Contract-AF is built on [AgentField](https://github.com/Agent-Field/agentfield), open infrastructure for production-grade autonomous agents.

**[Apache-2.0](LICENSE)**

</div>
