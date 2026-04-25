"""Unit tests for the S-1 branch of sec_edgar.

HTTP is mocked — no network calls. Tests cover the FTS-hit parser, the
display-name filter (drops hits from unrelated filers), and section
extraction for a fabricated S-1 HTML sample.
"""
from __future__ import annotations

from app.services.data_providers import sec_edgar
from app.services.data_providers.sec_edgar import (
    _extract_s1_prospectus_summary,
    _extract_s1_risk_factors,
    _parse_fts_s1_hit,
)


def _fts_hit(
    *,
    adsh: str = "0001628280-24-008872",
    form: str = "S-1",
    cik: str = "1713445",
    display_names: list[str] | None = None,
    file_date: str = "2024-02-22",
) -> dict:
    return {
        "_id": adsh,
        "_source": {
            "adsh": adsh,
            "form": form,
            "ciks": [cik],
            "display_names": display_names or ["Reddit, Inc. (RDDT) (CIK 0001713445)"],
            "file_date": file_date,
        },
    }


# ---------------------------------------------------------------------------
# FTS hit parsing
# ---------------------------------------------------------------------------


def test_parse_fts_s1_hit_happy_path() -> None:
    parsed = _parse_fts_s1_hit(_fts_hit(), query_lower="reddit")
    assert parsed is not None
    assert parsed["cik"] == "0001713445"
    assert parsed["company_title"].startswith("Reddit")
    assert parsed["filing"]["form"] == "S-1"
    assert parsed["filing"]["accession"] == "0001628280-24-008872"
    assert parsed["filing"]["accession_nodash"] == "000162828024008872"
    assert parsed["filing"]["filed_at"] == "2024-02-22"


def test_parse_fts_s1_hit_accepts_amendment() -> None:
    parsed = _parse_fts_s1_hit(_fts_hit(form="S-1/A"), query_lower="reddit")
    assert parsed is not None
    assert parsed["filing"]["form"] == "S-1/A"


def test_parse_fts_s1_hit_rejects_unmatched_display_name() -> None:
    """FTS can return filings from unrelated companies that merely mention the
    query string in their text. Those should be filtered out."""
    hit = _fts_hit(
        display_names=["SOMEONE ELSE INC. (XYZ) (CIK 0000012345)"]
    )
    assert _parse_fts_s1_hit(hit, query_lower="reddit") is None


def test_parse_fts_s1_hit_rejects_missing_ciks() -> None:
    bad = _fts_hit()
    bad["_source"]["ciks"] = []
    assert _parse_fts_s1_hit(bad, query_lower="reddit") is None


# ---------------------------------------------------------------------------
# Section extractors
# ---------------------------------------------------------------------------


def _sample_s1_html() -> str:
    """Synthetic S-1 HTML with the right section landmarks and enough body
    text that the ToC-vs-body heuristic (>2k char gap) picks the real section."""
    body = " risk paragraph lorem ipsum dolor sit amet consectetur adipiscing." * 50
    return f"""
    <html><body>
      <h1>Table of Contents</h1>
      <p>Summary ... Risk Factors ... Use of Proceeds ...</p>
      <h2>PROSPECTUS SUMMARY</h2>
      <p>We are a community-based platform. {"overview text. " * 200}</p>
      <h2>THE OFFERING</h2>
      <p>Shares offered: ...</p>
      <h2>RISK FACTORS</h2>
      <p>{body}</p>
      <h2>USE OF PROCEEDS</h2>
      <p>We intend to use the net proceeds ...</p>
    </body></html>
    """


def test_extract_s1_risk_factors_finds_body_section() -> None:
    text = _extract_s1_risk_factors(_sample_s1_html())
    assert "risk paragraph lorem ipsum" in text
    assert "Use of Proceeds" not in text  # stopped at the end marker
    assert len(text) <= 4000


def test_extract_s1_prospectus_summary_finds_body_section() -> None:
    text = _extract_s1_prospectus_summary(_sample_s1_html())
    assert "community-based platform" in text
    assert "RISK FACTORS" not in text
    assert len(text) <= 2500


def test_extract_s1_risk_factors_returns_empty_when_missing() -> None:
    assert _extract_s1_risk_factors("<html><body>no risk factors here</body></html>") == ""


# ---------------------------------------------------------------------------
# resolve_company_by_name — integration-ish (patch httpx)
# ---------------------------------------------------------------------------


