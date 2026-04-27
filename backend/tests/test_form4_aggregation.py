"""Unit tests for Form 4 aggregation and 10b5-1 classification.

Pure Python — no network, no LLM, no database.
"""
from __future__ import annotations

from datetime import date
from xml.etree import ElementTree as ET

import pytest

from app.models.agents.common import InsiderTransaction
from app.services.data_providers.sec_edgar import (
    _detect_planned_status,
    _parse_form4_xml,
    aggregate_insider_transactions,
)

_SOURCE_URL = "https://www.sec.gov/Archives/edgar/data/1326801/000100/form4.xml"


def _tx(
    filer: str = "Zuckerberg, Mark",
    role: str | None = "CEO",
    transaction: str = "sell",
    shares: float = 100_000.0,
    price: float = 500.0,
    filed_at: str = "2026-01-15",
    source_url: str = _SOURCE_URL,
    planned_status: str = "unknown",
) -> InsiderTransaction:
    return InsiderTransaction(
        filer=filer,
        role=role,
        transaction=transaction,
        shares=shares,
        price=price,
        value_usd=round(shares * price, 2),
        filed_at=date.fromisoformat(filed_at),
        form="Form 4",
        source_url=source_url,
        planned_status=planned_status,
    )


class TestAggregateInsiderTransactions:
    def test_unique_sellers_not_raw_rows(self):
        # Same filer, 3 transaction rows — should count as 1 unique seller
        txs = [
            _tx(filer="Smith, Jane", transaction="sell", shares=10_000),
            _tx(filer="Smith, Jane", transaction="sell", shares=5_000),
            _tx(filer="Smith, Jane", transaction="sell", shares=3_000),
        ]
        summary = aggregate_insider_transactions(txs)
        assert summary.unique_sellers == 1
        assert summary.raw_transaction_count == 3

    def test_two_unique_sellers_counted_correctly(self):
        txs = [
            _tx(filer="Smith, Jane", transaction="sell"),
            _tx(filer="Smith, Jane", transaction="sell"),
            _tx(filer="Jones, Bob", transaction="sell"),
        ]
        summary = aggregate_insider_transactions(txs)
        assert summary.unique_sellers == 2
        assert summary.raw_transaction_count == 3

    def test_csuite_seller_detection(self):
        txs = [_tx(role="CFO", transaction="sell")]
        summary = aggregate_insider_transactions(txs)
        assert summary.csuite_sellers == 1

    def test_ceo_is_csuite(self):
        txs = [_tx(role="CEO", transaction="sell")]
        summary = aggregate_insider_transactions(txs)
        assert summary.csuite_sellers == 1

    def test_board_seller_detection(self):
        txs = [_tx(role="Director", transaction="sell")]
        summary = aggregate_insider_transactions(txs)
        assert summary.board_sellers == 1
        assert summary.csuite_sellers == 0

    def test_board_not_counted_when_also_csuite(self):
        txs = [_tx(role="Chief Director of Operations", transaction="sell")]
        summary = aggregate_insider_transactions(txs)
        # "chief" triggers csuite, so board should not also be counted
        assert summary.csuite_sellers == 1
        assert summary.board_sellers == 0

    def test_buyer_counted_separately(self):
        txs = [
            _tx(filer="Smith, Jane", transaction="buy"),
            _tx(filer="Jones, Bob", transaction="sell"),
        ]
        summary = aggregate_insider_transactions(txs)
        assert summary.unique_buyers == 1
        assert summary.unique_sellers == 1

    def test_empty_list_all_zeros(self):
        summary = aggregate_insider_transactions([])
        assert summary.unique_sellers == 0
        assert summary.unique_buyers == 0
        assert summary.csuite_sellers == 0
        assert summary.board_sellers == 0
        assert summary.num_distinct_filings == 0
        assert summary.raw_transaction_count == 0
        assert summary.total_sales_value == 0.0
        assert summary.total_purchase_value == 0.0

    def test_total_values_match_sum(self):
        txs = [
            _tx(transaction="sell", shares=100, price=10.0),
            _tx(transaction="sell", shares=200, price=10.0),
            _tx(transaction="buy", shares=50, price=10.0),
        ]
        summary = aggregate_insider_transactions(txs)
        assert summary.total_sales_value == pytest.approx(3000.0)
        assert summary.total_purchase_value == pytest.approx(500.0)

    def test_distinct_filings_by_source_url(self):
        url_a = "https://sec.gov/data/1/00001/form4.xml"
        url_b = "https://sec.gov/data/1/00002/form4.xml"
        txs = [
            _tx(source_url=url_a),
            _tx(source_url=url_a),
            _tx(source_url=url_b),
        ]
        summary = aggregate_insider_transactions(txs)
        assert summary.num_distinct_filings == 2
        assert summary.raw_transaction_count == 3


