"""Celery tasks that drive the agent graphs and maintenance jobs.

Agent tasks are sync wrappers around async helpers — Celery's default
execution model is sync per task, so we spin up a fresh event loop per task
with `asyncio.run`. `worker_prefetch_multiplier=1` means serial execution per
worker process, so loop creation overhead is negligible.

No retries on agent tasks: the persistence layer already records failures
(status=FAILED + `_error` step), and re-running a failed graph rarely succeeds
without a code or data fix.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.session import SessionLocal, engine as db_engine
from app.models.db import Notification, NotificationKind, Portfolio, RebalanceTrigger
from app.services.runs.persistence import execute_portfolio_run, execute_research_run
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="research.execute", acks_late=True)
def run_research_task(run_id: str) -> str:
    """Execute a queued research run. Returns the run_id (for Celery result
    tracking). Failures bubble up so Celery marks the task FAILURE, but the
    AgentRun row in Postgres is the actual source of truth — the API reads
    from there, not from Celery's result backend."""
    async def _run() -> None:
        await db_engine.dispose(close=False)
        await execute_research_run(UUID(run_id))

    asyncio.run(_run())
    return run_id


@celery_app.task(name="portfolio.execute", acks_late=True)
def run_portfolio_task(run_id: str) -> str:
    async def _run() -> None:
        await db_engine.dispose(close=False)
        await execute_portfolio_run(UUID(run_id))

    asyncio.run(_run())
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
