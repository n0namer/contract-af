"""End-to-end test for Contract-AF via the AgentField control plane API.

Submits a contract document + user context to the running stack and polls
for results — exactly how a backend developer would integrate.

Prerequisites:
    docker compose up -d          # start control plane + agent

Usage:
    python test_harness.py                                       # default contract
    python test_harness.py tests/fixtures/sample_nda.txt         # specific file
    python test_harness.py --context "I am the employer"         # custom context
    python test_harness.py --server http://localhost:9090         # custom CP URL
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

CONTROL_PLANE = os.getenv("AGENTFIELD_SERVER", "http://localhost:8080")
DEFAULT_CONTRACT = "tests/fixtures/real_contract.txt"
DEFAULT_CONTEXT = (
    "I am the customer reviewing this agreement for renewal. "
    "Flag liability caps, IP ownership, indemnification, termination terms, "
    "and any auto-renewal or non-compete clauses."
)
POLL_INTERVAL_S = 10
MAX_WAIT_S = 1800  # 30 minutes


# ---------------------------------------------------------------------------
# Helpers — stdlib only, no pip dependencies
# ---------------------------------------------------------------------------


def _post_json(url: str, payload: dict) -> dict:
    """POST JSON to *url* and return parsed response."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _get_json(url: str) -> dict:
    """GET *url* and return parsed JSON response."""
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Contract-AF E2E test — submit contract via AgentField API",
    )
    parser.add_argument(
        "contract",
        nargs="?",
        default=DEFAULT_CONTRACT,
        help="Path to contract text file (default: %(default)s)",
    )
    parser.add_argument(
        "--context",
        default=DEFAULT_CONTEXT,
        help="User context describing your role and focus areas",
    )
    parser.add_argument(
        "--server",
        default=CONTROL_PLANE,
        help="AgentField control plane URL (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        default="exampl/result.json",
        help="Output file for the full report JSON (default: %(default)s)",
    )
    args = parser.parse_args()

    # ── 1. Read the contract ─────────────────────────────────────────────

    if not os.path.isfile(args.contract):
        print(f"ERROR: contract file not found: {args.contract}")
        sys.exit(1)

    with open(args.contract, encoding="utf-8") as fh:
        document_text = fh.read()

    char_count = len(document_text)
    word_count = len(document_text.split())
    print(f"Contract : {args.contract}")
    print(f"           {char_count:,} chars · {word_count:,} words")
    print(f"Context  : {args.context[:120]}{'…' if len(args.context) > 120 else ''}")
    print(f"Server   : {args.server}")

    # ── 2. Submit to control plane ───────────────────────────────────────

    execute_url = f"{args.server}/api/v1/execute/async/contract-af.analyze"

    payload = {
        "input": {
            "document_text": document_text,
            "user_context": args.context,
        },
    }

    print(f"\nPOST {execute_url}")
    start = time.monotonic()

    try:
        submit_resp = _post_json(execute_url, payload)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"ERROR: failed to submit — {exc}")
        print("Is the stack running?  docker compose up -d")
        sys.exit(1)

    execution_id = submit_resp.get("execution_id", "")
    print(f"Execution: {execution_id}")
    print(f"Status   : {submit_resp.get('status', '?')}")

    if not execution_id:
        print(f"ERROR: no execution_id in response: {json.dumps(submit_resp, indent=2)}")
        sys.exit(1)

    # ── 3. Poll for completion ───────────────────────────────────────────

    poll_url = f"{args.server}/api/v1/executions/{execution_id}"
    print(f"\nPolling  : {poll_url}")

    final_data: dict = {}

    while True:
        elapsed = time.monotonic() - start
        if elapsed > MAX_WAIT_S:
            print(f"\nTIMEOUT after {elapsed:.0f}s")
            sys.exit(1)

        time.sleep(POLL_INTERVAL_S)

        try:
            status_data = _get_json(poll_url)
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            print(f"  [{elapsed:6.0f}s] poll error: {exc}")
            continue

        status = status_data.get("status", "unknown")
        elapsed = time.monotonic() - start
        print(f"  [{elapsed:6.0f}s] status={status}")

        if status == "succeeded":
            final_data = status_data
            break

        if status == "failed":
            err = status_data.get("error", status_data.get("error_message", "unknown"))
            print(f"\nFAILED: {err}")
            _save_json(args.output, status_data)
            sys.exit(1)

    elapsed = time.monotonic() - start

    # ── 4. Save results ──────────────────────────────────────────────────

    report = final_data.get("result", {})
    _save_json(args.output, report)

    # ── 5. Print summary ─────────────────────────────────────────────────

    _print_summary(report, elapsed, args.contract, char_count, word_count)


def _save_json(path: str, data: dict) -> None:
    """Write *data* as pretty JSON to *path*, creating parent dirs."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    print(f"\nResults saved to {path}")


def _print_summary(
    report: dict,
    elapsed: float,
    contract_path: str,
    char_count: int,
    word_count: int,
) -> None:
    """Print human-readable summary of the analysis."""
    sep = "=" * 60

    print(f"\n{sep}")
    print("CONTRACT-AF  E2E RESULTS")
    print(sep)
    print(f"  Wall clock      : {elapsed:.1f}s ({elapsed / 60:.1f}m)")
    print(f"  Contract        : {os.path.basename(contract_path)}")
    print(f"                    {char_count:,} chars · {word_count:,} words")

    # Pipeline metadata
    metadata = report.get("metadata", {})
    if metadata:
        print(f"  Pipeline time   : {metadata.get('elapsed_seconds', 'N/A')}s")
        print(f"  Iterations      : {metadata.get('coverage_iterations', 'N/A')}")
        print(f"  Total findings  : {metadata.get('total_findings', 'N/A')}")
        print(f"  Clusters        : {metadata.get('clusters_analyzed', 'N/A')}")
        print(f"  Combo risks     : {metadata.get('combination_risks', 'N/A')}")

    # Risk profile
    structured = report.get("structured_json", {})
    risk_profile = structured.get(
        "overall_risk_profile",
        report.get("overall_risk_profile", {}),
    )
    if risk_profile:
        print(f"\n  Overall risk    : {risk_profile.get('overall_risk', 'N/A')}")
        print(f"  Recommendation  : {risk_profile.get('deal_recommendation', 'N/A')}")
        scores = risk_profile.get("category_scores", {})
        if scores:
            print("  Category scores :")
            for cat, score in sorted(scores.items(), key=lambda x: -float(x[1])):
                print(f"    {cat:30s} {float(score):5.1f}")

    # Executive summary preview
    exec_summary = report.get("executive_summary", "")
    if exec_summary:
        preview = exec_summary[:600].replace("\n", "\n    ")
        print(f"\n  Executive summary (preview):")
        print(f"    {preview}{'…' if len(exec_summary) > 600 else ''}")

    print(f"\n{sep}")
    print(f"PASS — Contract-AF analysis completed in {elapsed:.1f}s")
    print(sep)


if __name__ == "__main__":
    main()
