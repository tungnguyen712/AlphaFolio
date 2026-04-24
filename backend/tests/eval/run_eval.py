"""Eval harness — not part of the pytest suite (costs ~$1.20/run).

Invokes the compiled research graph directly against live SEC + Tavily +
Anthropic. For each ticker:

  1. Run graph, collect final state.
  2. Run every invariant; any failure is a hard FAIL for the ticker.
  3. Compare against golden snapshot (if present); differences become
     drift notes — warnings, not failures.
  4. Write a timestamped JSON report to tests/eval/reports/.

CLI:

    # Full eval across the default ticker set.
    docker compose exec backend uv run python tests/eval/run_eval.py

    # Single ticker.
    docker compose exec backend uv run python tests/eval/run_eval.py NVDA

    # Refresh golden snapshots (use after a deliberate prompt/model change).
    docker compose exec backend uv run python tests/eval/run_eval.py --update-golden
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.graphs.research import build_research_graph, new_research_state
from tests.eval.drift import (
    compare_to_golden,
    load_golden,
    save_golden,
    snapshot_of,
)
from tests.eval.invariants import run_invariants

_REPORTS_DIR = Path(__file__).parent / "reports"
_DEFAULT_TICKERS = ["NVDA", "AAPL", "AMD"]


async def _eval_ticker(ticker: str, *, update_golden: bool) -> dict:
    graph = build_research_graph()
    state = await graph.ainvoke(new_research_state(ticker=ticker, lookback_days=90))

    invariant_results = run_invariants(state)
    failures = [(name, reason) for name, reason in invariant_results if reason]
    passes = [name for name, reason in invariant_results if reason is None]

    snapshot = snapshot_of(state)
    golden = load_golden(ticker)
    drift_notes: list[str] = []
    if golden is None:
        drift_notes.append("no golden snapshot on file — recording this run as baseline")
        save_golden(ticker, snapshot)
    else:
        drift_notes = compare_to_golden(snapshot, golden)
        if update_golden:
            save_golden(ticker, snapshot)
            drift_notes.append("golden snapshot updated (--update-golden)")

    return {
        "ticker": ticker,
        "status": "fail" if failures else "pass",
        "invariants": {
            "passed": passes,
            "failed": [{"name": n, "reason": r} for n, r in failures],
        },
        "drift_notes": drift_notes,
        "snapshot": snapshot,
    }


def _print_ticker_report(result: dict) -> None:
    status = result["status"].upper()
    banner = f"{result['ticker']}  [{status}]"
    print("\n" + "=" * 72)
    print(banner)
    print("=" * 72)

    snap = result["snapshot"]
    print(f"  verdict:    {snap['verdict']}")
    print(f"  signal:     {snap['signal']} (confidence {snap['confidence']:.2f})")

    passed = result["invariants"]["passed"]
    failed = result["invariants"]["failed"]
    print(f"\n  invariants: {len(passed)} passed, {len(failed)} failed")
    for f in failed:
        print(f"    FAIL  {f['name']}: {f['reason']}")

    if result["drift_notes"]:
        print("\n  drift notes:")
        for note in result["drift_notes"]:
            print(f"    - {note}")


async def main(tickers: list[str], *, update_golden: bool) -> int:
    results = []
    for ticker in tickers:
        try:
            result = await _eval_ticker(ticker, update_golden=update_golden)
        except Exception as exc:  # noqa: BLE001 — a crash is a ticker-level fail, not a harness abort
            result = {
                "ticker": ticker,
                "status": "error",
                "error": repr(exc),
                "invariants": {"passed": [], "failed": []},
                "drift_notes": [],
                "snapshot": None,
            }
        results.append(result)
        _print_ticker_report(result)

    # Write timestamped report.
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    report_path = _REPORTS_DIR / f"eval_{stamp}.json"
    report_path.write_text(
        json.dumps(
            {
                "run_at": datetime.now(UTC).isoformat(),
                "tickers": tickers,
                "results": results,
            },
            indent=2,
            default=str,
        )
    )
    print(f"\nReport written to {report_path}")

    # Summary + exit code.
    total_fail = sum(1 for r in results if r["status"] != "pass")
    total_drift = sum(1 for r in results if r["drift_notes"])
    print(
        f"\nSummary: {len(results) - total_fail}/{len(results)} passed; "
        f"{total_drift} ticker(s) have drift notes."
    )
    return 0 if total_fail == 0 else 1


def _parse_args(argv: list[str]) -> tuple[list[str], bool]:
    update_golden = False
    positional: list[str] = []
    for arg in argv[1:]:
        if arg == "--update-golden":
            update_golden = True
        elif arg.startswith("-"):
            raise SystemExit(f"Unknown flag: {arg}")
        else:
            positional.append(arg.upper())
    tickers = positional or _DEFAULT_TICKERS
    return tickers, update_golden


if __name__ == "__main__":
    tickers, update_golden = _parse_args(sys.argv)
    print(f"Running eval for: {', '.join(tickers)}")
    if update_golden:
        print("(--update-golden: snapshots will be overwritten)")
    exit_code = asyncio.run(main(tickers, update_golden=update_golden))
    sys.exit(exit_code)
