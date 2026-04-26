"""DB persistence wrappers around the research and portfolio LangGraph flows.

Two-phase design (split in stage 4.2):

  enqueue_*_run(...)      -> creates the agent_runs row with status=QUEUED,
                             returns run_id immediately. Used by the API
                             so it can return 202 + run_id without blocking
                             on graph execution.

  execute_*_run(run_id)   -> loads the queued row, transitions to RUNNING,
                             streams the graph (writing one agent_run_steps
                             row per node), persists the flow-specific
                             report, transitions to COMPLETE / FAILED.
                             Called from a Celery worker.

  run_research(...) /
  run_portfolio(...)      -> convenience wrappers (enqueue + execute) used
                             by direct callers (verify scripts, tests).
                             Behavior preserved for stage-3.5 backward compat.

Failure path: any exception during execute_* funnels through _fail_run,
which marks status=FAILED and writes an `_error` step with the traceback.
"""
from __future__ import annotations

import asyncio
import traceback
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.graphs.portfolio import build_portfolio_graph, new_portfolio_state
from app.graphs.research import build_research_graph, new_research_state
from app.models.agents import (
    HoldingSnapshot,
    PortfolioConstructionOutput,
    RetrievalMode,
    SynthesisOutput,
)
from app.models.db import (
    AgentRun,
    AgentRunFlow,
    AgentRunStatus,
    AgentRunStep,
    PendingPositionStatus,
    Portfolio,
    PortfolioHolding,
    PortfolioPositionPending,
    PortfolioRecommendation,
    ResearchReport,
    ResearchSignal,
    RiskProfile,
)
from app.services.redis_client import publish_run_event

# Compile graphs once at import time. The compiled objects are stateless —
# state lives per-invocation — so sharing them across calls is safe and cheaper
# than rebuilding per request.
_research_graph = build_research_graph()
_portfolio_graph = build_portfolio_graph()


# ===========================================================================
# Research flow
# ===========================================================================


