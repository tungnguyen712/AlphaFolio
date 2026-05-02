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
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select

from app.db.session import SessionLocal, engine as db_engine
from app.models.db import Notification, NotificationKind, Portfolio, RebalanceTrigger
from app.services.runs.persistence import execute_portfolio_run, execute_research_run
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

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
    """Fire due rebalance triggers and create user notifications.

    Finds all active triggers whose `fires_at <= now()`, creates one
    Notification per trigger (kind=REBALANCE_TRIGGER), marks each trigger
    inactive, and returns the count of triggered items for monitoring.
    """
    return asyncio.run(_evaluate_triggers())


async def _evaluate_triggers() -> int:
    await db_engine.dispose(close=False)
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(RebalanceTrigger, Portfolio)
                .join(Portfolio, RebalanceTrigger.portfolio_id == Portfolio.id)
                .where(
                    RebalanceTrigger.active.is_(True),
                    RebalanceTrigger.fires_at <= now,
                )
            )
        ).all()

        if not rows:
            return 0

        for trigger, portfolio in rows:
            session.add(
                Notification(
                    user_id=portfolio.user_id,
                    kind=NotificationKind.REBALANCE_TRIGGER,
                    payload={
                        "trigger_id": str(trigger.id),
                        "portfolio_id": str(trigger.portfolio_id),
                        "kind": trigger.kind.value,
                        "condition": trigger.condition_json,
                        "fired_at": now.isoformat(),
                    },
                )
            )
            trigger.active = False
            trigger.last_evaluated_at = now

        await session.commit()
        logger.info("evaluate_triggers: fired %d trigger(s)", len(rows))
        return len(rows)
