"""Tests for the review layer: cross-ref resolver, adversary reviewer, gap analyst."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from contract_af.agents.cross_ref import (
    MAX_DEEP_DIVES,
    SENTINEL as CROSS_REF_SENTINEL,
    resolve_cross_references,
)
from contract_af.agents.adversary import (
    SENTINEL as ADVERSARY_SENTINEL,
    review_as_adversary,
)
from contract_af.agents.gap_analyst import analyze_gaps
from contract_af.models import (
    AnatomyResult,
    CrossRef,
    Finding,
    IntakeResult,
    Party,
    Section,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    *,
    id: str = "f-1",
    clause_ref: str = "5.1",
    clause_text: str = "Sample clause text.",
    category: str = "ip",
    severity: Severity = Severity.HIGH,
    description: str = "A risky clause.",
    reasoning: str = "Because reasons.",
    remediation: str = "Fix it.",
) -> Finding:
    return Finding(
        id=id,
        clause_ref=clause_ref,
        clause_text=clause_text,
        category=category,
        severity=severity,
        description=description,
        reasoning=reasoning,
        remediation=remediation,
    )


def _make_anatomy(
    *,
    sections: list[Section] | None = None,
    cross_references: list[CrossRef] | None = None,
) -> AnatomyResult:
    return AnatomyResult(
        sections=sections or [Section(number="1", title="Definitions")],
        defined_terms=[],
        cross_references=cross_references or [],
    )


def _make_intake(
    *,
    contract_type: str = "saas_agreement",
    your_role: str = "Customer",
    parties: list[Party] | None = None,
) -> IntakeResult:
    return IntakeResult(
        contract_type=contract_type,
        parties=parties
        or [
            Party(name="Acme", role="Provider", entity_type="corporation"),
            Party(name="TechStart", role="Customer", entity_type="llc"),
        ],
        your_role=your_role,
        jurisdiction="Delaware, USA",
        governing_law="Delaware",
        deal_structure="SaaS subscription",
        complexity="standard",
        confident=True,
    )


async def _enqueue_and_sentinel(
    queue: asyncio.Queue,
    items: list,
    sentinel: object,
) -> None:
    """Put items into queue followed by sentinel."""
    for item in items:
        await queue.put(item)
    await queue.put(sentinel)


# ===========================================================================
# Cross-Reference Resolver
# ===========================================================================


class TestCrossRefResolver:
    """Tests for resolve_cross_references."""

    @pytest.mark.asyncio
    async def test_detects_interaction(self, mock_app: MagicMock) -> None:
        """Two findings with related clauses produce a CombinationRisk."""
        finding_a = _make_finding(id="f-1", clause_ref="5.1", category="ip")
        finding_b = _make_finding(id="f-2", clause_ref="9.1", category="indemnity")

        anatomy = _make_anatomy(
            cross_references=[
                CrossRef(
                    from_section="5.1",
                    to_section="9.1",
                    relationship_type="subject_to",
                ),
            ],
        )

        mock_app.call.return_value = {
            "has_interaction": True,
            "severity": "high",
            "description": "IP assignment + indemnity creates one-sided risk.",
            "investigation": "The indemnity amplifies IP risk.",
        }

        queue: asyncio.Queue = asyncio.Queue()
        await _enqueue_and_sentinel(queue, [finding_a, finding_b], CROSS_REF_SENTINEL)

        risks = await resolve_cross_references(
            mock_app, queue, anatomy, "contract text"
        )

        assert len(risks) == 1
        assert risks[0].clause_refs == ["5.1", "9.1"]
        assert risks[0].severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_no_interaction(self, mock_app: MagicMock) -> None:
        """Unrelated findings produce no combination risks."""
        finding_a = _make_finding(id="f-1", clause_ref="1.1", category="definitions")
        finding_b = _make_finding(id="f-2", clause_ref="15.1", category="misc")

        anatomy = _make_anatomy()

        mock_app.call.return_value = {"has_interaction": False}

        queue: asyncio.Queue = asyncio.Queue()
        await _enqueue_and_sentinel(queue, [finding_a, finding_b], CROSS_REF_SENTINEL)

        risks = await resolve_cross_references(
            mock_app, queue, anatomy, "contract text"
        )

        assert len(risks) == 0

    @pytest.mark.asyncio
    async def test_deep_dive_on_critical(self, mock_app: MagicMock) -> None:
        """Critical interaction spawns combination_deep_dive (up to MAX_DEEP_DIVES)."""
        finding_a = _make_finding(id="f-1", clause_ref="5.1")
        finding_b = _make_finding(id="f-2", clause_ref="9.1")

        anatomy = _make_anatomy()

        mock_app.call.side_effect = [
            # First call: cross_ref_resolver returns critical interaction
            {
                "has_interaction": True,
                "severity": "critical",
                "description": "Critical combination found.",
                "deep_dive_prompt": "Investigate IP + indemnity interaction.",
            },
            # Second call: combination_deep_dive returns additional findings
            {
                "findings": [
                    {
                        "clause_refs": ["5.1", "9.1"],
                        "description": "Deep dive found hidden risk.",
                        "severity": "high",
                        "investigation": "Deep dive investigation result.",
                    }
                ]
            },
        ]

        queue: asyncio.Queue = asyncio.Queue()
        await _enqueue_and_sentinel(queue, [finding_a, finding_b], CROSS_REF_SENTINEL)

        risks = await resolve_cross_references(
            mock_app, queue, anatomy, "contract text"
        )

        # 1 from initial interaction + 1 from deep dive
        assert len(risks) == 2
        assert risks[0].severity == Severity.CRITICAL
        assert risks[1].description == "Deep dive found hidden risk."

        # Verify deep dive was called with correct agent name
        calls = mock_app.call.call_args_list
        assert calls[1][0][0] == "contract-af.combination_deep_dive"

    @pytest.mark.asyncio
    async def test_deep_dive_budget_cap(self, mock_app: MagicMock) -> None:
        """Deep dives are capped at MAX_DEEP_DIVES even with more critical findings."""
        anatomy = _make_anatomy()

        # Create MAX_DEEP_DIVES + 2 findings so we get MAX_DEEP_DIVES + 1
        # critical interactions but only MAX_DEEP_DIVES deep dives
        findings = [
            _make_finding(id=f"f-{i}", clause_ref=f"{i}.1")
            for i in range(MAX_DEEP_DIVES + 2)
        ]

        call_count = 0

        async def _mock_call(agent_name: str, **kwargs):
            nonlocal call_count
            call_count += 1
            if "cross_ref_resolver" in agent_name:
                return {
                    "has_interaction": True,
                    "severity": "critical",
                    "description": f"Critical combo {call_count}",
                    "deep_dive_prompt": "Investigate.",
                }
            if "combination_deep_dive" in agent_name:
                return {"findings": []}
            return {}

        mock_app.call.side_effect = _mock_call

        queue: asyncio.Queue = asyncio.Queue()
        await _enqueue_and_sentinel(queue, findings, CROSS_REF_SENTINEL)

        await resolve_cross_references(mock_app, queue, anatomy, "text")

        deep_dive_calls = [
            c
            for c in mock_app.call.call_args_list
            if c[0][0] == "contract-af.combination_deep_dive"
        ]
        assert len(deep_dive_calls) == MAX_DEEP_DIVES

    @pytest.mark.asyncio
    async def test_queue_consumption_until_sentinel(
        self, mock_app: MagicMock
    ) -> None:
        """Resolver reads all findings from queue until SENTINEL."""
        findings = [_make_finding(id=f"f-{i}", clause_ref=f"{i}.1") for i in range(5)]

        mock_app.call.return_value = {"has_interaction": False}

        queue: asyncio.Queue = asyncio.Queue()
        await _enqueue_and_sentinel(queue, findings, CROSS_REF_SENTINEL)

        await resolve_cross_references(mock_app, queue, _make_anatomy(), "text")

        # Queue should be empty (all items consumed)
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_timeout_on_empty_queue(self, mock_app: MagicMock) -> None:
        """Empty queue times out gracefully after wait_for timeout."""
        queue: asyncio.Queue = asyncio.Queue()
        # Do NOT put sentinel — rely on timeout

        # Patch wait_for timeout to be short for test speed
        original_wait_for = asyncio.wait_for

        async def _fast_timeout(coro, timeout):
            return await original_wait_for(coro, timeout=0.05)

        import contract_af.agents.cross_ref as cross_ref_mod

        original_fn = cross_ref_mod.asyncio.wait_for
        cross_ref_mod.asyncio.wait_for = _fast_timeout
        try:
            risks = await resolve_cross_references(
                mock_app, queue, _make_anatomy(), "text"
            )
            assert risks == []
        finally:
            cross_ref_mod.asyncio.wait_for = original_fn


# ===========================================================================
# Adversary Reviewer
# ===========================================================================


class TestAdversaryReviewer:
    """Tests for review_as_adversary."""

    @pytest.mark.asyncio
    async def test_false_positive_detection(self, mock_app: MagicMock) -> None:
        """Standard clause flagged as risk -> adversary marks as false positive."""
        finding = _make_finding(
            id="f-fp",
            clause_ref="7.1",
            description="Warranty disclaimer is aggressive.",
            severity=Severity.HIGH,
        )

        mock_app.call.return_value = {
            "is_false_positive": True,
            "false_positive_reason": "Standard SaaS warranty disclaimer.",
            "evidence": "Industry-standard language per UCC 2B.",
        }

        intake = _make_intake()

        queue: asyncio.Queue = asyncio.Queue()
        await _enqueue_and_sentinel(queue, [finding], ADVERSARY_SENTINEL)

        result = await review_as_adversary(
            mock_app, queue, intake, "contract text"
        )

        assert len(result.false_positives) == 1
        assert result.false_positives[0].finding_id == "f-fp"
        assert "Standard SaaS" in result.false_positives[0].reason

    @pytest.mark.asyncio
    async def test_exploitation_scenario(self, mock_app: MagicMock) -> None:
        """Broad clause generates an exploitation scenario."""
        finding = _make_finding(
            id="f-exploit",
            clause_ref="11.1",
            description="Non-compete is extremely broad.",
            severity=Severity.CRITICAL,
        )

        mock_app.call.return_value = {
            "is_false_positive": False,
            "exploitation_scenario": (
                "Provider can block Customer from using ANY competing product "
                "for 2 years after termination."
            ),
            "impact": "Customer locked out of entire market segment.",
        }

        queue: asyncio.Queue = asyncio.Queue()
        await _enqueue_and_sentinel(queue, [finding], ADVERSARY_SENTINEL)

        result = await review_as_adversary(
            mock_app, queue, _make_intake(), "text"
        )

        assert len(result.exploitation_scenarios) == 1
        assert result.exploitation_scenarios[0].finding_id == "f-exploit"
        assert "competing product" in result.exploitation_scenarios[0].scenario

    @pytest.mark.asyncio
    async def test_hidden_trap_detection(self, mock_app: MagicMock) -> None:
        """Adversary finds a trap not caught by analysts."""
        finding = _make_finding(
            id="f-trap",
            clause_ref="12.1",
            description="Perpetual license on feedback.",
            severity=Severity.HIGH,
        )

        mock_app.call.return_value = {
            "is_false_positive": False,
            "hidden_traps": [
                {
                    "clause_refs": ["12.1", "5.1"],
                    "description": (
                        "Combined perpetual license + IP assignment means Customer "
                        "loses all rights to improvements permanently."
                    ),
                    "exploitation_scenario": (
                        "Provider uses Customer-developed features in competing "
                        "products sold to Customer's competitors."
                    ),
                    "severity": "critical",
                }
            ],
        }

        queue: asyncio.Queue = asyncio.Queue()
        await _enqueue_and_sentinel(queue, [finding], ADVERSARY_SENTINEL)

        result = await review_as_adversary(
            mock_app, queue, _make_intake(), "text"
        )

        assert len(result.hidden_traps) == 1
        assert result.hidden_traps[0].severity == Severity.CRITICAL
        assert "12.1" in result.hidden_traps[0].clause_refs

    @pytest.mark.asyncio
    async def test_survival_pattern_spawns_sub_agent(
        self, mock_app: MagicMock
    ) -> None:
        """Multiple findings referencing survival clause -> sub-agent spawned."""
        # Two findings whose clause_refs appear in survival cross-references
        finding_a = _make_finding(id="f-s1", clause_ref="5.1", category="ip")
        finding_b = _make_finding(id="f-s2", clause_ref="9.1", category="indemnity")

        anatomy = _make_anatomy(
            cross_references=[
                # Section 14 references sections 5 and 9 as surviving
                CrossRef(
                    from_section="14.1",
                    to_section="5.1",
                    relationship_type="survival",
                ),
                CrossRef(
                    from_section="14.1",
                    to_section="9.1",
                    relationship_type="survival",
                ),
            ],
        )

        call_count = 0

        async def _mock_call(agent_name: str, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # Per-finding review calls
                return {"is_false_positive": False}
            # Third call: survival sub-agent
            return {
                "hidden_traps": [
                    {
                        "clause_refs": ["5.1", "9.1"],
                        "description": "IP + indemnity survive termination.",
                        "exploitation_scenario": "Post-termination IP exposure.",
                        "severity": "critical",
                    }
                ]
            }

        mock_app.call.side_effect = _mock_call

        queue: asyncio.Queue = asyncio.Queue()
        await _enqueue_and_sentinel(
            queue, [finding_a, finding_b], ADVERSARY_SENTINEL
        )

        result = await review_as_adversary(
            mock_app, queue, _make_intake(), anatomy, "text"
        )

        # Sub-agent should have been called (3 total calls: 2 reviews + 1 survival)
        assert mock_app.call.call_count == 3
        assert len(result.hidden_traps) == 1
        assert result.hidden_traps[0].severity == Severity.CRITICAL

    @pytest.mark.asyncio
    async def test_queue_consumption_until_sentinel(
        self, mock_app: MagicMock
    ) -> None:
        """Adversary reads all findings from queue until SENTINEL."""
        findings = [_make_finding(id=f"f-{i}", clause_ref=f"{i}.1") for i in range(4)]

        mock_app.call.return_value = {"is_false_positive": False}

        queue: asyncio.Queue = asyncio.Queue()
        await _enqueue_and_sentinel(queue, findings, ADVERSARY_SENTINEL)

        await review_as_adversary(
            mock_app, queue, _make_intake(), _make_anatomy(), "text"
        )

        assert queue.empty()
        # One call per finding (no survival pattern without cross-refs)
        assert mock_app.call.call_count == len(findings)


# ===========================================================================
# Gap Analyst
# ===========================================================================


class TestGapAnalyst:
    """Tests for analyze_gaps."""

    @pytest.mark.asyncio
    async def test_missing_clause_detected(self, mock_app: MagicMock) -> None:
        """SaaS agreement missing dispute_resolution -> reported as missing."""
        anatomy = _make_anatomy(
            sections=[
                Section(number="1", title="Definitions"),
                Section(number="2", title="Grant of License"),
                Section(number="3", title="Fees and Payment"),
                Section(number="4", title="Customer Data"),
                Section(number="5", title="Intellectual Property"),
                Section(number="6", title="Confidentiality"),
                Section(number="7", title="Warranties"),
                Section(number="8", title="Limitation of Liability"),
                Section(number="9", title="Indemnification"),
                Section(number="10", title="Term and Termination"),
                Section(number="13", title="Governing Law"),
            ],
        )

        # All expected types are "found" except dispute_resolution
        found_types = [
            "definitions",
            "grant_of_license",
            "fees_payment",
            "data_protection",
            "intellectual_property",
            "confidentiality",
            "warranties",
            "limitation_of_liability",
            "indemnification",
            "term_termination",
            "governing_law",
        ]

        mock_app.ai.return_value = MagicMock(expected=["dispute_resolution"])
        # Harness confirms absence
        mock_app.call.return_value = {"found": False}

        result = await analyze_gaps(
            mock_app, _make_intake(), anatomy, found_types, "text"
        )

        assert "dispute_resolution" in result.missing_clauses
        assert "dispute_resolution" in result.verified_absent

    @pytest.mark.asyncio
    async def test_found_under_alias(self, mock_app: MagicMock) -> None:
        """IP clause labeled 'Proprietary Rights' -> found_elsewhere."""
        anatomy = _make_anatomy(
            sections=[
                Section(number="1", title="Definitions"),
                Section(number="5", title="Proprietary Rights"),
            ],
        )

        found_types = ["definitions"]
        mock_app.ai.return_value = MagicMock(expected=["intellectual_property"])
        mock_app.call.return_value = {
            "found": True,
            "found_in": "Proprietary Rights",
        }

        result = await analyze_gaps(
            mock_app, _make_intake(), anatomy, found_types, "text"
        )

        ip_found = [
            f for f in result.found_elsewhere if f["expected"] == "intellectual_property"
        ]
        assert len(ip_found) == 1
        assert ip_found[0]["actual_section"] == "Proprietary Rights"
        assert "intellectual_property" not in result.missing_clauses

    @pytest.mark.asyncio
    async def test_verified_absent_by_harness(self, mock_app: MagicMock) -> None:
        """Harness confirms clause is truly missing from the contract."""
        anatomy = _make_anatomy(
            sections=[Section(number="1", title="Definitions")],
        )

        # Only definitions found — everything else missing
        found_types = [
            "definitions",
            "grant_of_license",
            "fees_payment",
            "data_protection",
            "intellectual_property",
            "confidentiality",
            "warranties",
            "limitation_of_liability",
            "indemnification",
            "term_termination",
            "governing_law",
        ]

        mock_app.ai.return_value = MagicMock(expected=["dispute_resolution"])
        mock_app.call.return_value = {"found": False}

        result = await analyze_gaps(
            mock_app, _make_intake(), anatomy, found_types, "text"
        )

        assert "dispute_resolution" in result.verified_absent

    @pytest.mark.asyncio
    async def test_harness_finds_clause_elsewhere(
        self, mock_app: MagicMock
    ) -> None:
        """Harness finds the clause buried in an unexpected section."""
        anatomy = _make_anatomy(
            sections=[Section(number="1", title="Definitions")],
        )

        found_types = [
            "definitions",
            "grant_of_license",
            "fees_payment",
            "data_protection",
            "intellectual_property",
            "confidentiality",
            "warranties",
            "limitation_of_liability",
            "indemnification",
            "term_termination",
            "governing_law",
        ]

        mock_app.ai.return_value = MagicMock(expected=["dispute_resolution"])
        # Harness finds dispute_resolution embedded in Miscellaneous
        mock_app.call.return_value = {
            "found": True,
            "found_in": "Section 15.5 Miscellaneous",
        }

        result = await analyze_gaps(
            mock_app, _make_intake(), anatomy, found_types, "text"
        )

        assert "dispute_resolution" not in result.missing_clauses
        dr_found = [
            f for f in result.found_elsewhere if f["expected"] == "dispute_resolution"
        ]
        assert len(dr_found) == 1
        assert dr_found[0]["actual_section"] == "Section 15.5 Miscellaneous"

    @pytest.mark.asyncio
    async def test_unknown_contract_type_uses_ai_expectations(
        self, mock_app: MagicMock
    ) -> None:
        """Unknown contract types use AI expectations instead of a hardcoded SaaS fallback."""
        intake = _make_intake(contract_type="convertible_note")
        anatomy = _make_anatomy()
        found_types = ["conversion_terms", "governing_law"]
        mock_app.ai.return_value = MagicMock(
            expected=["conversion_terms", "governing_law"]
        )

        result = await analyze_gaps(mock_app, intake, anatomy, found_types, "text")

        assert result.missing_clauses == []
        mock_app.ai.assert_awaited_once()
        mock_app.call.assert_not_called()
