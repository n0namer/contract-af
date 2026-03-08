"""Contract Anatomist agent — AI-driven structural parsing.

Uses .harness() to navigate the full contract document and extract
sections, defined terms, cross-references, exhibits, key dates,
and risk surface signals. The harness writes the document to a temp
file and the coding agent reads + parses it with full tool access.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from contract_af.models import AnatomyResult, IntakeResult


class _AnatomistResult(BaseModel):
    """Schema for harness output — matches AnatomyResult fields."""

    sections: list[dict[str, Any]] = Field(default_factory=list)
    defined_terms: list[dict[str, Any]] = Field(default_factory=list)
    cross_references: list[dict[str, Any]] = Field(default_factory=list)
    exhibits: list[dict[str, Any]] = Field(default_factory=list)
    key_dates: list[dict[str, Any]] = Field(default_factory=list)
    risk_surface: list[dict[str, Any]] = Field(default_factory=list)


_ANATOMIST_PROMPT = """\
You are a contract anatomist. Your task is to parse the contract document
in `contract.txt` (in the current directory) and extract its complete
structural map.

Contract metadata:
{metadata}

Read the FULL document and extract ALL of the following:

1. sections — every section and article header:
   {{number: "1", title: "DEFINITIONS", subsections: ["1.1", "1.2"]}}
   Include ALL levels (articles, major sections, subsections).

2. defined_terms — every defined term (quoted capitalized phrases):
   {{term: "Affiliate", definition_text: "means...",
    section_ref: "1.1", usage_count: 5}}

3. cross_references — inter-section references:
   {{from_section: "13.1", to_section: "1.1",
    relationship_type: "as_defined_in"}}
   Types: as_defined_in, subject_to, notwithstanding, references

4. exhibits — schedules, appendices, annexes:
   {{label: "Exhibit A", title: "Statement of Work",
    modifies_sections: ["3", "4"]}}

5. key_dates — effective dates, term lengths, renewal dates:
   {{date: "November 17, 2021", description: "Effective Date",
    section_ref: "preamble"}}

6. risk_surface — structural risk signals:
   {{section: "13", signal_type: "heavy_cross_refs",
    description: "...", severity: "high"}}
   signal_type: heavy_cross_refs, broad_definition, unusual_length,
   nested_conditions
   severity: critical, high, medium, low

Be EXHAUSTIVE with sections and defined terms.
Every section header in the document must appear in your output.
"""


def _extract_harness_result(result: object) -> _AnatomistResult:
    """Extract parsed result from HarnessResult, with fallbacks."""
    is_error = bool(getattr(result, "is_error", False))
    if is_error:
        error_msg = getattr(result, "error_message", None)
        raise RuntimeError(f"Anatomist harness error: {error_msg}")

    parsed = getattr(result, "parsed", None)
    if isinstance(parsed, _AnatomistResult):
        return parsed
    if isinstance(parsed, dict):
        return _AnatomistResult.model_validate(parsed)

    # Try raw text
    result_text = getattr(result, "result", None) or getattr(result, "text", None)
    if result_text and isinstance(result_text, str):
        try:
            data = json.loads(result_text)
            return _AnatomistResult.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            pass

    raise TypeError(f"Could not parse anatomist result: {type(result).__name__}")


async def analyze_structure(
    app: Any,
    document_text: str,
    intake: IntakeResult,
) -> AnatomyResult:
    """Build a structural map of the contract via .harness() AI analysis."""
    workdir = tempfile.mkdtemp(prefix="contract-af-anatomy-")
    try:
        # Write contract to temp file for the harness agent to read
        contract_path = Path(workdir) / "contract.txt"
        contract_path.write_text(document_text, encoding="utf-8")

        metadata = json.dumps(intake.model_dump(), default=str, indent=2)
        prompt = _ANATOMIST_PROMPT.format(metadata=metadata)

        result = await app.harness(
            prompt=prompt,
            schema=_AnatomistResult,
            cwd=workdir,
        )

        parsed = _extract_harness_result(result)
        return AnatomyResult.model_validate(parsed.model_dump())

    finally:
        shutil.rmtree(workdir, ignore_errors=True)
