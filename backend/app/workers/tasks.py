"""Celery tasks that drive the agent graphs.

Tasks are sync wrappers around the async `execute_*_run` helpers — Celery's
default execution model is sync per task, so we spin up a fresh event loop
per task with `asyncio.run`. Each Celery worker process services tasks
serially (`worker_prefetch_multiplier=1`), so loop creation overhead is
negligible.

No retries: the persistence layer already records failures (status=FAILED +
`_error` step), and re-running a failed graph rarely succeeds without a
code or data fix.
"""
from __future__ import annotations

import asyncio
from uuid import UUID

from app.services.runs.persistence import execute_portfolio_run, execute_research_run
from app.workers.celery_app import celery_app


@celery_app.task(name="research.execute", acks_late=True)
def run_research_task(run_id: str) -> str:
    """Execute a queued research run. Returns the run_id (for Celery result
    tracking). Failures bubble up so Celery marks the task FAILURE, but the
    AgentRun row in Postgres is the actual source of truth — the API reads
    from there, not from Celery's result backend."""
    asyncio.run(execute_research_run(UUID(run_id)))
    return run_id


@celery_app.task(name="portfolio.execute", acks_late=True)
def run_portfolio_task(run_id: str) -> str:
    asyncio.run(execute_portfolio_run(UUID(run_id)))
    return run_id
