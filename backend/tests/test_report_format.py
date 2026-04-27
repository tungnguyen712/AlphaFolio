"""Regression tests for report section parsing and rationale formatting.

Guards against rendering regressions like orphaned numeric fragments
("**1. ** HOLD. 81...") that appear when the LLM uses numbered markdown
bold headers instead of the prescribed ## heading format.

Tests are pure Python — no LLM, no network, no database.
"""
from __future__ import annotations

import re

import pytest

from app.models.agents.synthesis import SECTION_HEADINGS
from app.services.agents.synthesis import _parse_rationale_sections

# ---------------------------------------------------------------------------
# Sample rationale in the prescribed ## Heading format
# ---------------------------------------------------------------------------

WELL_FORMED_RATIONALE = """\
## Recommendation
HOLD — do not initiate at current prices; revisit on a pullback below $310.

## Investment Thesis
AMD is the #2 AI accelerator vendor with credible hyperscaler wins, but the \
stock has rallied 74% from its February low and is priced for perfection. \
The Meta $100B commitment validates the thesis but the contractual depth is \
unconfirmed.

## Top Signals
The Meta partnership announcement drove an 8.8% single-day rally and validates \
AMD's AI accelerator narrative (TipRanks, 2026-02-25). Q4'25 revenue of $10.3B \
(+34% YoY) beat consensus; the $5.4B data-center quarter is a record (CNBC, \
2026-02-03). Broad 10b5-1 insider selling across 6 unique executives totaling \
$63.9M with zero buys signals management monetizing into the rally (Form 4).

## Valuation Bridge
Current price: $347.81. Bull case: $434.76 (+25%). Base case: $375.63 (+8%). \
Bear case: $285.20 (–18%). Forward P/E, EV/revenue, and market cap are \
unavailable from structured data; analyst price targets range $265–$358 per \
news snippets (secondary source only).

## Key Uncertainties
Whether the Meta $100B commitment converts to firm near-term purchase \
obligations or remains a multi-year framework Meta can reduce as its MTIA \
in-house silicon ramps.

## Devil's Advocate
Consensus price targets sit below spot, the C-suite is selling broadly with \
zero offsetting buys, Q1 guide implies sequential deceleration, and momentum \
is crowded after a 74% run. Confirmation: any capex revision from Meta, MI400 \
timing slip, or BIS export restriction on a successor SKU.

## Data Quality
Validation warnings: market_cap, forward_pe, ev_revenue, 52w high/low \
unavailable. analyst_signal_source = news_reported_analyst_signal — price \
targets are secondary context only. Insider aggregation: 6 unique sellers, \
9 distinct filings, 36 raw transaction rows (row count > 3x filings flagged). \
Macro context fully null. Three low-quality sources (TheStreet, Seeking Alpha, \
Motley Fool) filtered upstream. Confidence penalty: 35%.

## Final Rationale
AMD's AI acceleration thesis is intact but the risk/reward at $347.81 is \
unattractive when every cited analyst PT except one sits below spot. We hold \
existing exposure and revisit an entry near the $285–$310 base/bear zone. \
Confidence: 45%.
"""

# ---------------------------------------------------------------------------
# Rationale in the old broken format (regression guard)
# ---------------------------------------------------------------------------

MALFORMED_RATIONALE_NUMBERED_BOLD = """\
**1. Recommendation** — HOLD. $347.81 is trading above analyst targets.

**2. Investment Thesis** — AMD is the #2 AI vendor.

**3. Top Signals** — Meta deal, record DC quarter, insider selling.
"""


# ---------------------------------------------------------------------------
# _parse_rationale_sections tests
# ---------------------------------------------------------------------------


