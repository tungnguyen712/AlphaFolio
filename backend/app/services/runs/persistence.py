"""DB persistence wrappers around the research and portfolio LangGraph flows.

Two-phase design (split in stage 4.2):

  enqueue_*_run(...)      -> creates the agent_runs row with status=QUEUED,
                             returns run_id immediately. Used by the API
                             so it can return 202 + run_id without blocking
                             on graph execution.

  execute_*_run(run_id)   -> locks the queued row, transitions to RUNNING,
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
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
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
from app.services.data_providers._cache import cache_get, cache_set, make_cache_key
from app.services.llm.anthropic_client import (
    LLMCallRecord,
    drain_llm_call_records,
    reset_llm_accounting,
    start_llm_accounting,
)
from app.services.pipeline.condition_extractor import extract_triggers
from app.services.redis_client import publish_run_event

# Compile graphs once at import time. The compiled objects are stateless —
# state lives per-invocation — so sharing them across calls is safe and cheaper
# than rebuilding per request.
_research_graph = build_research_graph()
_portfolio_graph = build_portfolio_graph()
logger = structlog.get_logger(__name__)
_RESEARCH_OUTPUT_CACHE_TTL_SECONDS = 30 * 60


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
    as_of_date: date | None = None,
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
        "as_of_date": str(as_of_date) if as_of_date else None,
    }
    flow = AgentRunFlow.BACKTEST if as_of_date else AgentRunFlow.RESEARCH
    async with SessionLocal() as session:
        run = AgentRun(
            user_id=user_id,
            flow=flow,
            ticker=stored_ticker,
            status=AgentRunStatus.QUEUED,
            graph_state={"_queued_inputs": queued_inputs},
            langsmith_trace_id=langsmith_trace_id,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        logger.info(
            "agent_run_enqueued",
            run_id=str(run.id),
            user_id=str(user_id),
            flow=flow.value,
            ticker=stored_ticker,
            mode=mode,
        )
        return run.id


async def execute_research_run(run_id: UUID) -> SynthesisOutput:
    """Load a queued run, execute the research graph, persist outputs.

    Idempotency guard: only QUEUED rows may transition into execution. The
    row is locked while the status flips to RUNNING, so Celery redeliveries
    and retries cannot run the same graph twice for one run_id.
    """
    async with SessionLocal() as session:
        run = await _claim_queued_run(session, run_id)
        queued_inputs = (run.graph_state or {}).get("_queued_inputs") or {}
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

            as_of_raw = queued_inputs.get("as_of_date")
            as_of = date.fromisoformat(as_of_raw) if as_of_raw else None
            cache_key = _research_output_cache_key(queued_inputs, as_of)
            if cache_key is not None:
                cached = await cache_get(cache_key)
                if cached is not None:
                    try:
                        synth = SynthesisOutput.model_validate(cached["synthesis"])
                    except Exception as exc:
                        logger.warning(
                            "research_output_cache_invalid",
                            run_id=str(run_id),
                            cache_key=cache_key,
                            error=str(exc),
                        )
                    else:
                        await _persist_cache_hit_step(session, run_id, cache_key)
                        await _finalize_run(session, run, {"synthesis": synth})
                        await _persist_research_report(
                            session=session,
                            run=run,
                            run_id=run_id,
                            synth=synth,
                            queued_inputs=queued_inputs,
                            as_of=as_of,
                        )
                        logger.info(
                            "research_output_cache_hit",
                            run_id=str(run_id),
                            cache_key=cache_key,
                            ticker=synth.ticker,
                        )
                        asyncio.create_task(
                            publish_run_event(
                                run_id, {"type": "done", "status": "complete"}
                            )
                        )
                        return synth

            initial = new_research_state(
                ticker=ticker_str,
                mode=queued_inputs.get("mode", "public"),
                lookback_days=queued_inputs.get("lookback_days", 90),
                portfolio_id=queued_inputs.get("portfolio_id"),
                in_portfolio=in_portfolio,
                as_of_date=as_of,
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
                as_of_date=as_of,
            )
            report_id = report.id  # UUID set by default= at construction
            session.add(report)
            await session.commit()
            logger.info(
                "research_report_persisted",
                run_id=str(run_id),
                report_id=str(report_id),
                ticker=synth.ticker,
                signal=synth.signal.value,
            )

            # Extract watch triggers from the finished report (best-effort)
            try:
                triggers = await extract_triggers(
                    synth,
                    user_id=run.user_id,
                    report_id=report_id,
                    ticker=synth.ticker,
                    as_of_date=as_of,
                )
                if triggers:
                    session.add_all(triggers)
                    await session.commit()
            except Exception as _exc:
                # Never block the research flow on trigger extraction failure
                import logging as _log  # noqa: PLC0415
                _log.getLogger(__name__).warning(
                    "extract_triggers failed for %s: %s", synth.ticker, _exc
                )

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

            if cache_key is not None:
                await cache_set(
                    cache_key,
                    {"synthesis": synth.model_dump(mode="json")},
                    _RESEARCH_OUTPUT_CACHE_TTL_SECONDS,
                )
                logger.info(
                    "research_output_cache_stored",
                    run_id=str(run_id),
                    cache_key=cache_key,
                    ticker=synth.ticker,
                    ttl_seconds=_RESEARCH_OUTPUT_CACHE_TTL_SECONDS,
                )

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
        logger.info(
            "agent_run_enqueued",
            run_id=str(run.id),
            user_id=str(user_id),
            flow=AgentRunFlow.PORTFOLIO.value,
            portfolio_id=str(portfolio_id),
        )
        return run.id


async def execute_portfolio_run(run_id: UUID) -> PortfolioConstructionOutput:
    async with SessionLocal() as session:
        run = await _claim_queued_run(session, run_id)
        q = (run.graph_state or {}).get("_queued_inputs") or {}
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
            logger.info(
                "portfolio_recommendation_persisted",
                run_id=str(run_id),
                recommendation_id=str(recommendation.id),
                portfolio_id=q["portfolio_id"],
            )

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


def _research_output_cache_key(
    queued_inputs: dict[str, Any],
    as_of: date | None,
) -> str | None:
    """Cache only user-independent public research outputs."""
    if queued_inputs.get("mode", "public") != "public":
        return None
    if queued_inputs.get("portfolio_id") is not None:
        return None
    ticker = queued_inputs.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        return None
    return make_cache_key(
        "research.output.v1",
        ticker=ticker.upper(),
        mode="public",
        lookback_days=queued_inputs.get("lookback_days", 90),
        as_of_date=as_of.isoformat() if as_of else None,
    )


async def _persist_cache_hit_step(
    session: AsyncSession,
    run_id: UUID,
    cache_key: str,
) -> None:
    step = AgentRunStep(
        run_id=run_id,
        agent_name="cache_hit",
        input=None,
        output={"cache_hit": True, "cache_key": cache_key},
        error=None,
        completed_at=datetime.now(UTC),
    )
    session.add(step)
    await session.flush()
    event = _step_event(step, "cache_hit", step.output or {})
    await session.commit()
    asyncio.create_task(publish_run_event(run_id, event))


async def _persist_research_report(
    *,
    session: AsyncSession,
    run: AgentRun,
    run_id: UUID,
    synth: SynthesisOutput,
    queued_inputs: dict[str, Any],
    as_of: date | None,
) -> None:
    portfolio_id_raw = queued_inputs.get("portfolio_id")
    report = ResearchReport(
        user_id=run.user_id,
        portfolio_id=UUID(portfolio_id_raw) if portfolio_id_raw else None,
        run_id=run_id,
        ticker=synth.ticker,
        signal=synth.signal,
        confidence=synth.layers.confidence,
        report_json=synth.model_dump(mode="json"),
        as_of_date=as_of,
    )
    report_id = report.id
    session.add(report)
    await session.commit()
    logger.info(
        "research_report_persisted",
        run_id=str(run_id),
        report_id=str(report_id),
        ticker=synth.ticker,
        signal=synth.signal.value,
    )

    try:
        triggers = await extract_triggers(
            synth,
            user_id=run.user_id,
            report_id=report_id,
            ticker=synth.ticker,
            as_of_date=as_of,
        )
        if triggers:
            session.add_all(triggers)
            await session.commit()
    except Exception as _exc:
        logger.warning(
            "research_trigger_extraction_failed",
            run_id=str(run_id),
            ticker=synth.ticker,
            error=str(_exc),
            exc_info=True,
        )

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


async def _claim_queued_run(session: AsyncSession, run_id: UUID) -> AgentRun:
    """Atomically claim a queued run for execution.

    `FOR UPDATE` serializes competing workers. The first caller flips the row
    to RUNNING; any later caller observes RUNNING/COMPLETE/FAILED and exits
    before streaming graph steps or creating flow-specific output rows.
    """
    result = await session.execute(
        select(AgentRun).where(AgentRun.id == run_id).with_for_update()
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise LookupError(f"agent_run {run_id} not found")
    if run.status != AgentRunStatus.QUEUED:
        logger.info(
            "agent_run_execution_refused",
            run_id=str(run_id),
            status=run.status.value,
            flow=run.flow.value,
        )
        raise RuntimeError(
            f"agent_run {run_id} has status {run.status}; only queued runs can execute"
        )

    run.status = AgentRunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    await session.commit()
    logger.info(
        "agent_run_claimed",
        run_id=str(run.id),
        user_id=str(run.user_id),
        flow=run.flow.value,
        ticker=run.ticker,
    )
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
    accounting_token = start_llm_accounting()

    async for update in graph.astream(initial_state, stream_mode="updates"):
        # `updates` yields {node_name: partial_state_update} — usually one key
        # per tick, but can be multiple when parallel branches finish in the
        # same loop iteration. Persist each one independently.
        step_completed_at = datetime.now(UTC)
        pending_steps: list[tuple[AgentRunStep, str, dict[str, Any]]] = []
        for node_name, node_update in update.items():
            if not isinstance(node_update, dict):
                continue
            accumulated.update(node_update)
            jsonable_output = _to_jsonable(node_update)
            accounting = _aggregate_llm_records(drain_llm_call_records(node_name))

            step = AgentRunStep(
                run_id=run_id,
                agent_name=node_name,
                input=None,
                output=jsonable_output,
                error=None,
                llm_model=accounting["llm_model"],
                input_tokens=accounting["input_tokens"],
                output_tokens=accounting["output_tokens"],
                latency_ms=accounting["latency_ms"],
                estimated_cost_usd=accounting["estimated_cost_usd"],
                started_at=None,
                completed_at=step_completed_at,
            )
            session.add(step)
            pending_steps.append((step, node_name, jsonable_output))
            logger.info(
                "agent_run_step_completed",
                run_id=str(run_id),
                agent_name=node_name,
                llm_model=step.llm_model,
                input_tokens=step.input_tokens,
                output_tokens=step.output_tokens,
                latency_ms=step.latency_ms,
                estimated_cost_usd=step.estimated_cost_usd,
            )
        await session.flush()
        pending_events = [
            _step_event(step, node_name, jsonable_output)
            for step, node_name, jsonable_output in pending_steps
        ]
        await session.commit()
        for event in pending_events:
            asyncio.create_task(publish_run_event(run_id, event))

    reset_llm_accounting(accounting_token)
    return accumulated


def _aggregate_llm_records(records: list[LLMCallRecord]) -> dict[str, Any]:
    if not records:
        return {
            "llm_model": None,
            "input_tokens": None,
            "output_tokens": None,
            "latency_ms": None,
            "estimated_cost_usd": None,
        }
    models = {record.model for record in records}
    input_tokens = _sum_optional_int(record.input_tokens for record in records)
    output_tokens = _sum_optional_int(record.output_tokens for record in records)
    estimated_cost = _sum_optional_float(record.estimated_cost_usd for record in records)
    return {
        "llm_model": next(iter(models)) if len(models) == 1 else "multiple",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": round(sum(record.latency_ms for record in records), 2),
        "estimated_cost_usd": (
            round(estimated_cost, 6) if estimated_cost is not None else None
        ),
    }


def _sum_optional_int(values: Iterable[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _sum_optional_float(values: Iterable[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _step_event(
    step: AgentRunStep, node_name: str, jsonable_output: dict[str, Any]
) -> dict[str, Any]:
    return {
        "type": "step",
        "id": str(step.id),
        "agent_name": node_name,
        "output": jsonable_output,
        "error": step.error,
        "llm_model": step.llm_model,
        "input_tokens": step.input_tokens,
        "output_tokens": step.output_tokens,
        "latency_ms": step.latency_ms,
        "estimated_cost_usd": step.estimated_cost_usd,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
    }


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
    logger.info(
        "agent_run_completed",
        run_id=str(run.id),
        flow=run.flow.value,
        latency_ms=_run_latency_ms(run),
    )


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
    logger.warning(
        "agent_run_failed",
        run_id=str(run.id),
        flow=run.flow.value,
        error=error_msg,
        latency_ms=_run_latency_ms(run),
    )
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
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj


def _run_latency_ms(run: AgentRun) -> float | None:
    if run.started_at is None or run.completed_at is None:
        return None
    return round((run.completed_at - run.started_at).total_seconds() * 1000, 2)