class TestDetectPlannedStatus:
    def _make_tx_xml(
        self,
        code: str = "S",
        footnote_id: str | None = None,
        footnote_text: str | None = None,
    ) -> tuple[ET.Element, ET.Element]:
        """Build minimal Form 4 XML for testing _detect_planned_status."""
        root_xml = "<ownershipDocument>"
        if footnote_text and footnote_id:
            root_xml += f'<footnotes><footnote id="{footnote_id}">{footnote_text}</footnote></footnotes>'
        root_xml += "</ownershipDocument>"
        root = ET.fromstring(root_xml)

        tx_xml = f"""<nonDerivativeTransaction>
            <transactionCoding>
                <transactionCode>{code}</transactionCode>
            </transactionCoding>"""
        if footnote_id:
            tx_xml += f'<footnoteId id="{footnote_id}"/>'
        tx_xml += "</nonDerivativeTransaction>"
        tx = ET.fromstring(tx_xml)

        return tx, root

    def test_10b5_footnote_detected(self):
        tx, root = self._make_tx_xml(
            code="S",
            footnote_id="F1",
            footnote_text="Sale pursuant to Rule 10b5-1 trading plan adopted January 2025.",
        )
        assert _detect_planned_status(tx, root) == "planned_10b5_1"

    def test_rule_10b5_variant_detected(self):
        tx, root = self._make_tx_xml(
            code="S",
            footnote_id="F2",
            footnote_text="This transaction is part of a Rule 10b5 arrangement.",
        )
        assert _detect_planned_status(tx, root) == "planned_10b5_1"

    def test_open_market_sell_no_footnote_is_discretionary(self):
        tx, root = self._make_tx_xml(code="S")
        assert _detect_planned_status(tx, root) == "discretionary"

    def test_open_market_buy_no_footnote_is_discretionary(self):
        tx, root = self._make_tx_xml(code="P")
        assert _detect_planned_status(tx, root) == "discretionary"

    def test_option_exercise_code_m(self):
        tx, root = self._make_tx_xml(code="M")
        assert _detect_planned_status(tx, root) == "option_exercise"

    def test_compensation_code_f(self):
        tx, root = self._make_tx_xml(code="F")
        assert _detect_planned_status(tx, root) == "compensation"

    def test_unknown_code_returns_unknown(self):
        tx, root = self._make_tx_xml(code="Z")
        assert _detect_planned_status(tx, root) == "unknown"


class TestParseForm4XmlPlannedStatus:
    _MINIMAL_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerName>Zuckerberg, Mark</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <officerTitle>CEO</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <footnotes>
    <footnote id="F1">Sale pursuant to Rule 10b5-1 plan adopted March 2025.</footnote>
  </footnotes>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding>
        <transactionCode>S</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares>
          <value>50000</value>
        </transactionShares>
        <transactionPricePerShare>
          <value>520.00</value>
        </transactionPricePerShare>
      </transactionAmounts>
      <footnoteId id="F1"/>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""

    def test_planned_status_included_in_output(self):
        filing = {
            "filed_at": "2026-03-15",
            "accession_nodash": "0001326801026000010",
            "primary_doc": "form4.xml",
            "cik": "1326801",
        }
        results = _parse_form4_xml(self._MINIMAL_FORM4_XML, filing)
        assert len(results) == 1
        assert "planned_status" in results[0]
        assert results[0]["planned_status"] == "planned_10b5_1"

    def test_planned_status_default_discretionary_without_footnote(self):
        xml = """<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Smith, Jane</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><officerTitle>CFO</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>10000</value></transactionShares>
        <transactionPricePerShare><value>100.00</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""
        filing = {
            "filed_at": "2026-01-10",
            "accession_nodash": "0001234560260000010",
            "primary_doc": "form4.xml",
            "cik": "123456",
        }
        results = _parse_form4_xml(xml, filing)
        assert len(results) == 1
        assert results[0]["planned_status"] == "discretionary"
