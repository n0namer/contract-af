"""Tests for the contract anatomist — structural parsing of contract documents."""

from __future__ import annotations

import pytest

from contract_af.agents.anatomy import (
    _compute_risk_signals,
    _extract_cross_references,
    _extract_defined_terms,
    _extract_exhibits,
    _extract_key_dates,
    _extract_sections,
    analyze_structure,
)
from contract_af.models import (
    AnatomyResult,
    CrossRef,
    DefinedTerm,
    IntakeResult,
    Party,
    Section,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_intake(**overrides) -> IntakeResult:
    """Build a minimal IntakeResult for tests."""
    defaults = {
        "contract_type": "saas_agreement",
        "parties": [
            Party(name="Acme Cloud Inc.", role="provider", entity_type="corporation"),
            Party(name="TechStart LLC", role="customer", entity_type="llc"),
        ],
        "your_role": "customer",
        "jurisdiction": "Delaware, USA",
        "governing_law": "Delaware",
        "deal_structure": "SaaS subscription",
        "complexity": "standard",
        "confident": True,
    }
    return IntakeResult(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# 1. Section extraction
# ---------------------------------------------------------------------------


class TestSectionExtraction:
    """Given sample contract text, extracts sections with correct numbers and titles."""

    def test_extracts_major_sections(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        numbers = [s.number for s in sections]

        # All major sections 1-15 should be found
        for n in range(1, 16):
            assert str(n) in numbers, f"Section {n} not found"

    def test_extracts_subsections(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        numbers = [s.number for s in sections]

        # Subsections like 1.1, 2.1, etc. should be present
        assert "1.1" in numbers
        assert "2.1" in numbers
        assert "10.1" in numbers

    def test_section_titles_populated(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        for sec in sections:
            assert sec.title, f"Section {sec.number} has empty title"

    def test_sections_sorted_numerically(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        numbers = [s.number for s in sections]
        # "1" should come before "2", "2" before "10", etc.
        idx_1 = numbers.index("1")
        idx_2 = numbers.index("2")
        idx_10 = numbers.index("10")
        assert idx_1 < idx_2 < idx_10

    def test_parent_has_subsections_linked(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        sec_1 = next(s for s in sections if s.number == "1")
        # Section 1 should have subsections 1.1, 1.2, etc.
        assert len(sec_1.subsections) > 0
        assert "1.1" in sec_1.subsections

    def test_article_pattern_with_roman_numerals(self) -> None:
        text = (
            "ARTICLE I — DEFINITIONS\n"
            "Some definitions here.\n\n"
            "ARTICLE II — GRANT OF LICENSE\n"
            "Some license terms here.\n"
        )
        sections = _extract_sections(text)
        numbers = [s.number for s in sections]
        assert "1" in numbers
        assert "2" in numbers

    def test_section_keyword_pattern(self) -> None:
        text = (
            "Section 3.1 — Payment Terms\n"
            "The customer shall pay.\n\n"
            "Section 3.2 — Late Fees\n"
            "Interest accrues.\n"
        )
        sections = _extract_sections(text)
        numbers = [s.number for s in sections]
        assert "3.1" in numbers
        assert "3.2" in numbers


# ---------------------------------------------------------------------------
# 2. Defined term extraction
# ---------------------------------------------------------------------------


class TestDefinedTermExtraction:
    """Finds quoted capitalized terms like "Work Product", "Confidential Information"."""

    def test_finds_quoted_defined_terms(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        terms = _extract_defined_terms(sample_contract_text, sections)
        term_names = [t.term for t in terms]

        assert "Agreement" in term_names
        assert "Confidential Information" in term_names
        assert "Work Product" in term_names
        assert "Customer Data" in term_names

    def test_usage_count_greater_than_zero(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        terms = _extract_defined_terms(sample_contract_text, sections)

        for dt in terms:
            assert dt.usage_count >= 1, f'"{dt.term}" has zero usage count'

    def test_definition_text_populated(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        terms = _extract_defined_terms(sample_contract_text, sections)

        # At least some terms should have definition text
        terms_with_defs = [t for t in terms if t.definition_text]
        assert len(terms_with_defs) > 0

    def test_section_ref_assigned(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        terms = _extract_defined_terms(sample_contract_text, sections)

        # Terms defined in section 1 should have section_ref pointing there
        work_product = next((t for t in terms if t.term == "Work Product"), None)
        assert work_product is not None
        assert work_product.section_ref != "unknown"

    def test_skips_short_terms(self) -> None:
        text = '"OK" is not a real defined term but "Authorized Users" is.'
        sections: list[Section] = []
        terms = _extract_defined_terms(text, sections)
        term_names = [t.term for t in terms]
        assert "OK" not in term_names

    def test_finds_bold_defined_terms(self) -> None:
        text = '**Service Level Agreement** means the uptime commitments.'
        sections: list[Section] = []
        terms = _extract_defined_terms(text, sections)
        term_names = [t.term for t in terms]
        assert "Service Level Agreement" in term_names


# ---------------------------------------------------------------------------
# 3. Cross-reference detection
# ---------------------------------------------------------------------------


class TestCrossReferenceDetection:
    """Finds patterns like "pursuant to Section X", "as defined in Section Y"."""

    def test_finds_cross_references(self) -> None:
        """Use the fixture file which has richer cross-ref language."""
        fixture_path = (
            "/Users/santoshkumarradha/Documents/agentfield/code/examples/"
            "contract-af/tests/fixtures/sample_saas_agreement.txt"
        )
        with open(fixture_path) as f:
            text = f.read()

        sections = _extract_sections(text)
        refs = _extract_cross_references(text, sections)

        assert len(refs) > 0
        # Each cross-ref should have from/to sections and a relationship type
        for ref in refs:
            assert ref.from_section
            assert ref.to_section
            assert ref.relationship_type

    def test_detects_subject_to_pattern(self) -> None:
        text = (
            "1. DEFINITIONS\n"
            "Some text here.\n\n"
            "2. LICENSE\n"
            "Subject to the terms of Section 1, the license is granted.\n"
        )
        sections = _extract_sections(text)
        refs = _extract_cross_references(text, sections)
        to_sections = [r.to_section for r in refs]
        assert "1" in to_sections

    def test_detects_as_defined_in_pattern(self) -> None:
        text = (
            "1. DEFINITIONS\n"
            "Terms are defined here.\n\n"
            "2. LICENSE\n"
            'The "Service" as defined in Section 1 is granted.\n'
        )
        sections = _extract_sections(text)
        refs = _extract_cross_references(text, sections)
        as_defined = [r for r in refs if r.relationship_type == "as_defined_in"]
        assert len(as_defined) > 0

    def test_no_self_references(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        refs = _extract_cross_references(sample_contract_text, sections)

        for ref in refs:
            assert ref.from_section != ref.to_section, (
                f"Self-reference found: {ref.from_section} -> {ref.to_section}"
            )

    def test_deduplicates_references(self) -> None:
        text = (
            "1. DEFINITIONS\n"
            "Terms here.\n\n"
            "2. LICENSE\n"
            "Pursuant to Section 1 and also pursuant to Section 1, we grant.\n"
        )
        sections = _extract_sections(text)
        refs = _extract_cross_references(text, sections)
        # Same from/to/type triple should not appear twice
        keys = [(r.from_section, r.to_section, r.relationship_type) for r in refs]
        assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# 4. Exhibit detection
# ---------------------------------------------------------------------------


class TestExhibitDetection:
    """Finds Exhibit/Schedule/Appendix references."""

    def test_finds_exhibits_in_fixture_file(self) -> None:
        fixture_path = (
            "/Users/santoshkumarradha/Documents/agentfield/code/examples/"
            "contract-af/tests/fixtures/sample_saas_agreement.txt"
        )
        with open(fixture_path) as f:
            text = f.read()

        exhibits = _extract_exhibits(text)
        labels = [e.label for e in exhibits]
        # The fixture has "EXHIBIT A" at the bottom
        assert any("A" in label for label in labels), f"No Exhibit A found in {labels}"

    def test_finds_schedule_and_appendix(self) -> None:
        # _EXHIBIT_PATTERN requires labels at the start of a line
        text = (
            "Schedule 1 — Pricing Details\n"
            "See pricing info.\n\n"
            "Appendix B — Data Processing Agreement\n"
            "This appendix governs data processing.\n"
        )
        exhibits = _extract_exhibits(text)
        labels_upper = [e.label.upper() for e in exhibits]
        assert any("SCHEDULE" in l for l in labels_upper)
        assert any("APPENDIX" in l for l in labels_upper)

    def test_exhibit_title_populated(self) -> None:
        text = "Exhibit A — Service Level Agreement\nSome SLA terms.\n"
        exhibits = _extract_exhibits(text)
        assert len(exhibits) >= 1
        assert exhibits[0].title

    def test_deduplicates_exhibits(self) -> None:
        text = (
            "Exhibit A — SLA\n"
            "Some SLA content.\n\n"
            "See Exhibit A for details.\n"
        )
        exhibits = _extract_exhibits(text)
        labels_upper = [e.label.upper() for e in exhibits]
        assert labels_upper.count("EXHIBIT A") == 1


# ---------------------------------------------------------------------------
# 5. Key date extraction
# ---------------------------------------------------------------------------


class TestKeyDateExtraction:
    """Finds dates in "January 15, 2026" format."""

    def test_finds_effective_date(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        dates = _extract_key_dates(sample_contract_text, sections)

        # The fixture mentions "Effective Date" with "January 15, 2026"
        descriptions_lower = [d.description.lower() for d in dates]
        assert any("effective" in desc for desc in descriptions_lower), (
            f"No effective date found in {descriptions_lower}"
        )

    def test_date_string_extracted(self) -> None:
        # The date context pattern needs "effective date ... January 15, 2026."
        # with a sentence-ending period to match _DATE_CONTEXT_PATTERN.
        text = (
            "1. TERM\n"
            "The effective date of this agreement is January 15, 2026.\n"
        )
        sections = _extract_sections(text)
        dates = _extract_key_dates(text, sections)

        dates_with_values = [d for d in dates if d.date]
        assert len(dates_with_values) > 0
        assert "January 15, 2026" in dates_with_values[0].date

    def test_finds_termination_context(self) -> None:
        text = (
            "1. TERM\n"
            "The termination date shall be December 31, 2027.\n"
        )
        sections = _extract_sections(text)
        dates = _extract_key_dates(text, sections)
        assert any("termination" in d.description.lower() for d in dates)

    def test_finds_term_length_clause(self) -> None:
        text = (
            "10. TERM AND TERMINATION\n"
            "The term of this Agreement shall be twelve (12) months.\n"
        )
        sections = _extract_sections(text)
        dates = _extract_key_dates(text, sections)
        assert len(dates) > 0


# ---------------------------------------------------------------------------
# 6. Risk signal: broad definition
# ---------------------------------------------------------------------------


class TestRiskSignalBroadDefinition:
    """'Work Product' with 'whether or not' triggers broad_definition signal."""

    def test_broad_definition_detected(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        terms = _extract_defined_terms(sample_contract_text, sections)
        refs = _extract_cross_references(sample_contract_text, sections)

        signals = _compute_risk_signals(
            sections, terms, refs, sample_contract_text,
        )
        broad_signals = [s for s in signals if s.signal_type == "broad_definition"]
        assert len(broad_signals) > 0

        # "Work Product" specifically should trigger it (contains "whether or not")
        broad_descs = " ".join(s.description for s in broad_signals)
        assert "Work Product" in broad_descs

    def test_broad_definition_severity_is_medium(self, sample_contract_text: str) -> None:
        sections = _extract_sections(sample_contract_text)
        terms = _extract_defined_terms(sample_contract_text, sections)
        refs = _extract_cross_references(sample_contract_text, sections)

        signals = _compute_risk_signals(
            sections, terms, refs, sample_contract_text,
        )
        broad_signals = [s for s in signals if s.signal_type == "broad_definition"]
        for s in broad_signals:
            assert s.severity == Severity.MEDIUM

    def test_no_false_positive_on_normal_definition(self) -> None:
        text = (
            '1. DEFINITIONS\n'
            '1.1 "Service" means the cloud platform.\n'
        )
        sections = _extract_sections(text)
        terms = _extract_defined_terms(text, sections)
        refs: list[CrossRef] = []

        signals = _compute_risk_signals(sections, terms, refs, text)
        broad_signals = [s for s in signals if s.signal_type == "broad_definition"]
        assert len(broad_signals) == 0


# ---------------------------------------------------------------------------
# 7. Risk signal: heavy cross-refs
# ---------------------------------------------------------------------------


class TestRiskSignalHeavyCrossRefs:
    """Sections with >3 cross-references get flagged."""

    def test_heavy_cross_refs_with_synthetic_data(self) -> None:
        sections = [
            Section(number="1", title="DEFINITIONS"),
            Section(number="2", title="LICENSE"),
            Section(number="3", title="PAYMENT"),
        ]
        # Section "1" is referenced >3 times from various sections
        refs = [
            CrossRef(from_section="2", to_section="1", relationship_type="references"),
            CrossRef(from_section="3", to_section="1", relationship_type="references"),
            CrossRef(from_section="2", to_section="1", relationship_type="subject_to"),
            CrossRef(from_section="3", to_section="1", relationship_type="as_defined_in"),
        ]
        terms: list[DefinedTerm] = []
        text = "dummy text"

        signals = _compute_risk_signals(sections, terms, refs, text)
        heavy = [s for s in signals if s.signal_type == "heavy_cross_refs"]
        assert len(heavy) > 0
        assert any(s.section == "1" for s in heavy)

    def test_heavy_cross_refs_severity_scales(self) -> None:
        sections = [
            Section(number="1", title="DEFINITIONS"),
            Section(number="2", title="LICENSE"),
        ]
        # 7 references to section "1" => severity should be HIGH (>6)
        refs = [
            CrossRef(from_section="2", to_section="1", relationship_type=f"ref_{i}")
            for i in range(7)
        ]
        terms: list[DefinedTerm] = []
        text = "dummy text"

        signals = _compute_risk_signals(sections, terms, refs, text)
        heavy = [s for s in signals if s.signal_type == "heavy_cross_refs"]
        assert any(s.severity == Severity.HIGH for s in heavy)

    def test_no_flag_below_threshold(self) -> None:
        sections = [
            Section(number="1", title="DEFINITIONS"),
            Section(number="2", title="LICENSE"),
        ]
        # Only 2 references — below the threshold of 3
        refs = [
            CrossRef(from_section="2", to_section="1", relationship_type="references"),
            CrossRef(from_section="1", to_section="2", relationship_type="references"),
        ]
        terms: list[DefinedTerm] = []
        text = "dummy text"

        signals = _compute_risk_signals(sections, terms, refs, text)
        heavy = [s for s in signals if s.signal_type == "heavy_cross_refs"]
        assert len(heavy) == 0


# ---------------------------------------------------------------------------
# 8. Full integration
# ---------------------------------------------------------------------------


class TestFullIntegration:
    """Run analyze_structure on sample_contract_text, verify AnatomyResult fields."""

    async def test_analyze_structure_returns_anatomy_result(
        self, sample_contract_text: str,
    ) -> None:
        intake = _make_intake()
        result = await analyze_structure(
            app=None,  # no harness fallback needed — text has sections
            document_text=sample_contract_text,
            intake=intake,
        )

        assert isinstance(result, AnatomyResult)

    async def test_all_fields_populated(
        self, sample_contract_text: str,
    ) -> None:
        intake = _make_intake()
        result = await analyze_structure(
            app=None,
            document_text=sample_contract_text,
            intake=intake,
        )

        assert len(result.sections) > 0
        assert len(result.defined_terms) > 0
        # The simple fixture lacks "pursuant to Section X" style cross-refs,
        # so cross_references may be empty. key_dates require date-context
        # sentences ending with a period.
        assert len(result.risk_surface) > 0

    async def test_risk_surface_includes_broad_definition(
        self, sample_contract_text: str,
    ) -> None:
        intake = _make_intake()
        result = await analyze_structure(
            app=None,
            document_text=sample_contract_text,
            intake=intake,
        )

        signal_types = [s.signal_type for s in result.risk_surface]
        assert "broad_definition" in signal_types

    async def test_all_fields_populated_rich_fixture(self) -> None:
        """Use the full fixture file which has cross-refs and date contexts."""
        fixture_path = (
            "/Users/santoshkumarradha/Documents/agentfield/code/examples/"
            "contract-af/tests/fixtures/sample_saas_agreement.txt"
        )
        with open(fixture_path) as f:
            text = f.read()

        intake = _make_intake()
        result = await analyze_structure(app=None, document_text=text, intake=intake)

        assert len(result.sections) > 0
        assert len(result.defined_terms) > 0
        assert len(result.cross_references) > 0
        assert len(result.exhibits) > 0
        assert len(result.risk_surface) > 0

    async def test_integration_with_fixture_file(self) -> None:
        fixture_path = (
            "/Users/santoshkumarradha/Documents/agentfield/code/examples/"
            "contract-af/tests/fixtures/sample_saas_agreement.txt"
        )
        with open(fixture_path) as f:
            text = f.read()

        intake = _make_intake()
        result = await analyze_structure(app=None, document_text=text, intake=intake)

        assert isinstance(result, AnatomyResult)
        assert len(result.sections) > 10
        assert len(result.defined_terms) > 5
        # Fixture has "Exhibit A" at the bottom
        assert len(result.exhibits) >= 1


# ---------------------------------------------------------------------------
# 9. Empty / minimal document
# ---------------------------------------------------------------------------


class TestEmptyDocument:
    """Gracefully handles empty or minimal input."""

    async def test_empty_string_no_app(self) -> None:
        intake = _make_intake()
        result = await analyze_structure(
            app=None,
            document_text="",
            intake=intake,
        )

        assert isinstance(result, AnatomyResult)
        assert result.sections == []
        assert result.defined_terms == []
        assert result.cross_references == []

    async def test_minimal_text_no_sections(self) -> None:
        intake = _make_intake()
        result = await analyze_structure(
            app=None,
            document_text="This is just a paragraph with no structure.",
            intake=intake,
        )

        assert isinstance(result, AnatomyResult)
        assert result.sections == []

    async def test_empty_with_app_triggers_fallback(self, mock_app) -> None:
        """When sections are empty and app is provided, harness fallback fires."""
        intake = _make_intake()

        mock_app.call.return_value = AnatomyResult(
            sections=[],
            defined_terms=[],
            cross_references=[],
        )

        result = await analyze_structure(
            app=mock_app,
            document_text="",
            intake=intake,
        )

        mock_app.call.assert_called_once()
        assert isinstance(result, AnatomyResult)

    def test_extract_sections_whitespace_only(self) -> None:
        sections = _extract_sections("   \n\n\t  \n  ")
        assert sections == []

    def test_extract_defined_terms_empty(self) -> None:
        terms = _extract_defined_terms("", [])
        assert terms == []

    def test_extract_cross_references_empty(self) -> None:
        refs = _extract_cross_references("", [])
        assert refs == []

    def test_extract_exhibits_empty(self) -> None:
        exhibits = _extract_exhibits("")
        assert exhibits == []

    def test_extract_key_dates_empty(self) -> None:
        dates = _extract_key_dates("", [])
        assert dates == []
