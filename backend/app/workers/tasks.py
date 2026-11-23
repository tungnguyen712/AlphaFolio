"""Celery tasks that drive the agent graphs and maintenance jobs.

Agent tasks are sync wrappers around async helpers — Celery's default
execution model is sync per task, so we spin up a fresh event loop per task
with `asyncio.run`. `worker_prefetch_multiplier=1` means serial execution per
worker process, so loop creation overhead is negligible.

Retry policy for agent tasks: transient provider failures (network timeouts,
connection errors, HTTP 429/5xx) are retried up to 3 times with exponential
backoff (60s → 120s → 240s). Terminal failures (bad ticker, LLM schema errors,
Pydantic validation) propagate immediately without retry — the AgentRun row
already records the failure in Postgres and retrying won't help.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
import structlog
from sqlalchemy import select

from app.db.session import SessionLocal, engine as db_engine
from app.models.db import Notification, NotificationKind, RebalanceTrigger, User
from app.models.db.enums import RebalanceTriggerKind
from app.services.runs.persistence import execute_portfolio_run, execute_research_run
from app.services.telegram import send_message as tg_send
from app.workers.celery_app import celery_app

_ET = ZoneInfo("America/New_York")

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Transient error classification
# ---------------------------------------------------------------------------

# Exception types that indicate a temporary infrastructure/provider problem
# that is worth retrying. Everything else is treated as terminal.
_TRANSIENT_TYPES = (
    httpx.TimeoutException,     # connect / read / write / pool timeout
    httpx.ConnectError,         # DNS failure, TCP refused
    httpx.RemoteProtocolError,  # server closed connection mid-response
)


def _is_transient(exc: BaseException) -> bool:
    """Return True when the exception is likely to resolve on a retry."""
    if isinstance(exc, _TRANSIENT_TYPES):
        return True
    # HTTP 429 (rate-limited) or 5xx (provider/LLM server error) are retryable.
    # 4xx data errors (404 ticker not found, 422 bad input) are not.
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


# ---------------------------------------------------------------------------
# Agent tasks
# ---------------------------------------------------------------------------


@celery_app.task(
    name="research.execute",
    bind=True,
    acks_late=True,
    max_retries=3,
    reject_on_worker_lost=True,
)
def run_research_task(self, run_id: str) -> str:  # type: ignore[override]
    """Execute a queued research run. Returns the run_id (for Celery result
    tracking). Failures bubble up so Celery marks the task FAILURE, but the
    AgentRun row in Postgres is the actual source of truth — the API reads
    from there, not from Celery's result backend.

    Transient provider errors are retried up to 3 times (exponential backoff).
    On final failure the run remains FAILED in Postgres with a traceback step.
    """
    async def _run() -> None:
        await db_engine.dispose(close=False)
        await execute_research_run(UUID(run_id))

    logger.info("research_task_dispatch", run_id=run_id, attempt=self.request.retries + 1)
    try:
        asyncio.run(_run())
    except Exception as exc:
        if _is_transient(exc):
            delay = 60 * (2 ** self.request.retries)  # 60 → 120 → 240 s
            logger.warning(
                "research.execute transient failure (attempt %d/%d) run_id=%s: %s"
                " — retrying in %ds",
                self.request.retries + 1,
                self.max_retries + 1,
                run_id,
                exc,
                delay,
            )
            raise self.retry(exc=exc, countdown=delay)
        logger.error(
            "research.execute permanent failure run_id=%s: %s",
            run_id,
            exc,
            exc_info=True,
        )
        raise
    return run_id


@celery_app.task(
    name="portfolio.execute",
    bind=True,
    acks_late=True,
    max_retries=3,
    reject_on_worker_lost=True,
)
def run_portfolio_task(self, run_id: str) -> str:  # type: ignore[override]
    """Execute a queued portfolio run. Same retry semantics as run_research_task."""
    async def _run() -> None:
        await db_engine.dispose(close=False)
        await execute_portfolio_run(UUID(run_id))

    logger.info("portfolio_task_dispatch", run_id=run_id, attempt=self.request.retries + 1)
    try:
        asyncio.run(_run())
    except Exception as exc:
        if _is_transient(exc):
            delay = 60 * (2 ** self.request.retries)  # 60 → 120 → 240 s
            logger.warning(
                "portfolio.execute transient failure (attempt %d/%d) run_id=%s: %s"
                " — retrying in %ds",
                self.request.retries + 1,
                self.max_retries + 1,
                run_id,
                exc,
                delay,
            )
            raise self.retry(exc=exc, countdown=delay)
        logger.error(
            "portfolio.execute permanent failure run_id=%s: %s",
            run_id,
            exc,
            exc_info=True,
        )
        raise
    return run_id


@celery_app.task(name="maintenance.evaluate_triggers")
def evaluate_triggers_task() -> int:
    """Fire due triggers and create user notifications + Telegram pushes.

    Two loops:
      1. Time-based: fires_at <= now (existing behaviour, now also handles
         EARNINGS_BEAT_CHECK which fetches actual EPS from yfinance).
      2. Price-based: PRICE_BELOW / PRICE_ABOVE with fires_at IS NULL,
         evaluated only during US market hours (9:30–16:00 ET Mon–Fri).

    Returns total count of fired triggers for monitoring.
    """
    return asyncio.run(_evaluate_triggers())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_market_hours() -> bool:
    """Return True if current ET wall clock is inside regular session hours."""
    now_et = datetime.now(_ET)
    if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now_et < market_close


def _batch_prices(tickers: list[str]) -> dict[str, float]:
    """Fetch latest prices for a list of tickers via yfinance.

    Runs synchronously (called inside run_in_executor).
    Returns a dict {ticker: latest_close}. Missing tickers are omitted.
    """
    if not tickers:
        return {}
    try:
        import yfinance as yf  # noqa: PLC0415

        data = yf.download(
            tickers,
            period="1d",
            interval="1m",
            progress=False,
            auto_adjust=True,
        )
        if data.empty:
            return {}
        close = data["Close"] if "Close" in data.columns else data
        # multi-ticker → DataFrame; single ticker → Series
        if hasattr(close, "iloc"):
            last_row = close.iloc[-1]
            if hasattr(last_row, "items"):
                return {
                    str(t): float(v)
                    for t, v in last_row.items()
                    if v is not None and not (hasattr(v, "__class__") and v != v)
                }
            return {tickers[0]: float(last_row)}
        return {}
    except Exception as exc:
        logger.warning("_batch_prices failed: %s", exc)
        return {}


def _fetch_eps_beat(ticker: str, earnings_date_str: str) -> dict | None:
    """Fetch actual vs estimated EPS from yfinance. Returns dict or None."""
    try:
        import yfinance as yf  # noqa: PLC0415

        t = yf.Ticker(ticker)
        hist = t.earnings_dates
        if hist is None or hist.empty:
            return None
        # earnings_dates index is tz-aware Timestamps
        from datetime import date as _date  # noqa: PLC0415

        target = _date.fromisoformat(earnings_date_str)
        for idx, row in hist.iterrows():
            row_date = idx.date() if hasattr(idx, "date") else idx
            if abs((row_date - target).days) <= 2:
                eps_est = row.get("EPS Estimate")
                eps_act = row.get("Reported EPS")
                surprise = row.get("Surprise(%)")
                return {
                    "eps_estimate": float(eps_est) if eps_est is not None else None,
                    "eps_actual": float(eps_act) if eps_act is not None else None,
                    "surprise_pct": float(surprise) if surprise is not None else None,
                }
        return None
    except Exception as exc:
        logger.debug("_fetch_eps_beat %s: %s", ticker, exc)
        return None


# ---------------------------------------------------------------------------
# Core async evaluation
# ---------------------------------------------------------------------------

async def _evaluate_triggers() -> int:
    await db_engine.dispose(close=False)
    now = datetime.now(UTC)
    fired = 0

    async with SessionLocal() as session:
        # ----------------------------------------------------------------
        # Loop 1: time-based triggers (fires_at IS NOT NULL and <= now)
        # ----------------------------------------------------------------
        time_rows = (
            await session.execute(
                select(RebalanceTrigger)
                .where(
                    RebalanceTrigger.active.is_(True),
                    RebalanceTrigger.fires_at.is_not(None),
                    RebalanceTrigger.fires_at <= now,
                )
            )
        ).scalars().all()

        # Prefetch users needed for Telegram
        user_ids = {t.user_id for t in time_rows}
        users: dict[UUID, User] = {}
        if user_ids:
            user_rows = (
                await session.execute(select(User).where(User.id.in_(user_ids)))
            ).scalars().all()
            users = {u.id: u for u in user_rows}

        for trigger in time_rows:
            cond = trigger.condition_json
            ticker = cond.get("ticker", "")

            if trigger.kind == RebalanceTriggerKind.EARNINGS_DATE:
                notif_kind = NotificationKind.REBALANCE_TRIGGER
                title = f"📅 {ticker} earnings today"
                body = cond.get("description", f"{ticker} earnings")
            elif trigger.kind == RebalanceTriggerKind.EARNINGS_BEAT_CHECK:
                notif_kind = NotificationKind.EARNINGS_RESULT
                ed = cond.get("earnings_date", "")
                eps_data = await asyncio.get_event_loop().run_in_executor(
                    None, _fetch_eps_beat, ticker, ed
                )
                beat_str = ""
                if eps_data:
                    act = eps_data.get("eps_actual")
                    est = eps_data.get("eps_estimate")
                    surp = eps_data.get("surprise_pct")
                    if act is not None and est is not None:
                        beat_str = (
                            f" | EPS: actual {act:.2f} vs est {est:.2f}"
                            + (f" ({surp:+.1f}%)" if surp is not None else "")
                        )
                cond = {**cond, "eps_result": eps_data}
                title = f"📊 {ticker} earnings result"
                body = f"{ticker} post-earnings check{beat_str}"
            elif trigger.kind == RebalanceTriggerKind.CUSTOM:
                notif_kind = NotificationKind.WATCH_REMINDER
                desc = cond.get("description", "Watch condition triggered")
                title = f"🔔 {ticker}: {desc}"
                body = desc
            else:
                notif_kind = NotificationKind.REBALANCE_TRIGGER
                title = f"Trigger: {trigger.kind.value}"
                body = str(cond)

            session.add(
                Notification(
                    user_id=trigger.user_id,
                    kind=notif_kind,
                    payload={
                        "trigger_id": str(trigger.id),
                        "portfolio_id": str(trigger.portfolio_id) if trigger.portfolio_id else None,
                        "ticker": ticker,
                        "kind": trigger.kind.value,
                        "condition": cond,
                        "fired_at": now.isoformat(),
                        "report_id": cond.get("report_id"),
                        "title": title,
                        "body": body,
                    },
                )
            )
            trigger.active = False
            trigger.last_evaluated_at = now
            fired += 1

            # Telegram push (best-effort)
            user = users.get(trigger.user_id)
            if user and user.telegram_chat_id:
                msg = f"<b>{title}</b>\n{body}"
                await tg_send(user.telegram_chat_id, msg)

        # ----------------------------------------------------------------
        # Loop 2: price-based triggers (fires_at IS NULL, market hours only)
        # ----------------------------------------------------------------
        if _is_market_hours():
            price_rows = (
                await session.execute(
                    select(RebalanceTrigger)
                    .where(
                        RebalanceTrigger.active.is_(True),
                        RebalanceTrigger.fires_at.is_(None),
                        RebalanceTrigger.kind.in_(
                            [RebalanceTriggerKind.PRICE_BELOW, RebalanceTriggerKind.PRICE_ABOVE]
                        ),
                    )
                )
            ).scalars().all()

            if price_rows:
                tickers_needed = list({t.condition_json.get("ticker", "") for t in price_rows if t.condition_json.get("ticker")})
                prices = await asyncio.get_event_loop().run_in_executor(
                    None, _batch_prices, tickers_needed
                )

                # Prefetch any new users not already loaded
                new_user_ids = {t.user_id for t in price_rows} - set(users)
                if new_user_ids:
                    new_users = (
                        await session.execute(select(User).where(User.id.in_(new_user_ids)))
                    ).scalars().all()
                    users.update({u.id: u for u in new_users})

                for trigger in price_rows:
                    cond = trigger.condition_json
                    ticker = cond.get("ticker", "")
                    threshold = cond.get("threshold")
                    current = prices.get(ticker)

                    if current is None or threshold is None:
                        continue

                    hit = (
                        trigger.kind == RebalanceTriggerKind.PRICE_BELOW and current <= threshold
                    ) or (
                        trigger.kind == RebalanceTriggerKind.PRICE_ABOVE and current >= threshold
                    )

                    if not hit:
                        continue

                    direction = "dropped to" if trigger.kind == RebalanceTriggerKind.PRICE_BELOW else "reached"
                    title = f"💰 {ticker} {direction} ${current:.2f}"
                    body = (
                        f"Your {'entry' if trigger.kind == RebalanceTriggerKind.PRICE_BELOW else 'exit'} "
                        f"target ${threshold:.2f} was hit. Current: ${current:.2f}."
                    )

                    session.add(
                        Notification(
                            user_id=trigger.user_id,
                            kind=NotificationKind.PRICE_ALERT,
                            payload={
                                "trigger_id": str(trigger.id),
                                "ticker": ticker,
                                "kind": trigger.kind.value,
                                "threshold": threshold,
                                "current_price": current,
                                "fired_at": now.isoformat(),
                                "report_id": cond.get("report_id"),
                                "title": title,
                                "body": body,
                            },
                        )
                    )
                    trigger.active = False
                    trigger.last_evaluated_at = now
                    fired += 1

                    user = users.get(trigger.user_id)
                    if user and user.telegram_chat_id:
                        rationale = cond.get("rationale", "")
                        msg = f"<b>{title}</b>\n{body}"
                        if rationale:
                            msg += f"\n<i>{rationale}</i>"
                        await tg_send(user.telegram_chat_id, msg)

        if fired:
            await session.commit()
            logger.info("evaluate_triggers: fired %d trigger(s)", fired)
        return fired
