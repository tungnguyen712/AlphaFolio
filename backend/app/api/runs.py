"""Run kickoff, status, and SSE streaming endpoints.

POST endpoints enqueue a row, dispatch a Celery task, and return 202
immediately. GET endpoints read from agent_runs and (when the run is
COMPLETE) join the linked report or recommendation row.

Routes intentionally span two URL prefixes:
  POST /research/runs            (start a research run)
  POST /portfolios/{id}/runs     (start a portfolio run, owned by a portfolio)
  GET  /runs/{run_id}            (status of any run)
  GET  /runs/{run_id}/stream     (SSE — live step events via Redis pub/sub)
  GET  /runs/{run_id}/steps
  GET  /runs                     (recent runs, paginated)

So this module declares two routers with different prefixes and main.py
includes them both.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.api.deps import CurrentUserDep, DBSessionDep
from app.api.portfolios import _load_owned_portfolio
from app.api.schemas.runs import (
    PortfolioRunRequest,
    ResearchRunRequest,
    RunAccepted,
    RunStatusOut,
    RunStepOut,
)
from app.db.session import SessionLocal
from app.models.agents import HoldingSnapshot, SynthesisOutput
from app.models.db import (
    AgentRun,
    AgentRunFlow,
    AgentRunStatus,
    AgentRunStep,
    PortfolioHolding,
    PortfolioRecommendation,
    ResearchReport,
)
from app.services.redis_client import get_redis, run_event_channel
from app.services.runs import enqueue_portfolio_run, enqueue_research_run
from app.workers.tasks import run_portfolio_task, run_research_task

# Public router — POST /research/runs lives under the /research prefix to
# stay consistent with /research/reports. The status/list endpoints live at
# /runs (no prefix) so they're flow-agnostic.
research_runs_router = APIRouter(prefix="/research", tags=["runs"])
runs_router = APIRouter(prefix="", tags=["runs"])


# ---------------------------------------------------------------------------
# Kickoff: research
# ---------------------------------------------------------------------------


@research_runs_router.post(
    "/runs", response_model=RunAccepted, status_code=status.HTTP_202_ACCEPTED
)
async def start_research_run(
    body: ResearchRunRequest,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> RunAccepted:
    if body.portfolio_id is not None:
        # Verify the user owns the portfolio they're tagging research to.
        await _load_owned_portfolio(db, body.portfolio_id, user.id)

    run_id = await enqueue_research_run(
        user_id=user.id,
        ticker=body.ticker,
        mode=body.mode,
        lookback_days=body.lookback_days,
        portfolio_id=body.portfolio_id,
        as_of_date=body.as_of_date,
    )
    run_research_task.delay(str(run_id))
    flow = AgentRunFlow.BACKTEST if body.as_of_date else AgentRunFlow.RESEARCH
    return RunAccepted(run_id=run_id, flow=flow, status=AgentRunStatus.QUEUED)


# ---------------------------------------------------------------------------
# Kickoff: portfolio
# ---------------------------------------------------------------------------


@runs_router.post(
    "/portfolios/{portfolio_id}/runs",
    response_model=RunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_portfolio_run(
    portfolio_id: UUID,
    body: PortfolioRunRequest,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> RunAccepted:
    portfolio = await _load_owned_portfolio(db, portfolio_id, user.id)

    holdings_rows = (
        await db.execute(
            select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio_id)
        )
    ).scalars().all()
    holdings = [
        HoldingSnapshot(
            ticker=h.ticker,
            shares=Decimal(h.shares),
            avg_cost=Decimal(h.avg_cost),
            asset_class=h.asset_class,
        )
        for h in holdings_rows
    ]

    candidates: list[SynthesisOutput] = []
    if body.candidate_report_ids:
        rows = (
            await db.execute(
                select(ResearchReport).where(
                    ResearchReport.user_id == user.id,
                    ResearchReport.id.in_(body.candidate_report_ids),
                )
            )
        ).scalars().all()
        # Refuse if any requested id was missing or owned by someone else —
        # don't silently drop candidates without telling the caller.
        if len(rows) != len(body.candidate_report_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="one or more candidate_report_ids not found",
            )
        candidates = [SynthesisOutput.model_validate(r.report_json) for r in rows]

    run_id = await enqueue_portfolio_run(
        user_id=user.id,
        portfolio_id=portfolio.id,
        holdings=holdings,
        cash_balance=portfolio.cash_balance,
        risk_profile=portfolio.risk_profile,
        candidates=candidates,
        objective=body.objective,
    )
    run_portfolio_task.delay(str(run_id))
    return RunAccepted(run_id=run_id, flow=AgentRunFlow.PORTFOLIO, status=AgentRunStatus.QUEUED)


# ---------------------------------------------------------------------------
# Status: any run
# ---------------------------------------------------------------------------


@runs_router.get("/runs/{run_id}", response_model=RunStatusOut)
async def get_run(
    run_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> RunStatusOut:
    run = await _load_owned_run(db, run_id, user.id)
    report_json: dict | None = None
    recommendation_json: dict | None = None
    error_text: str | None = None
    as_of_date = None

    if run.status == AgentRunStatus.COMPLETE:
        if run.flow in (AgentRunFlow.RESEARCH, AgentRunFlow.BACKTEST):
            report = (
                await db.execute(
                    select(ResearchReport).where(ResearchReport.run_id == run_id)
                )
            ).scalar_one_or_none()
            if report is not None:
                report_json = report.report_json
                as_of_date = report.as_of_date
        else:
            rec = (
                await db.execute(
                    select(PortfolioRecommendation).where(
                        PortfolioRecommendation.run_id == run_id
                    )
                )
            ).scalar_one_or_none()
            if rec is not None:
                recommendation_json = rec.recommendation_json

    elif run.status == AgentRunStatus.FAILED:
        err_step = (
            await db.execute(
                select(AgentRunStep)
                .where(
                    AgentRunStep.run_id == run_id,
                    AgentRunStep.agent_name == "_error",
                )
                .order_by(AgentRunStep.completed_at.desc())
            )
        ).scalars().first()
        if err_step is not None:
            error_text = err_step.error

    return RunStatusOut(
        id=run.id,
        flow=run.flow,
        status=run.status,
        ticker=run.ticker,
        started_at=run.started_at,
        completed_at=run.completed_at,
        report=report_json,
        recommendation=recommendation_json,
        as_of_date=as_of_date,
        error=error_text,
    )


@runs_router.get("/runs/{run_id}/steps", response_model=list[RunStepOut])
async def get_run_steps(
    run_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> list[AgentRunStep]:
    await _load_owned_run(db, run_id, user.id)
    rows = (
        await db.execute(
            select(AgentRunStep)
            .where(AgentRunStep.run_id == run_id)
            .order_by(AgentRunStep.completed_at)
        )
    ).scalars().all()
    return list(rows)


@runs_router.get("/runs/{run_id}/stream")
async def stream_run_events(
    run_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
    last_event_id_query: str | None = Query(default=None, alias="last_event_id"),
) -> StreamingResponse:
    """SSE stream of agent-step events for a run.

    Emits `step` events as each agent node completes, a `status` event when
    the run transitions to RUNNING, and a terminal `done` event on completion
    or failure. Clients should close the connection after receiving `done`.

    Connects to an already-finished run replay DB steps after Last-Event-ID
    immediately and sends `done` without waiting on Redis.
    """
    # Ownership check must happen HERE, before the StreamingResponse is
    # returned. HTTPException raised inside an async generator fires after
    # headers are already committed (Starlette sends 200 before iterating the
    # body), so a 404 inside the generator can't reach the client correctly.
    run = await _load_owned_run(db, run_id, user.id)
    last_event_id = last_event_id_header or last_event_id_query
    return StreamingResponse(
        _run_event_generator(run_id, run.status, last_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _run_event_generator(
    run_id: UUID, run_status: AgentRunStatus, last_event_id: str | None = None
) -> AsyncIterator[bytes]:
    def sse(payload: dict[str, Any], event_id: str | None = None) -> bytes:
        prefix = f"id: {event_id}\n" if event_id else ""
        return f"{prefix}data: {json.dumps(payload)}\n\n".encode()

    # Terminal path: replay DB steps then close immediately.
    if run_status in (AgentRunStatus.COMPLETE, AgentRunStatus.FAILED):
        async with SessionLocal() as db:
            rows = (
                await db.execute(_steps_stmt(run_id))
            ).scalars().all()
        error_text: str | None = None
        for r in _steps_after_last_event_id(rows, last_event_id):
            if r.agent_name == "_error":
                error_text = r.error
            else:
                yield sse({
                    "type": "step",
                    "id": str(r.id),
                    "agent_name": r.agent_name,
                    "output": r.output,
                    "error": r.error,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }, str(r.id))
        yield sse({
            "type": "done",
            "status": run_status.value,
            "error": error_text if run_status == AgentRunStatus.FAILED else None,
        })
        return

    # Live path: subscribe first so we don't miss events, then catch up from DB.
    redis = get_redis()
    channel = run_event_channel(run_id)
    async with redis.pubsub() as pubsub:
        await pubsub.subscribe(channel)

        async with SessionLocal() as db:
            rows = (
                await db.execute(_steps_stmt(run_id))
            ).scalars().all()
            # Re-check status in the same session — run may have completed
            # between the ownership check and the subscription.
            fresh_run = (
                await db.execute(
                    select(AgentRun).where(AgentRun.id == run_id)
                )
            ).scalar_one()
            current_status = fresh_run.status

        seen: set[str] = set()
        for r in _steps_after_last_event_id(rows, last_event_id):
            if r.agent_name != "_error":
                event_id = str(r.id)
                seen.add(event_id)
                yield sse({
                    "type": "step",
                    "id": event_id,
                    "agent_name": r.agent_name,
                    "output": r.output,
                    "error": r.error,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }, event_id)

        # If run completed while we were setting up, emit done and return.
        if current_status in (AgentRunStatus.COMPLETE, AgentRunStatus.FAILED):
            error_row = next((r for r in rows if r.agent_name == "_error"), None)
            yield sse({
                "type": "done",
                "status": current_status.value,
                "error": (
                    error_row.error
                    if error_row and current_status == AgentRunStatus.FAILED
                    else None
                ),
            })
            return

        # Stream live events from Redis.
        deadline = asyncio.get_event_loop().time() + 600  # 10 min max
        while True:
            if asyncio.get_event_loop().time() > deadline:
                yield sse({"type": "done", "status": "failed", "error": "stream timeout"})
                return

            # Poll with a short timeout so we can re-check run status periodically.
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2.0)
            if message is None:
                # Keepalive comment — prevents Railway/Cloudflare from closing an
                # idle HTTP/2 connection while Opus is generating (can take 60-90s).
                yield b": keepalive\n\n"
                # No message yet — check if run already completed in DB (catch-up).
                async with SessionLocal() as db:
                    check = (await db.execute(
                        select(AgentRun).where(AgentRun.id == run_id)
                    )).scalar_one_or_none()
                if check and check.status in (AgentRunStatus.COMPLETE, AgentRunStatus.FAILED):
                    # Replay any steps we haven't emitted yet.
                    async with SessionLocal() as db:
                        late_rows = (await db.execute(
                            _steps_stmt(run_id)
                        )).scalars().all()
                    err: str | None = None
                    for r in late_rows:
                        if r.agent_name == "_error":
                            err = r.error
                            continue
                        event_id = str(r.id)
                        if event_id not in seen:
                            seen.add(event_id)
                            yield sse({
                                "type": "step",
                                "id": event_id,
                                "agent_name": r.agent_name,
                                "output": r.output,
                                "error": r.error,
                                "completed_at": (
                                    r.completed_at.isoformat()
                                    if r.completed_at
                                    else None
                                ),
                            }, event_id)
                    yield sse({
                        "type": "done",
                        "status": check.status.value,
                        "error": err if check.status == AgentRunStatus.FAILED else None,
                    })
                    return
                continue

            payload = json.loads(message["data"])

            # Deduplicate steps already replayed from DB.
            if payload.get("type") == "step":
                event_id = payload.get("id")
                if not isinstance(event_id, str):
                    continue
                if event_id in seen:
                    continue
                seen.add(event_id)

            yield sse(payload, payload.get("id") if payload.get("type") == "step" else None)
            if payload.get("type") == "done":
                return


@runs_router.get("/runs", response_model=list[RunStatusOut])
async def list_runs(
    user: CurrentUserDep,
    db: DBSessionDep,
    flow: AgentRunFlow | None = None,
    run_status: AgentRunStatus | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[RunStatusOut]:
    stmt = select(AgentRun).where(AgentRun.user_id == user.id)
    if flow:
        stmt = stmt.where(AgentRun.flow == flow)
    if run_status:
        stmt = stmt.where(AgentRun.status == run_status)
    stmt = (
        stmt.order_by(AgentRun.started_at.desc().nulls_last())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    # List endpoint returns shallow status — clients fetch /runs/{id} for the
    # nested report/recommendation/error blob.
    return [
        RunStatusOut(
            id=r.id,
            flow=r.flow,
            status=r.status,
            ticker=r.ticker,
            started_at=r.started_at,
            completed_at=r.completed_at,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_owned_run(db, run_id: UUID, user_id: UUID) -> AgentRun:
    run = (
        await db.execute(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="run not found"
        )
    return run


def _steps_stmt(run_id: UUID):
    return (
        select(AgentRunStep)
        .where(AgentRunStep.run_id == run_id)
        .order_by(AgentRunStep.completed_at.nulls_last(), AgentRunStep.id)
    )


def _steps_after_last_event_id(
    rows: list[AgentRunStep], last_event_id: str | None
) -> list[AgentRunStep]:
    """Return rows after the cursor step id, replaying all rows for bad cursors."""
    if not last_event_id:
        return rows
    for idx, row in enumerate(rows):
        if str(row.id) == last_event_id:
            return rows[idx + 1 :]
    return rows


class _BulkDeleteRunsBody(BaseModel):
    ids: list[UUID]


@runs_router.delete("/runs", status_code=status.HTTP_204_NO_CONTENT)
async def delete_runs(
    body: _BulkDeleteRunsBody,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> None:
    """Delete one or more agent runs owned by the current user.

    Cascades to agent_run_steps via DB FK. Silently ignores unknown / foreign
    IDs — idempotent for safe retries.
    """
    if not body.ids:
        return
    await db.execute(
        delete(AgentRun).where(
            AgentRun.user_id == user.id,
            AgentRun.id.in_(body.ids),
        )
    )
    await db.commit()
