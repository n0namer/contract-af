<div align="center">

# Contract-AF

### AI-Native Legal Contract Risk Analyzer Built on [AgentField](https://github.com/Agent-Field/agentfield)

[![Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-16a34a?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-179%20passing-16a34a?style=for-the-badge)](#development)
[![Built with AgentField](https://img.shields.io/badge/Built%20with-AgentField-0A66C2?style=for-the-badge)](https://github.com/Agent-Field/agentfield)
[![More from Agent-Field](https://img.shields.io/badge/More_from-Agent--Field-111827?style=for-the-badge&logo=github)](https://github.com/Agent-Field)

<p>
  <a href="#what-you-get-back">Output</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#api">API</a> •
  <a href="#comparison">Comparison</a>
</p>

</div>

<p align="center">
  <img src="assets/hero.png" alt="Contract-AF — Your AI Legal Team" width="100%" />
</p>

## One-Call DX

Trigger it with the `af` CLI (requires af ≥ 0.1.87) — it streams live progress and prints the result:

```bash
af call contract-af.analyze --in '{"document_text": "MASTER SERVICES AGREEMENT\n\n1. Term. This Agreement commences on the Effective Date and auto-renews for successive 12-month terms unless either party gives 90 days written notice.\n2. Liability. Provider'"'"'s total liability shall not exceed fees paid in the prior 3 months.\n3. Termination. Customer may terminate for convenience with 60 days notice; Provider may terminate immediately for any breach.", "user_context": "I am the customer"}'
```

Prefer raw HTTP? Hit the API directly with curl:

```bash
curl -X POST http://localhost:8080/api/v1/execute/async/contract-af.analyze \
  -H "Content-Type: application/json" \
  -d '{"input": {"document_text": "MASTER SERVICES AGREEMENT ... full contract text ...", "user_context": "I am the customer"}}'
```

Other tools flag patterns. Contract-AF **reads like a lawyer** — navigates the full document, traces definitions across sections, discovers combination risks between clauses, and reviews from the opposing party's perspective. Every finding: exploitation scenario, risk score, negotiation playbook. One API call, ~$0.40-$1.30.

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

Every finding includes **where** (clause ref + text), **why** (reasoning + exploitation scenario), **how bad** (deterministic score), and **what to do** (remediation + negotiation with fallbacks). Not "this might be a problem" — traces definitions, proves clause interactions, tells you exactly what to negotiate.

## How It Works

**7-phase adaptive pipeline**, 20-50+ agent invocations per run (100+ on complex contracts):

**Intake** → **Anatomy** → **Planning** → **Parallel Clause Analysis** → **Review Layer** → **Coverage Gate** → **Synthesis** → **Report**

Intake classifies the deal. Anatomy navigates the full document and maps structure. Planning routes sections to specialized analysts. Clause Analysis deep-reads clusters with adaptive depth. The Review Layer runs cross-reference resolution, adversarial review, and gap verification — all streaming in parallel. The Coverage Gate loops back if gaps remain. Synthesis scores and ranks. Report outputs multiple formats.

What makes this different from "throw a contract at an LLM and ask for risks":

### Agents that spawn agents at runtime

When a clause analyst finds something worth investigating — a broad definition, an unusual cross-reference, a dangerous clause interaction — it **crafts a specific investigation prompt** and **spawns a new agent** at runtime to pursue it.

> **Example:** An IP analyst reads *"All Work Product shall be the sole property of Company"*, checks Definitions, finds "Work Product" includes inventions *"whether or not related to Company's business."* It recognizes this is unusually broad, launches a Definition Impact Analyzer: *"Analyze the impact of this definition on Sections 5, 8, and 12. Does it capture personal projects?"* The child investigates, reports back. Parent integrates.

Not static dispatch. The investigation path emerges from what the system discovers in *your specific contract*.

### Adversarial verification

Finding agents and disproving agents are **structurally separated**:
- **Clause analysts** are incentivized to find risks
- **Adversary Reviewer** is incentivized to challenge them — re-reads actual clause text, identifies standard practice, false positives, and what the other side would argue
- The adversary also hunts **hidden traps** the analysts missed — e.g., discovering three separate risk clauses all survive termination via the same Section 14, creating combined post-termination obligations far worse than any individual clause suggests

### Streaming analysis — overlap, don't batch

Downstream agents don't wait. The Cross-Reference Resolver and Adversary Reviewer consume findings from a streaming queue as clause analysts produce them. By the time the last analyst finishes, the review layer is already halfway done. When the Cross-Ref Resolver discovers a critical interaction between clauses from different analysts, it spawns a focused deep-dive immediately — while other analysts are still running.

### Adaptive depth with hard budget caps

Three nested control loops — each with hard caps:

- **Per-analyst** — follows out-of-scope references (max 3), self-escalates on critical signals, exits early on no risk
- **Cross-agent** — cross-ref resolver or adversary spawns focused sub-agents for combination risks (max 3 per phase)
- **Coverage gate** — after all agents complete, checks for missed/under-analyzed sections, spawns new analysts for gaps (max 2 iterations, 3 analysts each)

Explores deeply where signal exists, moves on where it doesn't, never spirals into unbounded cost.

### Deterministic scoring — LLMs reason, code scores

Risk scores are computed by code, not LLMs. Severity weights, combination risk multipliers (1.5x), exploitability multipliers (1.3x), jurisdiction discounts (California non-competes → unenforceable) — all deterministic. LLMs handle what requires intelligence: negotiation language, fallback positions, counterparty arguments.

### Graceful escalation

Every fast `.ai()` gate includes a `confident` flag. When input doesn't fit assumptions (unusual structure, exhibits before recitals, missing headers), the system automatically escalates to a deeper document-navigating agent (~$0.05-$0.10 extra). A wrong classification propagating through the entire pipeline costs far more.

> **Same pattern, code security:** [SEC-AF](https://github.com/Agent-Field/sec-af) applies adversarial verification to codebases — hunters find vulnerabilities, provers disprove false positives. Every finding ships with a verdict.

## Cost

| Contract Size | Budget Models | Mid-Tier Models | Premium Models |
|---|---|---|---|
| 20-page SaaS agreement | ~$0.20-$0.45 | ~$0.65-$1.30 | ~$2.00-$4.00 |
| 50-page enterprise license | ~$0.45-$0.90 | ~$1.20-$2.40 | ~$4.00-$7.00 |
| 100-page M&A agreement | ~$0.80-$1.50 | ~$2.00-$4.00 | ~$6.00-$12.00 |

Budget: Kimi K2.5, MiniMax. Mid-tier: GPT-4o-mini, Sonnet. Premium: Opus, GPT-4o. Any OpenRouter-compatible model works.

## Quick Start

```bash
git clone https://github.com/Agent-Field/contract-af.git && cd contract-af
cp .env.example .env          # Add OPENROUTER_API_KEY
docker compose up --build
```

Starts AgentField control plane (`http://localhost:8080`) + Contract-AF agent.

```bash
curl -X POST http://localhost:8080/api/v1/execute/async/contract-af.analyze \
  -H "Content-Type: application/json" \
  -d '{"input": {"file_path": "/path/to/contract.pdf", "user_context": "I am the customer"}}'
```

Poll for results:

```bash
curl http://localhost:8080/api/v1/executions/<execution_id>
```

## Comparison

| | Contract-AF | Harvey AI | Klarity | Spellbook |
|---|---|---|---|---|
| **Approach** | Multi-agent pipeline with adversarial verification | Single model, enterprise | ML extraction + rules | Single model, clause library |
| **Verified findings** | Adversarial review + exploitation scenarios | Not documented | Pattern-based extraction | Not documented |
| **Negotiation playbook** | Per-finding strategy with fallbacks | General guidance | Not included | Clause suggestions |
| **Cross-clause analysis** | Streaming cross-reference resolution with runtime deep-dives | Not documented | Not documented | Not documented |
| **Adaptive depth** | 3 nested control loops with budget caps | Fixed pass | Fixed pass | Fixed pass |
| **Open source** | Apache 2.0 | Proprietary | Proprietary | Proprietary |
| **Cost** | ~$0.40-$1.30/contract | ~$500-$2000/mo | ~$1000+/mo | ~$500+/mo |

**Strongest at:** Adversarial verification, cross-clause interaction analysis, adaptive depth, deterministic scoring, negotiation playbooks, cost.

**Others are stronger at:** Enterprise integrations, clause libraries, legal corpora training (Harvey, Spellbook), purpose-built ML extraction for specific types (Klarity).

## Supported Contract Types

SaaS, employment, NDAs, licensing, service, consulting, partnership — and any type you throw at it. Auto-classifies at intake, selects relevant clause categories, checks for expected clauses. No code changes for new types.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest                    # 179 tests
ruff check src/ tests/
```

---

### Also built on AgentField

> **[SEC-AF](https://github.com/Agent-Field/sec-af)** — AI-native security auditor. 250 agents per audit, 94% noise reduction, every finding proven exploitable.
>
> **[AF Deep Research](https://github.com/Agent-Field/af-deep-research)** — Autonomous research backend. 10,000+ agent invocations per query with self-correcting loops.

[All repos →](https://github.com/Agent-Field)

---

<div align="center">

Contract-AF is built on [AgentField](https://github.com/Agent-Field/agentfield), open infrastructure for production-grade autonomous agents. [See what else we're building →](https://github.com/Agent-Field)

**[Apache-2.0](LICENSE)**

</div>
