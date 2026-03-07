# Contract-AF

Legal contract risk analyzer powered by [AgentField](https://github.com/Agent-Field/agentfield). Finds dangerous clauses, proves exploitability in your context, and generates a negotiation playbook.

**Kills:** Harvey AI ($300M), Klarity, Spellbook ($1k-$10k/mo)
**Cost:** ~$0.40-$1.00/contract

## Architecture

7-phase adaptive review pipeline with 10+ specialized agents:

1. **Intake** (.ai()) - Classify contract type, parties, jurisdiction
2. **Anatomy** (.harness()) - Navigate full document, map structure
3. **Analysis Plan** (.ai()) - Route sections to specialized clusters
4. **Clause Review** (.harness() x N) - Parallel deep analysis with meta-prompting
5. **Review Layer** (.harness() x 3) - Cross-ref resolver, adversary reviewer, gap analyst
6. **Synthesis** (.harness()) - Risk scoring + negotiation strategy
7. **Report** (.harness()) - Multi-format output

See [architecture doc](docs/plans/2026-03-07-contract-af-architecture-options.md) for full design.

## Quick Start

```bash
pip install -e .[dev]

# Start AgentField control plane
cd /path/to/agentfield/control-plane && go run ./cmd/af dev

# Run contract-af
export AGENTFIELD_SERVER=http://localhost:8080
contract-af analyze my-contract.pdf --context "I am the customer, SaaS subscription"
```

## Development

```bash
pip install -e .[dev]
pytest
ruff check src/ tests/
```

## License

Apache 2.0
