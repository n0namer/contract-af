"""CLI entry point for Contract-AF."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from contract_af.utils.document_loader import load_document


def main() -> None:
    """Parse arguments and dispatch to the requested sub-command."""
    parser = argparse.ArgumentParser(
        description="Contract-AF: Legal contract risk analyzer",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- analyze ---
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a contract")
    analyze_parser.add_argument("file", help="Path to contract file (PDF, DOCX, TXT)")
    analyze_parser.add_argument(
        "--context", default="", help="Your role and concerns (e.g. 'I am the customer')"
    )
    analyze_parser.add_argument(
        "--output", "-o", default=None, help="Output file for report (default: stdout)"
    )
    analyze_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        dest="output_format",
        help="Output format (default: markdown)",
    )

    # --- serve ---
    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")

    args = parser.parse_args()

    if args.command == "analyze":
        asyncio.run(_analyze(args))
    elif args.command == "serve":
        _serve(args)
    else:
        parser.print_help()
        sys.exit(1)


async def _analyze(args: argparse.Namespace) -> None:
    """Load the document and run the analysis pipeline."""
    full_text, _ = load_document(args.file)
    print(f"Loaded {len(full_text)} characters from {args.file}", file=sys.stderr)

    from contract_af.pipeline.orchestrator import analyze_contract

    try:
        from contract_af.app import app as agent_app
    except Exception:
        agent_app = None  # Graceful fallback for testing without AgentField

    report = await analyze_contract(agent_app, full_text, args.context)

    if args.output_format == "json":
        output = json.dumps(report.structured_json, indent=2)
    else:
        output = report.risk_report_md

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)


def _serve(args: argparse.Namespace) -> None:
    """Start the uvicorn server."""
    import uvicorn

    uvicorn.run("contract_af.api:app", host=args.host, port=args.port, reload=True)


if __name__ == "__main__":
    main()
