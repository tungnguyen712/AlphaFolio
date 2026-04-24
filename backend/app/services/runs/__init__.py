"""Persistence wrappers around the LangGraph flows.

API-layer and background-worker entry points should call the functions here
rather than invoking compiled graphs directly — they guarantee every run lands
in `agent_runs` + `agent_run_steps` and emits a domain-specific report row
(`research_reports` / `portfolio_recommendations`) on success.
"""
from app.services.runs.persistence import run_portfolio, run_research

__all__ = ["run_portfolio", "run_research"]