async def enqueue_research_run(
    *,
    user_id: UUID,
    ticker: str,
    mode: RetrievalMode = "public",
    lookback_days: int = 90,
    portfolio_id: UUID | None = None,
    langsmith_trace_id: str | None = None,
) -> UUID:
    """Insert a QUEUED agent_runs row and return its id.

    The graph itself is not invoked here — that's `execute_research_run`'s
    job. Run-level inputs (mode, lookback_days, portfolio_id) are stashed
    in graph_state so the worker can recover them without a separate table.

    For pre_ipo mode, `ticker` is the company name string. We store the
    display form on agent_runs.ticker; case is preserved for non-public.
    """
    stored_ticker = ticker.upper() if mode == "public" else ticker
    queued_inputs = {
        "ticker": ticker,
        "mode": mode,
        "lookback_days": lookback_days,
        "portfolio_id": str(portfolio_id) if portfolio_id else None,
    }
    async with SessionLocal() as session:
        run = AgentRun(
            user_id=user_id,
            flow=AgentRunFlow.RESEARCH,
            ticker=stored_ticker,
            status=AgentRunStatus.QUEUED,
            graph_state={"_queued_inputs": queued_inputs},
            langsmith_trace_id=langsmith_trace_id,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run.id


async def execute_research_run(run_id: UUID) -> SynthesisOutput:
    """Load a queued run, execute the research graph, persist outputs.

    Idempotency caveat: if called twice on the same run_id, the second call
    will overwrite step rows and produce a second research_report row tied
    to the same run. The Celery task layer dispatches once per run_id, so
    in normal operation this isn't a concern.
    """
    async with SessionLocal() as session:
        run = await _load_run(session, run_id)
        queued_inputs = (run.graph_state or {}).get("_queued_inputs") or {}

        run.status = AgentRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        await session.commit()
        asyncio.create_task(
            publish_run_event(run_id, {"type": "status", "status": "running"})
        )

        try:
            ticker_str = queued_inputs.get("ticker") or run.ticker or ""
            ticker_upper = ticker_str.upper()
            in_portfolio = False
            if ticker_upper:
                check = await session.execute(
                    select(PortfolioHolding.id)
                    .join(Portfolio, PortfolioHolding.portfolio_id == Portfolio.id)
                    .where(
                        Portfolio.user_id == run.user_id,
                        PortfolioHolding.ticker == ticker_upper,
                    )
                    .limit(1)
                )
                in_portfolio = check.scalar_one_or_none() is not None

            initial = new_research_state(
                ticker=ticker_str,
                mode=queued_inputs.get("mode", "public"),
                lookback_days=queued_inputs.get("lookback_days", 90),
                portfolio_id=queued_inputs.get("portfolio_id"),
                in_portfolio=in_portfolio,
            )
            final_state = await _stream_and_persist(
                session, _research_graph, initial, run_id
            )

            synth: SynthesisOutput = final_state["synthesis"]
            await _finalize_run(session, run, final_state)

            portfolio_id_raw = queued_inputs.get("portfolio_id")
            report = ResearchReport(
                user_id=run.user_id,
                portfolio_id=UUID(portfolio_id_raw) if portfolio_id_raw else None,
                run_id=run_id,
                ticker=synth.ticker,
                signal=synth.signal,
                confidence=synth.layers.confidence,
                report_json=synth.model_dump(mode="json"),
            )
            report_id = report.id  # UUID set by default= at construction
            session.add(report)
            await session.commit()

            # Research BUY + portfolio context → queue pending position
            if synth.signal == ResearchSignal.BUY and portfolio_id_raw:
                pending = PortfolioPositionPending(
                    portfolio_id=UUID(portfolio_id_raw),
                    ticker=synth.ticker,
                    target_pct=Decimal(str(synth.recommended_position_pct or 0)),
                    source_report_id=report_id,
                    status=PendingPositionStatus.PENDING,
                )
                session.add(pending)
                await session.commit()

            asyncio.create_task(
                publish_run_event(run_id, {"type": "done", "status": "complete"})
            )
            return synth

        except Exception as exc:
            await _fail_run(session, run, exc)
            raise


async def run_research(
    *,
    user_id: UUID,
    ticker: str,
    mode: RetrievalMode = "public",
    lookback_days: int = 90,
    portfolio_id: UUID | None = None,
    langsmith_trace_id: str | None = None,
) -> tuple[UUID, SynthesisOutput]:
    """Convenience wrapper: enqueue + execute synchronously.

    Used by `verify_*.py` smoke scripts and `test_run_persistence.py`. The
    API layer never calls this — it uses `enqueue_research_run` + the Celery
    task to keep the request-response cycle non-blocking.
    """
    run_id = await enqueue_research_run(
        user_id=user_id,
        ticker=ticker,
        mode=mode,
        lookback_days=lookback_days,
        portfolio_id=portfolio_id,
        langsmith_trace_id=langsmith_trace_id,
    )
    synth = await execute_research_run(run_id)
    return run_id, synth


# ===========================================================================
# Portfolio flow
# ===========================================================================


async def enqueue_portfolio_run(
    *,
    user_id: UUID,
    portfolio_id: UUID,
    holdings: list[HoldingSnapshot],
    cash_balance: Decimal,
    risk_profile: RiskProfile,
    candidates: list[SynthesisOutput] | None = None,
    objective: str | None = None,
    langsmith_trace_id: str | None = None,
) -> UUID:
    """Insert a QUEUED agent_runs row for the portfolio flow.

    Holdings/cash/candidates are serialized into graph_state so the worker
    can rehydrate them. Decimals stringify via _to_jsonable.
    """
    queued_inputs = {
        "portfolio_id": str(portfolio_id),
        "holdings": [h.model_dump(mode="json") for h in holdings],
        "cash_balance": str(cash_balance),
        "risk_profile": risk_profile.value,
        "candidates": [c.model_dump(mode="json") for c in (candidates or [])],
        "objective": objective,
    }
    async with SessionLocal() as session:
        run = AgentRun(
            user_id=user_id,
            flow=AgentRunFlow.PORTFOLIO,
            ticker=None,
            status=AgentRunStatus.QUEUED,
            graph_state={"_queued_inputs": queued_inputs},
            langsmith_trace_id=langsmith_trace_id,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run.id


async def execute_portfolio_run(run_id: UUID) -> PortfolioConstructionOutput:
    async with SessionLocal() as session:
        run = await _load_run(session, run_id)
        q = (run.graph_state or {}).get("_queued_inputs") or {}

        run.status = AgentRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        await session.commit()
        asyncio.create_task(
            publish_run_event(run_id, {"type": "status", "status": "running"})
        )

        try:
            holdings = [HoldingSnapshot.model_validate(h) for h in q.get("holdings", [])]
            candidates = [
                SynthesisOutput.model_validate(c) for c in q.get("candidates", [])
            ]
            initial = new_portfolio_state(
                portfolio_id=q["portfolio_id"],
                holdings=holdings,
                cash_balance=Decimal(q["cash_balance"]),
                risk_profile=RiskProfile(q["risk_profile"]),
                candidates=candidates,
                objective=q.get("objective"),
            )
            final_state = await _stream_and_persist(
                session, _portfolio_graph, initial, run_id
            )

            rec: PortfolioConstructionOutput = final_state["recommendation"]
            await _finalize_run(session, run, final_state)

            recommendation = PortfolioRecommendation(
                portfolio_id=UUID(q["portfolio_id"]),
                run_id=run_id,
                recommendation_json=rec.model_dump(mode="json"),
            )
            session.add(recommendation)
            await session.commit()

            asyncio.create_task(
                publish_run_event(run_id, {"type": "done", "status": "complete"})
            )
            return rec

        except Exception as exc:
            await _fail_run(session, run, exc)
            raise


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
    """Convenience wrapper: enqueue + execute synchronously."""
    run_id = await enqueue_portfolio_run(
        user_id=user_id,
        portfolio_id=portfolio_id,
        holdings=holdings,
        cash_balance=cash_balance,
        risk_profile=risk_profile,
        candidates=candidates,
        objective=objective,
        langsmith_trace_id=langsmith_trace_id,
    )
    rec = await execute_portfolio_run(run_id)
    return run_id, rec


# ===========================================================================
# Internals
# ===========================================================================


async def _load_run(session: AsyncSession, run_id: UUID) -> AgentRun:
    result = await session.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise LookupError(f"agent_run {run_id} not found")
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
        pending_events: list[dict[str, Any]] = []
        for node_name, node_update in update.items():
            if not isinstance(node_update, dict):
                continue
            accumulated.update(node_update)
            jsonable_output = _to_jsonable(node_update)

            step = AgentRunStep(
                run_id=run_id,
                agent_name=node_name,
                input=None,
                output=jsonable_output,
                started_at=None,
                completed_at=step_completed_at,
            )
            session.add(step)
            pending_events.append({
                "type": "step",
                "agent_name": node_name,
                "output": jsonable_output,
                "error": None,
                "completed_at": step_completed_at.isoformat(),
            })
        await session.commit()
        for event in pending_events:
            asyncio.create_task(publish_run_event(run_id, event))

    return accumulated


async def _finalize_run(
    session: AsyncSession,
    run: AgentRun,
    final_state: dict[str, Any],
) -> None:
    run.status = AgentRunStatus.COMPLETE
    run.completed_at = datetime.now(UTC)
    # Strip the _queued_inputs marker from graph_state on completion — it's
    # bookkeeping for the worker, not part of the run's deliverable.
    run.graph_state = _to_jsonable(final_state)
    await session.commit()


async def _fail_run(session: AsyncSession, run: AgentRun, exc: BaseException) -> None:
    """Mark the run FAILED and attach the traceback as a trailing step row.

    Uses a fresh transaction because the outer one may be in an aborted state
    after the raise — rollback + retry on the shared session is fragile.
    """
    await session.rollback()

    error_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    error_msg = f"{type(exc).__name__}: {exc}"
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
    asyncio.create_task(
        publish_run_event(
            run.id,
            {"type": "done", "status": "failed", "error": error_msg[:300]},
        )
    )


def _to_jsonable(obj: Any) -> Any:
    """Best-effort JSONB serialization for graph state / node updates.

    Pydantic agent outputs have model_dump(mode="json"); for plain dicts we
    recurse. Anything weird (Decimal, datetime) at leaves gets stringified
    via the default= path in asyncpg's JSONB encoder on write — but we
    normalize Pydantic up front so the stored blob is round-trippable.
    """
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