class TestParseRationaleSections:
    def test_well_formed_sections_parsed(self):
        sections = _parse_rationale_sections(WELL_FORMED_RATIONALE)
        assert set(SECTION_HEADINGS).issubset(set(sections.keys()))

    def test_section_bodies_non_empty(self):
        sections = _parse_rationale_sections(WELL_FORMED_RATIONALE)
        for heading in SECTION_HEADINGS:
            assert sections[heading].strip(), f"Section '{heading}' body is empty"

    def test_recommendation_body_starts_with_signal_word(self):
        sections = _parse_rationale_sections(WELL_FORMED_RATIONALE)
        body = sections["Recommendation"].upper()
        assert any(word in body for word in ("HOLD", "BUY", "SELL"))

    def test_no_orphaned_numbered_bold_fragments(self):
        sections = _parse_rationale_sections(WELL_FORMED_RATIONALE)
        for heading, body in sections.items():
            # Detect patterns like "**1." or "**2." at the start of any line
            assert not re.search(r"\*\*\d+\.", body), (
                f"Section '{heading}' contains numbered bold fragment: {body[:80]}"
            )

    def test_section_bodies_do_not_contain_raw_heading_markers(self):
        sections = _parse_rationale_sections(WELL_FORMED_RATIONALE)
        for heading, body in sections.items():
            # Body should not start with ## (heading was consumed by the parser)
            assert not body.startswith("##"), (
                f"Section '{heading}' body still contains ## prefix"
            )

    def test_empty_string_returns_empty_dict(self):
        assert _parse_rationale_sections("") == {}

    def test_no_sections_returns_empty_dict(self):
        assert _parse_rationale_sections("Just plain prose with no headings.") == {}

    def test_partial_sections_parsed(self):
        partial = "## Recommendation\nHOLD.\n\n## Investment Thesis\nStrong AI position."
        sections = _parse_rationale_sections(partial)
        assert "Recommendation" in sections
        assert "Investment Thesis" in sections
        assert sections["Recommendation"].strip() == "HOLD."


# ---------------------------------------------------------------------------
# AMD regression test — guards the specific failure mode from production
# ---------------------------------------------------------------------------

# Simulated AMD rationale that looks like broken LLM output
AMD_BROKEN_RATIONALE = MALFORMED_RATIONALE_NUMBERED_BOLD

# Well-formed AMD rationale in prescribed format
AMD_WELL_FORMED_RATIONALE = WELL_FORMED_RATIONALE


class TestAmdRegressionReport:
    def test_broken_format_produces_no_sections(self):
        """Old-style numbered-bold rationale should return no ## sections
        (the parser won't find ## headings, returning an empty dict — the
        frontend then falls back to RationaleText)."""
        sections = _parse_rationale_sections(AMD_BROKEN_RATIONALE)
        # No ## headers in the broken format → empty dict
        assert sections == {}

    def test_well_formed_format_produces_all_sections(self):
        sections = _parse_rationale_sections(AMD_WELL_FORMED_RATIONALE)
        assert len(sections) == len(SECTION_HEADINGS)

    def test_valuation_mentions_price_without_fragment(self):
        """$347.81 should appear intact in the Valuation Bridge section,
        not split into '$347.' and '81...'."""
        sections = _parse_rationale_sections(AMD_WELL_FORMED_RATIONALE)
        valuation = sections.get("Valuation Bridge", "")
        assert "347.81" in valuation, "Price $347.81 should appear intact in Valuation Bridge"

    def test_no_section_body_starts_with_orphaned_number(self):
        """Regression: no body should start with a bare number like '81 is trading'."""
        sections = _parse_rationale_sections(AMD_WELL_FORMED_RATIONALE)
        orphan_re = re.compile(r"^\d+\s+\w")
        for heading, body in sections.items():
            assert not orphan_re.match(body), (
                f"Section '{heading}' body starts with orphaned number: {body[:60]}"
            )

    def test_recommendation_section_does_not_contain_raw_asterisks(self):
        sections = _parse_rationale_sections(AMD_WELL_FORMED_RATIONALE)
        rec = sections.get("Recommendation", "")
        # The heading itself should not be inside the body
        assert "**" not in rec or re.search(r"\*\*[^*]+\*\*", rec), (
            "Raw unmatched ** asterisks in Recommendation body"
        )

    def test_data_quality_section_present_and_mentions_confidence(self):
        sections = _parse_rationale_sections(AMD_WELL_FORMED_RATIONALE)
        dq = sections.get("Data Quality", "")
        assert "confidence" in dq.lower() or "penalty" in dq.lower(), (
            "Data Quality section should mention confidence or penalty"
        )

    def test_section_headings_constant_matches_expected_names(self):
        """Guard: if someone renames a section, the constant must be updated too."""
        assert "Recommendation" in SECTION_HEADINGS
        assert "Investment Thesis" in SECTION_HEADINGS
        assert "Top Signals" in SECTION_HEADINGS
        assert "Valuation Bridge" in SECTION_HEADINGS
        assert "Key Uncertainties" in SECTION_HEADINGS
        assert "Devil's Advocate" in SECTION_HEADINGS
        assert "Data Quality" in SECTION_HEADINGS
        assert "Final Rationale" in SECTION_HEADINGS
        assert len(SECTION_HEADINGS) == 8
