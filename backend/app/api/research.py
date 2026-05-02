"""Read endpoints for research reports.

Run kickoff lives in app/api/runs.py (POST /research/runs there). This module
is read-only: list and fetch already-persisted reports.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.api.deps import CurrentUserDep, DBSessionDep
from app.api.schemas.research import ResearchReportOut, ResearchReportSummary
from app.models.db import ResearchReport

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/reports", response_model=list[ResearchReportSummary])
async def list_reports(
    user: CurrentUserDep,
    db: DBSessionDep,
    ticker: str | None = None,
    portfolio_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[ResearchReport]:
    stmt = select(ResearchReport).where(ResearchReport.user_id == user.id)
    if ticker:
        stmt = stmt.where(ResearchReport.ticker == ticker.upper())
    if portfolio_id:
        stmt = stmt.where(ResearchReport.portfolio_id == portfolio_id)
    stmt = (
        stmt.order_by(ResearchReport.created_at.desc()).limit(limit).offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/reports/{report_id}", response_model=ResearchReportOut)
async def get_report(
    report_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> ResearchReportOut:
    report = (
        await db.execute(
            select(ResearchReport).where(
                ResearchReport.id == report_id, ResearchReport.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="report not found"
        )
    return ResearchReportOut(
        id=report.id,
        run_id=report.run_id,
        portfolio_id=report.portfolio_id,
        ticker=report.ticker,
        signal=report.signal,
        confidence=report.confidence,
        created_at=report.created_at,
        report=report.report_json,
    )


class _BulkDeleteBody(BaseModel):
    ids: list[UUID]


@router.delete("/reports", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reports(
    body: _BulkDeleteBody,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> None:
    """Delete one or more research reports owned by the current user.

    Silently ignores IDs that don't exist or belong to another user —
    idempotent so retry-on-network-error is safe.
    """
    if not body.ids:
        return
    await db.execute(
        delete(ResearchReport).where(
            ResearchReport.user_id == user.id,
            ResearchReport.id.in_(body.ids),
        )
    )
    await db.commit()
