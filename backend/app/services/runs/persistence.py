"""DB persistence wrappers around the research and portfolio LangGraph flows.

Every call here:
  1. Opens an `agent_runs` row (status=RUNNING, started_at=now).
  2. Streams the graph via `astream(stream_mode="updates")` and writes one
     `agent_run_steps` row per node completion with the node's output dict
     (JSONB). Each step row is committed immediately — so if the process
     dies mid-run, partial progress is preserved for replay.
  3. On clean completion, dumps the final typed state to `graph_state`,
     flips status to COMPLETE, sets completed_at, and writes the
     flow-specific report row (`research_reports` for research,
     `portfolio_recommendations` for portfolio).
  4. On exception, flips status to FAILED, records the traceback on a
     trailing step row, and re-raises.

No LangGraph checkpointer for now — the dump-at-end in `graph_state` plus
per-step outputs gives us replay without introducing a second DB driver
(langgraph-checkpoint-postgres uses psycopg v3; our stack is asyncpg).
Revisit once we add background job resume in stage 4.
"""
from __future__ import annotations

import traceback
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.graphs.portfolio import build_portfolio_graph, new_portfolio_state
from app.graphs.research import build_research_graph, new_research_state
from app.models.agents import (
    HoldingSnapshot,
    PortfolioConstructionOutput,
    SynthesisOutput,
)
from app.models.db import (
    AgentRun,
    AgentRunFlow,
    AgentRunStatus,
    AgentRunStep,
    PortfolioRecommendation,
    ResearchReport,
    RiskProfile,
)

# Compile graphs once at import time. The compiled objects are stateless —
# state lives per-invocation — so sharing them across calls is safe and cheaper
# than rebuilding per request.
_research_graph = build_research_graph()
_portfolio_graph = build_portfolio_graph()


# ---------------------------------------------------------------------------
# Research flow
# ---------------------------------------------------------------------------


async def run_research(
    *,
    user_id: UUID,
    ticker: str,
    lookback_days: int = 90,
    portfolio_id: UUID | None = None,
    langsmith_trace_id: str | None = None,
) -> tuple[UUID, SynthesisOutput]:
    """Run the research graph with full DB persistence.

    Returns (agent_run_id, synthesis_output). The research_report is also
    persisted and can be looked up by run_id.
    """
    async with SessionLocal() as session:
        run = await _open_run(
            session,
            user_id=user_id,
            flow=AgentRunFlow.RESEARCH,
            ticker=ticker.upper(),
            langsmith_trace_id=langsmith_trace_id,
        )
        run_id = run.id

        try:
            initial = new_research_state(
                ticker=ticker,
                lookback_days=lookback_days,
                portfolio_id=str(portfolio_id) if portfolio_id else None,
            )
            final_state = await _stream_and_persist(session, _research_graph, initial, run_id)

            synth: SynthesisOutput = final_state["synthesis"]
            await _finalize_run(session, run, final_state)

            report = ResearchReport(
                user_id=user_id,
                portfolio_id=portfolio_id,
                run_id=run_id,
                ticker=synth.ticker,
                signal=synth.signal,
                confidence=synth.layers.confidence,
                report_json=synth.model_dump(mode="json"),
            )
            session.add(report)
            await session.commit()

            return run_id, synth

        except Exception as exc:
            await _fail_run(session, run, exc)
            raise


# ---------------------------------------------------------------------------
# Portfolio flow
# ---------------------------------------------------------------------------