async def test_resolve_company_raises_lookup_error_on_no_hits(monkeypatch) -> None:
    """EDGAR FTS returns an empty hits list when a name doesn't match."""
    import pytest

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"hits": {"hits": []}}

    class _Client:
        def __init__(self, *a, **kw):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):  # noqa: ARG002
            return None

        async def get(self, *a, **kw):  # noqa: ARG002
            return _Resp()

    monkeypatch.setattr(sec_edgar.httpx, "AsyncClient", _Client)

    # Unique name so the cache doesn't short-circuit the FTS call.
    import uuid

    unique_name = f"ZZZNOTACOMPANY_{uuid.uuid4().hex[:8].upper()}"
    with pytest.raises(LookupError, match="No S-1 filings"):
        await sec_edgar.resolve_company_by_name(unique_name)


async def test_resolve_ticker_from_name_exact_ticker_match(monkeypatch) -> None:
    _patch_company_tickers(monkeypatch, _company_tickers_fixture())
    import uuid

    # NVDA is in the fixture. We also cache-bust by asking with a padded
    # version; the exact-ticker branch lower()s everything so "NvDA" works.
    _ = uuid.uuid4()  # noqa: F841 — just to keep this test name unique each run if needed
    result = await sec_edgar.resolve_ticker_from_name("NVDA")
    assert result["ticker"] == "NVDA"
    assert result["title"].startswith("NVIDIA")


async def test_resolve_ticker_from_name_friendly_name(monkeypatch) -> None:
    _patch_company_tickers(monkeypatch, _company_tickers_fixture())
    result = await sec_edgar.resolve_ticker_from_name("Nvidia")
    assert result["ticker"] == "NVDA"


async def test_resolve_ticker_from_name_ambiguous_raises(monkeypatch) -> None:
    """'Apple' matches multiple titles — resolver should surface the options
    rather than silently pick one."""
    import pytest

    _patch_company_tickers(
        monkeypatch,
        {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "APPLE INC"},
            "1": {
                "cik_str": 1418121,
                "ticker": "APLE",
                "title": "APPLE HOSPITALITY REIT, INC.",
            },
        },
    )
    with pytest.raises(LookupError, match="multiple tickers"):
        await sec_edgar.resolve_ticker_from_name("Appl")


async def test_resolve_ticker_from_name_raises_on_no_match(monkeypatch) -> None:
    import pytest

    _patch_company_tickers(monkeypatch, _company_tickers_fixture())
    with pytest.raises(LookupError, match="No SEC-registered ticker"):
        await sec_edgar.resolve_ticker_from_name("NotARealCompanyZZZZZ")


def _company_tickers_fixture() -> dict:
    return {
        "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
        "2": {"cik_str": 2488, "ticker": "AMD", "title": "ADVANCED MICRO DEVICES INC"},
    }


def _patch_company_tickers(monkeypatch, payload: dict) -> None:
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *a, **kw):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):  # noqa: ARG002
            return None

        async def get(self, *a, **kw):  # noqa: ARG002
            return _Resp()

    monkeypatch.setattr(sec_edgar.httpx, "AsyncClient", _Client)

    # Bypass the DB-backed signal_cache so stale cached results from previous
    # runs don't short-circuit the function body and mask logic changes.
    from app.services.data_providers import _cache

    async def _no_cache_get(key: str):  # noqa: ARG001
        return None

    async def _no_cache_set(key: str, payload: dict, ttl: int) -> None:  # noqa: ARG001
        return None

    monkeypatch.setattr(_cache, "cache_get", _no_cache_get)
    monkeypatch.setattr(_cache, "cache_set", _no_cache_set)


async def test_resolve_company_picks_most_recent_by_filed_date(monkeypatch) -> None:
    """Given multiple S-1 hits for the same CIK, resolve_company_by_name
    returns them sorted newest-first."""
    import uuid

    # Unique name in both the query and the synthetic display_names so the
    # substring filter lets the hits through AND the cache doesn't short-
    # circuit to a previous run.
    unique_name = f"Reddit_{uuid.uuid4().hex[:8]}"
    matching_display_names = [f"{unique_name}, Inc. (RDDT) (CIK 0001713445)"]

    payload = {
        "hits": {
            "hits": [
                _fts_hit(
                    adsh="A-1",
                    file_date="2024-01-05",
                    display_names=matching_display_names,
                ),
                _fts_hit(
                    adsh="B-2",
                    file_date="2024-03-07",
                    form="S-1/A",
                    display_names=matching_display_names,
                ),
                _fts_hit(
                    adsh="C-3",
                    file_date="2024-02-22",
                    display_names=matching_display_names,
                ),
            ]
        }
    }

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *a, **kw):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):  # noqa: ARG002
            return None

        async def get(self, *a, **kw):  # noqa: ARG002
            return _Resp()

    monkeypatch.setattr(sec_edgar.httpx, "AsyncClient", _Client)

    result = await sec_edgar.resolve_company_by_name(unique_name)
    assert result["cik"] == "0001713445"
    assert [f["accession"] for f in result["filings"]] == ["B-2", "C-3", "A-1"]
