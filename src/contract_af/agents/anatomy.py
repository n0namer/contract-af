"""Contract Anatomist agent — structural parsing of contract documents.

Programmatic extraction of sections, defined terms, cross-references,
exhibits, key dates, and risk surface signals. Uses regex-based parsing
as the primary path; delegates to a .harness() agent only when
programmatic parsing finds ambiguity.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Any

from contract_af.models import (
    AnatomyResult,
    CrossRef,
    DefinedTerm,
    Exhibit,
    IntakeResult,
    KeyDate,
    RiskSignal,
    Section,
    Severity,
)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Section/article headers (ordered by specificity)
_ARTICLE_PATTERN = re.compile(
    r"^(?:ARTICLE\s+([IVXLCDM]+|\d+))[.:\s—–-]+\s*(.+)",
    re.MULTILINE | re.IGNORECASE,
)
_SECTION_MAJOR_PATTERN = re.compile(
    r"^(\d+)\.\s+([A-Z][A-Z\s,;&/()-]{2,})",
    re.MULTILINE,
)
_SECTION_SUB_PATTERN = re.compile(
    r"^(\d+\.\d+(?:\.\d+)*)\s+(.+)",
    re.MULTILINE,
)
_SECTION_KEYWORD_PATTERN = re.compile(
    r"^Section\s+(\d+(?:\.\d+)*)[.:\s—–-]+\s*(.+)",
    re.MULTILINE | re.IGNORECASE,
)

# Defined terms — quoted capitalized phrases
_DEFINED_TERM_QUOTED = re.compile(r'"([A-Z][^"]{2,})"')
_DEFINED_TERM_BOLD = re.compile(r"\*\*([A-Z][^*]{2,})\*\*")

# Cross-references
_CROSS_REF_PATTERN = re.compile(
    r"(?:as\s+defined\s+in|pursuant\s+to|subject\s+to|"
    r"in\s+accordance\s+with|under|set\s+forth\s+in|"
    r"described\s+in|referred\s+to\s+in|notwithstanding)\s+"
    r"(?:Section|Article|Clause)\s+(\d+(?:\.\d+)*)",
    re.IGNORECASE,
)
_SIMPLE_REF_PATTERN = re.compile(
    r"(?:Section|Article|Clause)\s+(\d+(?:\.\d+)*)",
    re.IGNORECASE,
)

# Exhibits, schedules, appendices
_EXHIBIT_PATTERN = re.compile(
    r"^((?:Exhibit|Schedule|Appendix|Annex|Attachment)\s+[A-Z0-9]+)"
    r"[.:\s—–-]*\s*(.*)",
    re.MULTILINE | re.IGNORECASE,
)

# Key dates
_FULL_DATE_PATTERN = re.compile(
    r"(\w+\s+\d{1,2},?\s+\d{4})",
)
_DATE_CONTEXT_PATTERN = re.compile(
    r"((?:effective\s+date|commencement\s+date|termination\s+date|"
    r"expiration\s+date|start\s+date|end\s+date|renewal\s+date|"
    r"notice\s+period|term\s+of)[^.]*\.)",
    re.IGNORECASE,
)
_TERM_LENGTH_PATTERN = re.compile(
    r"((?:term|duration|period)\s+(?:of|shall\s+be)\s+[^.]*\.)",
    re.IGNORECASE,
)

# Risk-signal helpers
_BROAD_SCOPE_PATTERN = re.compile(
    r"(?:whether\s+or\s+not|including\s+but\s+not\s+limited\s+to|"
    r"without\s+limitation|in\s+any\s+form|any\s+and\s+all|"
    r"directly\s+or\s+indirectly|whatsoever|however\s+caused)",
    re.IGNORECASE,
)
_NESTED_CONDITION_PATTERN = re.compile(
    r"\b(?:if|then|unless|except|notwithstanding|provided\s+that|"
    r"provided,?\s+however|subject\s+to|excluding)\b",
    re.IGNORECASE,
)

# Roman numeral mapping for article numbering
_ROMAN_MAP: dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
}

# Upper threshold for cross-refs per section to flag complexity
_CROSS_REF_THRESHOLD = 3
# Nested-condition count threshold per section
_NESTED_CONDITION_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def analyze_structure(
    app: Any,
    document_text: str,
    intake: IntakeResult,
) -> AnatomyResult:
    """Build a structural map of the contract document.

    Primary path is deterministic regex parsing. Falls back to the
    ``contract-af.anatomist`` harness when programmatic extraction
    encounters ambiguity (e.g. no sections found).
    """
    sections = _extract_sections(document_text)

    # Fallback: if programmatic parsing found nothing, delegate to harness
    if not sections and app is not None:
        return await _harness_fallback(app, document_text, intake)

    defined_terms = _extract_defined_terms(document_text, sections)
    cross_references = _extract_cross_references(document_text, sections)
    exhibits = _extract_exhibits(document_text)
    key_dates = _extract_key_dates(document_text, sections)
    risk_surface = _compute_risk_signals(
        sections, defined_terms, cross_references, document_text,
    )

    return AnatomyResult(
        sections=sections,
        defined_terms=defined_terms,
        cross_references=cross_references,
        exhibits=exhibits,
        key_dates=key_dates,
        risk_surface=risk_surface,
    )


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------


def _extract_sections(text: str) -> list[Section]:
    """Extract all section/article headers from the document text."""
    seen_numbers: set[str] = set()
    sections: list[Section] = []

    # 1. Articles (ARTICLE I, ARTICLE 2, ...)
    for match in _ARTICLE_PATTERN.finditer(text):
        raw_num = match.group(1).strip()
        num = str(_ROMAN_MAP.get(raw_num.upper(), raw_num))
        title = match.group(2).strip().rstrip(".")
        if num not in seen_numbers:
            seen_numbers.add(num)
            sections.append(Section(number=num, title=title))

    # 2. "Section X.Y — Title"
    for match in _SECTION_KEYWORD_PATTERN.finditer(text):
        num = match.group(1).strip()
        title = match.group(2).strip().rstrip(".")
        if num not in seen_numbers:
            seen_numbers.add(num)
            sections.append(Section(number=num, title=title))

    # 3. Major numbered sections: "1. DEFINITIONS"
    for match in _SECTION_MAJOR_PATTERN.finditer(text):
        num = match.group(1).strip()
        title = match.group(2).strip().rstrip(".")
        if num not in seen_numbers:
            seen_numbers.add(num)
            sections.append(Section(number=num, title=title))

    # 4. Subsections: "1.1 Something"
    for match in _SECTION_SUB_PATTERN.finditer(text):
        num = match.group(1).strip()
        title = match.group(2).strip().rstrip(".")
        if num not in seen_numbers:
            seen_numbers.add(num)
            parent = num.rsplit(".", 1)[0]
            sections.append(Section(number=num, title=title))
            # Wire subsection to parent
            _add_subsection(sections, parent, num)

    # Sort by a key that orders numerically
    sections.sort(key=_section_sort_key)
    return sections


def _add_subsection(sections: list[Section], parent_num: str, child_num: str) -> None:
    """Link a subsection number to its parent section (immutable append)."""
    for idx, sec in enumerate(sections):
        if sec.number == parent_num and child_num not in sec.subsections:
            updated = Section(
                number=sec.number,
                title=sec.title,
                page_range=sec.page_range,
                subsections=[*sec.subsections, child_num],
            )
            sections[idx] = updated
            return


def _section_sort_key(section: Section) -> tuple[int, ...]:
    """Produce a numeric tuple for sorting '1' < '1.1' < '2'."""
    parts: list[int] = []
    for part in section.number.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


# ---------------------------------------------------------------------------
# Defined-term extraction
# ---------------------------------------------------------------------------


def _extract_defined_terms(
    text: str,
    sections: list[Section],
) -> list[DefinedTerm]:
    """Find defined terms (quoted capitalised phrases) and count usages."""
    # Locate definitions section if present
    def_section_ref = _find_definitions_section(sections)

    # Collect all quoted capitalised terms
    raw_terms: dict[str, list[int]] = {}
    for match in _DEFINED_TERM_QUOTED.finditer(text):
        term = match.group(1).strip()
        raw_terms.setdefault(term, []).append(match.start())

    # Also check bold-style definitions (markdown)
    for match in _DEFINED_TERM_BOLD.finditer(text):
        term = match.group(1).strip()
        raw_terms.setdefault(term, []).append(match.start())

    results: list[DefinedTerm] = []
    for term, positions in raw_terms.items():
        # Skip very short or all-caps acronyms (likely not defined terms)
        if len(term) < 3:
            continue

        # Try to extract definition text (the sentence containing the first occurrence)
        first_pos = positions[0]
        definition_text = _extract_definition_sentence(text, first_pos, term)

        # Determine section where the term is first defined
        section_ref = _locate_section_for_position(text, first_pos, sections)
        if not section_ref and def_section_ref:
            section_ref = def_section_ref

        results.append(
            DefinedTerm(
                term=term,
                definition_text=definition_text,
                section_ref=section_ref or "unknown",
                usage_count=len(positions),
            )
        )

    return results


def _find_definitions_section(sections: list[Section]) -> str:
    """Return the section number of a 'Definitions' section, if any."""
    for sec in sections:
        if re.search(r"definition", sec.title, re.IGNORECASE):
            return sec.number
    return ""


def _extract_definition_sentence(text: str, pos: int, term: str) -> str:
    """Extract the sentence surrounding position *pos* as definition text."""
    # Walk back to prior sentence boundary
    start = max(0, pos - 300)
    end = min(len(text), pos + 500)
    window = text[start:end]

    # Find the sentence containing the term
    sentences = re.split(r"(?<=[.;])\s+", window)
    for sentence in sentences:
        if term in sentence:
            return sentence.strip()[:500]
    return ""


def _locate_section_for_position(
    text: str,
    pos: int,
    sections: list[Section],
) -> str:
    """Given a character position, find which section it falls under."""
    # Build a position map for section headers
    best_section = ""
    best_pos = -1

    for sec in sections:
        # Find the header position in the text
        patterns = [
            re.escape(f"{sec.number}. {sec.title}"),
            re.escape(f"{sec.number} {sec.title}"),
            rf"Section\s+{re.escape(sec.number)}",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match and match.start() <= pos and match.start() > best_pos:
                best_pos = match.start()
                best_section = sec.number
                break

    return best_section


# ---------------------------------------------------------------------------
# Cross-reference extraction
# ---------------------------------------------------------------------------


def _extract_cross_references(
    text: str,
    sections: list[Section],
) -> list[CrossRef]:
    """Find cross-references between sections."""
    section_numbers = {sec.number for sec in sections}
    refs: list[CrossRef] = []
    seen: set[tuple[str, str, str]] = set()

    # Contextual cross-references ("pursuant to Section X")
    relationship_patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"as\s+defined\s+in\s+(?:Section|Article|Clause)\s+(\d+(?:\.\d+)*)", re.IGNORECASE), "as_defined_in"),
        (re.compile(r"pursuant\s+to\s+(?:Section|Article|Clause)\s+(\d+(?:\.\d+)*)", re.IGNORECASE), "subject_to"),
        (re.compile(r"subject\s+to\s+(?:Section|Article|Clause)\s+(\d+(?:\.\d+)*)", re.IGNORECASE), "subject_to"),
        (re.compile(r"notwithstanding\s+(?:Section|Article|Clause)\s+(\d+(?:\.\d+)*)", re.IGNORECASE), "notwithstanding"),
        (re.compile(r"(?:in\s+accordance\s+with|under|set\s+forth\s+in|described\s+in|referred\s+to\s+in)\s+(?:Section|Article|Clause)\s+(\d+(?:\.\d+)*)", re.IGNORECASE), "references"),
    ]

    for pattern, rel_type in relationship_patterns:
        for match in pattern.finditer(text):
            to_section = match.group(1)
            from_section = _locate_section_for_position(
                text, match.start(), sections,
            )
            if not from_section:
                continue

            key = (from_section, to_section, rel_type)
            if key not in seen:
                seen.add(key)
                refs.append(
                    CrossRef(
                        from_section=from_section,
                        to_section=to_section,
                        relationship_type=rel_type,
                    )
                )

    # Simple references not yet captured
    for match in _SIMPLE_REF_PATTERN.finditer(text):
        to_section = match.group(1)
        from_section = _locate_section_for_position(
            text, match.start(), sections,
        )
        if not from_section or from_section == to_section:
            continue
        key = (from_section, to_section, "references")
        if key not in seen:
            seen.add(key)
            refs.append(
                CrossRef(
                    from_section=from_section,
                    to_section=to_section,
                    relationship_type="references",
                )
            )

    return refs


# ---------------------------------------------------------------------------
# Exhibit / schedule extraction
# ---------------------------------------------------------------------------


def _extract_exhibits(text: str) -> list[Exhibit]:
    """Find exhibits, schedules, appendices, annexes, and attachments."""
    exhibits: list[Exhibit] = []
    seen_labels: set[str] = set()

    for match in _EXHIBIT_PATTERN.finditer(text):
        label = match.group(1).strip()
        title = match.group(2).strip().rstrip(".")
        normalised_label = label.upper()

        if normalised_label in seen_labels:
            continue
        seen_labels.add(normalised_label)

        # Find which sections reference this exhibit
        ref_pattern = re.compile(re.escape(label), re.IGNORECASE)
        modifies: list[str] = []
        for ref_match in ref_pattern.finditer(text):
            # Don't count the exhibit header itself
            if ref_match.start() == match.start():
                continue
            # Try to figure out which section this reference falls in
            # (lightweight: look backwards for a section number)
            preceding = text[max(0, ref_match.start() - 500) : ref_match.start()]
            sec_match = re.findall(r"(?:Section|Article)\s+(\d+(?:\.\d+)*)", preceding, re.IGNORECASE)
            if sec_match:
                sec_num = sec_match[-1]
                if sec_num not in modifies:
                    modifies.append(sec_num)

        exhibits.append(
            Exhibit(
                label=label,
                title=title if title else label,
                modifies_sections=modifies,
            )
        )

    return exhibits


# ---------------------------------------------------------------------------
# Key-date extraction
# ---------------------------------------------------------------------------


def _extract_key_dates(
    text: str,
    sections: list[Section],
) -> list[KeyDate]:
    """Extract effective dates, term lengths, renewal dates, notice periods."""
    dates: list[KeyDate] = []
    seen_descriptions: set[str] = set()

    # Date-context sentences (effective date, termination date, etc.)
    for match in _DATE_CONTEXT_PATTERN.finditer(text):
        sentence = match.group(1).strip()
        # Pull out the actual date if present
        date_match = _FULL_DATE_PATTERN.search(sentence)
        date_str = date_match.group(1) if date_match else ""

        description = _summarise_date_context(sentence)
        if description in seen_descriptions:
            continue
        seen_descriptions.add(description)

        section_ref = _locate_section_for_position(
            text, match.start(), sections,
        )

        dates.append(
            KeyDate(
                date=date_str,
                description=description,
                section_ref=section_ref or "unknown",
            )
        )

    # Term-length clauses without explicit dates
    for match in _TERM_LENGTH_PATTERN.finditer(text):
        sentence = match.group(1).strip()
        description = _summarise_date_context(sentence)
        if description in seen_descriptions:
            continue
        seen_descriptions.add(description)

        section_ref = _locate_section_for_position(
            text, match.start(), sections,
        )

        dates.append(
            KeyDate(
                date="",
                description=description,
                section_ref=section_ref or "unknown",
            )
        )

    return dates


def _summarise_date_context(sentence: str) -> str:
    """Return a short description derived from the sentence."""
    # Truncate to a readable length
    cleaned = re.sub(r"\s+", " ", sentence).strip()
    return cleaned[:200]


# ---------------------------------------------------------------------------
# Risk-signal computation
# ---------------------------------------------------------------------------


def _compute_risk_signals(
    sections: list[Section],
    defined_terms: list[DefinedTerm],
    cross_references: list[CrossRef],
    text: str,
) -> list[RiskSignal]:
    """Generate risk-surface signals from structural data."""
    signals: list[RiskSignal] = []

    # 1. Sections with > threshold cross-references = high structural complexity
    ref_counts: Counter[str] = Counter()
    for ref in cross_references:
        ref_counts[ref.from_section] += 1
        ref_counts[ref.to_section] += 1

    for sec_num, count in ref_counts.items():
        if count > _CROSS_REF_THRESHOLD:
            signals.append(
                RiskSignal(
                    section=sec_num,
                    signal_type="heavy_cross_refs",
                    description=(
                        f"Section {sec_num} has {count} cross-references, "
                        f"indicating high structural complexity."
                    ),
                    severity=Severity.HIGH if count > 6 else Severity.MEDIUM,
                )
            )

    # 2. Defined terms with broad-scope language
    for dt in defined_terms:
        if _BROAD_SCOPE_PATTERN.search(dt.definition_text):
            signals.append(
                RiskSignal(
                    section=dt.section_ref,
                    signal_type="broad_definition",
                    description=(
                        f'Defined term "{dt.term}" uses broad scope language '
                        f"in its definition."
                    ),
                    severity=Severity.MEDIUM,
                )
            )

    # 3. Sections longer than average = unusual_length
    section_lengths = _measure_section_lengths(text, sections)
    if section_lengths:
        avg_len = statistics.mean(section_lengths.values()) if section_lengths else 0
        for sec_num, length in section_lengths.items():
            if avg_len > 0 and length > avg_len * 2:
                signals.append(
                    RiskSignal(
                        section=sec_num,
                        signal_type="unusual_length",
                        description=(
                            f"Section {sec_num} is {length} chars, "
                            f"significantly longer than the average "
                            f"({int(avg_len)} chars)."
                        ),
                        severity=Severity.MEDIUM,
                    )
                )

    # 4. Nested conditions (if/then/unless/except/notwithstanding)
    for sec_num, sec_text in _iter_section_texts(text, sections):
        condition_count = len(_NESTED_CONDITION_PATTERN.findall(sec_text))
        if condition_count >= _NESTED_CONDITION_THRESHOLD:
            signals.append(
                RiskSignal(
                    section=sec_num,
                    signal_type="nested_conditions",
                    description=(
                        f"Section {sec_num} contains {condition_count} "
                        f"conditional qualifiers, creating complex logic."
                    ),
                    severity=(
                        Severity.HIGH if condition_count > 6
                        else Severity.MEDIUM
                    ),
                )
            )

    return signals


def _measure_section_lengths(
    text: str,
    sections: list[Section],
) -> dict[str, int]:
    """Approximate char-length for each section."""
    lengths: dict[str, int] = {}
    section_positions = _build_section_positions(text, sections)

    sorted_positions = sorted(section_positions, key=lambda x: x[1])
    for i, (sec_num, start) in enumerate(sorted_positions):
        end = sorted_positions[i + 1][1] if i + 1 < len(sorted_positions) else len(text)
        lengths[sec_num] = end - start

    return lengths


def _build_section_positions(
    text: str,
    sections: list[Section],
) -> list[tuple[str, int]]:
    """Find the character position of each section header in the text."""
    positions: list[tuple[str, int]] = []
    for sec in sections:
        patterns = [
            rf"(?:^|\n)\s*{re.escape(sec.number)}\.\s+{re.escape(sec.title[:20])}",
            rf"(?:^|\n)\s*{re.escape(sec.number)}\s+{re.escape(sec.title[:20])}",
            rf"Section\s+{re.escape(sec.number)}",
            rf"ARTICLE\s+(?:{re.escape(sec.number)}|[IVXLCDM]+)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                positions.append((sec.number, match.start()))
                break

    return positions


def _iter_section_texts(
    text: str,
    sections: list[Section],
) -> list[tuple[str, str]]:
    """Yield (section_number, section_text) pairs."""
    section_positions = _build_section_positions(text, sections)
    sorted_positions = sorted(section_positions, key=lambda x: x[1])

    results: list[tuple[str, str]] = []
    for i, (sec_num, start) in enumerate(sorted_positions):
        end = sorted_positions[i + 1][1] if i + 1 < len(sorted_positions) else len(text)
        results.append((sec_num, text[start:end]))

    return results


# ---------------------------------------------------------------------------
# Harness fallback
# ---------------------------------------------------------------------------


async def _harness_fallback(
    app: Any,
    document_text: str,
    intake: IntakeResult,
) -> AnatomyResult:
    """Delegate to the contract-af.anatomist harness when regex parsing
    cannot extract structure (e.g. non-standard formatting)."""
    result = await app.call(
        "contract-af.anatomist",
        input={
            "document_text": document_text,
            "intake": intake.model_dump(),
            "reason": "Programmatic section extraction found no sections; "
                      "delegating to harness for structural analysis.",
        },
    )
    # The harness returns an AnatomyResult-shaped dict
    if isinstance(result, AnatomyResult):
        return result
    return AnatomyResult.model_validate(result)