async def run_portfolio(
    *,
    user_id: UUID,
    portfolio_id: UUID,
    holdings: list[HoldingSnapshot],
    cash_balance: Decimal,
    risk_profile: RiskProfile,
    candidates: list[SynthesisOutput] | None = None,
    objective: str | None = None,
    langsmith_trace_id: str | None = None,
) -> tuple[UUID, PortfolioConstructionOutput]:
    """Run the portfolio graph with full DB persistence."""
    async with SessionLocal() as session:
        run = await _open_run(
            session,
            user_id=user_id,
            flow=AgentRunFlow.PORTFOLIO,
            ticker=None,
            langsmith_trace_id=langsmith_trace_id,
        )
        run_id = run.id

        try:
            initial = new_portfolio_state(
                portfolio_id=str(portfolio_id),
                holdings=holdings,
                cash_balance=cash_balance,
                risk_profile=risk_profile,
                candidates=candidates,
                objective=objective,
            )
            final_state = await _stream_and_persist(session, _portfolio_graph, initial, run_id)

            rec: PortfolioConstructionOutput = final_state["recommendation"]
            await _finalize_run(session, run, final_state)

            recommendation = PortfolioRecommendation(
                portfolio_id=portfolio_id,
                run_id=run_id,
                recommendation_json=rec.model_dump(mode="json"),
            )
            session.add(recommendation)
            await session.commit()

            return run_id, rec

        except Exception as exc:
            await _fail_run(session, run, exc)
            raise


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _open_run(
    session: AsyncSession,
    *,
    user_id: UUID,
    flow: AgentRunFlow,
    ticker: str | None,
    langsmith_trace_id: str | None,
) -> AgentRun:
    run = AgentRun(
        user_id=user_id,
        flow=flow,
        ticker=ticker,
        status=AgentRunStatus.RUNNING,
        started_at=datetime.now(UTC),
        langsmith_trace_id=langsmith_trace_id,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _stream_and_persist(
    session: AsyncSession,
    graph: Any,
    initial_state: dict[str, Any],
    run_id: UUID,
) -> dict[str, Any]:
    """Stream `updates` from the graph, persist one step per node completion,
    and return the reconstructed final state."""
    accumulated: dict[str, Any] = dict(initial_state)

    async for update in graph.astream(initial_state, stream_mode="updates"):
        # `updates` yields {node_name: partial_state_update} — usually one key
        # per tick, but can be multiple when parallel branches finish in the
        # same loop iteration. Persist each one independently.
        step_completed_at = datetime.now(UTC)
        for node_name, node_update in update.items():
            if not isinstance(node_update, dict):
                continue
            accumulated.update(node_update)

            step = AgentRunStep(
                run_id=run_id,
                agent_name=node_name,
                input=None,  # stage 3.5: full input context is in graph_state
                output=_to_jsonable(node_update),
                started_at=None,  # node-level timing is a stage-3.6 concern
                completed_at=step_completed_at,
            )
            session.add(step)
        await session.commit()

    return accumulated


async def _finalize_run(
    session: AsyncSession,
    run: AgentRun,
    final_state: dict[str, Any],
) -> None:
    run.status = AgentRunStatus.COMPLETE
    run.completed_at = datetime.now(UTC)
    run.graph_state = _to_jsonable(final_state)
    await session.commit()


async def _fail_run(session: AsyncSession, run: AgentRun, exc: BaseException) -> None:
    """Mark the run FAILED and attach the traceback as a trailing step row.

    Uses a fresh transaction because the outer one may be in an aborted state
    after the raise — rollback + retry on the shared session is fragile.
    """
    await session.rollback()

    error_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    run.status = AgentRunStatus.FAILED
    run.completed_at = datetime.now(UTC)
    session.add(run)

    session.add(
        AgentRunStep(
            run_id=run.id,
            agent_name="_error",
            input=None,
            output=None,
            error=error_text[:20_000],
            completed_at=datetime.now(UTC),
        )
    )
    await session.commit()


def _to_jsonable(obj: Any) -> Any:
    """Best-effort JSONB serialization for graph state / node updates.

    Pydantic agent outputs have model_dump(mode="json"); for plain dicts we
    recurse. Anything weird (Decimal, datetime) at leaves gets stringified
    via the default= path in asyncpg's JSONB encoder on write — but we
    normalize Pydantic up front so the stored blob is round-trippable.
    """
    from pydantic import BaseModel

    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, UUID):
        return str(obj)
    return obj
