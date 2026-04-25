"""Persistence wrappers around the LangGraph flows.

Two-phase API:
  - `enqueue_*_run(...)` writes the QUEUED row, returns run_id immediately.
  - `execute_*_run(run_id)` runs the graph and transitions status.

API endpoints call enqueue + dispatch a Celery task; the worker calls
execute. Direct callers (tests, verify scripts) use the convenience wrappers
`run_research` / `run_portfolio`, which call both in sequence.
"""
from app.services.runs.persistence import (
    enqueue_portfolio_run,
    enqueue_research_run,
    execute_portfolio_run,
    execute_research_run,
    run_portfolio,
    run_research,
)

__all__ = [
    "enqueue_portfolio_run",
    "enqueue_research_run",
    "execute_portfolio_run",
    "execute_research_run",
    "run_portfolio",
    "run_research",
]
