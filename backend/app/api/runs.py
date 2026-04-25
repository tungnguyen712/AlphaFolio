"""Run kickoff and status endpoints.

POST endpoints enqueue a row, dispatch a Celery task, and return 202
immediately. GET endpoints read from agent_runs and (when the run is
COMPLETE) join the linked report or recommendation row.

Routes intentionally span two URL prefixes:
  POST /research/runs            (start a research run)
  POST /portfolios/{id}/runs     (start a portfolio run, owned by a portfolio)
  GET  /runs/{run_id}            (status of any run)
  GET  /runs/{run_id}/steps
  GET  /runs                     (recent runs, paginated)

So this module declares two routers with different prefixes and main.py
includes them both.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DBSessionDep
from app.api.portfolios import _load_owned_portfolio
from app.api.schemas.runs import (
    PortfolioRunRequest,
    ResearchRunRequest,
    RunAccepted,
    RunStatusOut,
    RunStepOut,
)
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
    )
    run_research_task.delay(str(run_id))
    return RunAccepted(run_id=run_id, flow=AgentRunFlow.RESEARCH, status=AgentRunStatus.QUEUED)


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

    if run.status == AgentRunStatus.COMPLETE:
        if run.flow == AgentRunFlow.RESEARCH:
            report = (
                await db.execute(
                    select(ResearchReport).where(ResearchReport.run_id == run_id)
                )
            ).scalar_one_or_none()
            if report is not None:
                report_json = report.report_json
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
