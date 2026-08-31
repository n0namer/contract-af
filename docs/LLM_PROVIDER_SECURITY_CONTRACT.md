# Contract-AF — LLM Provider & Security Profile

Status: canonical repo-local provider profile
Cross-component contract: `n0namer/universal-solver:main/docs/architecture/llm-provider-security-contract.md`

## Current source contract

`agentfield-package.yaml` currently declares:
- required `OPENROUTER_API_KEY` for both harness and direct `.ai()` reasoning;
- `HARNESS_PROVIDER` (`aforge` by default, `opencode` as rollback/config alternative);
- `HARNESS_MODEL`;
- `AI_MODEL` for direct AI reasoning calls;
- AgentField control-plane credentials separately.

The current manifest is therefore **OpenRouter-centric** and uses more than one model-call path.

## Provider rule

Contract-AF must treat these paths independently:
1. coding/reasoning harness path;
2. direct `.ai()` path.

Provider/model/base propagation must be proven for both paths that are exercised by the workflow. One successful path cannot stand in for the other.

## Gonka/OpenAI-compatible adoption rule

If Contract-AF is migrated to Gonka/OpenAI-compatible routing, do not simply substitute a token. First prove:
- source/runtime supports `OPENAI_API_KEY` + `OPENAI_BASE_URL` through both harness and direct-AI paths;
- model namespaces are explicitly compatible;
- dynamic/runtime overrides preserve the configured base URL;
- no OpenRouter fallback remains unless explicitly policy-approved.

Only then should manifest/bootstrap requirements be updated from their current OpenRouter-centric contract.

## Security requirements

- Never commit/log raw LLM or AgentField credentials.
- Legal/contract inputs may contain confidential data; evidence/logs must be minimized and redacted.
- Provider secrets, AgentField API credentials, and access to contract source material are separate capabilities.
- Do not place credentials in URLs or command-line arguments that may be logged.
- Fallback behavior must be explicit and observable.

## Acceptance ladder

1. Exact Contract-AF source/runtime identity known.
2. Package starts and node registers.
3. Harness provider/model resolves as intended.
4. Direct `.ai()` provider/model resolves as intended.
5. Required provider env/base reaches the actual model clients.
6. Minimal harness/direct calls succeed as applicable.
7. Execution evidence shows intended provider/model and no unintended fallback.
8. Contract-analysis canary produces semantically valid, evidence-grounded risk output.

Health/registration alone is not provider or semantic PASS.

## Failure classes

Use: `BOOTSTRAP_ADMISSION`, `MODEL_RESOLUTION`, `ENV_PROPAGATION`, `BASE_URL_LOSS`, `AUTH`, `FALLBACK`, `TRANSPORT`, `SEMANTIC`.

Patch the first failing layer only.
