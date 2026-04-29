"""Simulation flow API — hypothetical portfolio backtesting.

Synchronous (supply-chain pattern): POST runs the engine and returns the
result directly. Results are cached in signal_cache so repeated requests for
the same parameters are free.

Endpoints:
  POST /simulation/runs         — run a new simulation (or return cached)
  GET  /simulation/runs/{id}    — fetch a saved simulation result
  GET  /simulation/runs         — list the user's saved simulations
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DBSessionDep
from app.models.db import SimulationRun
from app.services.data_providers._cache import cache_get, cache_set
from app.services.simulation.engine import SimPosition, SimResult, run_simulation

router = APIRouter(prefix="/simulation", tags=["simulation"])

_SIM_CACHE_TTL = 24 * 3600  # 24 hours


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class SimPositionIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    weight: float = Field(gt=0.0, le=1.0)


class SimRunRequest(BaseModel):
    positions: list[SimPositionIn] = Field(min_length=1, max_length=10)
    start_date: date
    end_date: date
    benchmark: str = Field(default="VOO", min_length=1, max_length=16)


class SimMetricsOut(BaseModel):
    ticker: str
    total_return: float
    cagr: float
    sharpe: float
    max_drawdown: float
    start_price: float
    end_price: float


class SimDailyPoint(BaseModel):
    date: str
    cumulative_pct: float


class SimRunOut(BaseModel):
    id: UUID
    positions: list[dict[str, Any]]
    start_date: date
    end_date: date
    benchmark: str
    status: str
    series: dict[str, list[SimDailyPoint]] | None = None
    portfolio_series: list[SimDailyPoint] | None = None
    metrics: dict[str, SimMetricsOut] | None = None
    portfolio_metrics: SimMetricsOut | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/runs", response_model=SimRunOut, status_code=status.HTTP_201_CREATED)
async def create_simulation(
    body: SimRunRequest,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> SimRunOut:
    _validate_request(body)

    positions = [SimPosition(ticker=p.ticker.upper(), weight=p.weight) for p in body.positions]
    cache_key = _cache_key(positions, body.start_date, body.end_date, body.benchmark.upper())

    # Check signal_cache first
    cached = await cache_get(cache_key)
    if cached is not None:
        result_json = cached
    else:
        try:
            result: SimResult = await run_simulation(
                positions=positions,
                start_date=body.start_date,
                end_date=body.end_date,
                benchmark=body.benchmark.upper(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        result_json = _result_to_json(result)
        await cache_set(cache_key, result_json, _SIM_CACHE_TTL)

    run = SimulationRun(
        user_id=user.id,
        positions=[{"ticker": p.ticker, "weight": p.weight} for p in positions],
        start_date=body.start_date,
        end_date=body.end_date,
        benchmark=body.benchmark.upper(),
        result_json=result_json,
        status="complete",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    return _to_out(run)


@router.get("/runs/{run_id}", response_model=SimRunOut)
async def get_simulation(
    run_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> SimRunOut:
    run = await _load_owned(db, run_id, user.id)
    return _to_out(run)


@router.get("/runs", response_model=list[SimRunOut])
async def list_simulations(
    user: CurrentUserDep,
    db: DBSessionDep,
    limit: int = 20,
    offset: int = 0,
) -> list[SimRunOut]:
    rows = (
        await db.execute(
            select(SimulationRun)
            .where(SimulationRun.user_id == user.id)
            .order_by(SimulationRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [_to_out(r) for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_request(body: SimRunRequest) -> None:
    if body.end_date <= body.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be after start_date",
        )
    days = (body.end_date - body.start_date).days
    if days < 30:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Date range must be at least 30 days",
        )
    if days > 3650:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Date range cannot exceed 10 years",
        )
    total_weight = sum(p.weight for p in body.positions)
    if abs(total_weight - 1.0) > 0.02:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Position weights must sum to 1.0 (got {total_weight:.3f})",
        )


def _cache_key(
    positions: list[SimPosition],
    start_date: date,
    end_date: date,
    benchmark: str,
) -> str:
    key_data = json.dumps({
        "positions": sorted([{"t": p.ticker, "w": p.weight} for p in positions], key=lambda x: x["t"]),
        "start": str(start_date),
        "end": str(end_date),
        "benchmark": benchmark,
    }, sort_keys=True)
    return f"sim.v1:{hashlib.sha256(key_data.encode()).hexdigest()[:32]}"


def _result_to_json(result: SimResult) -> dict[str, Any]:
    return {
        "series": {
            ticker: [{"date": p.date, "cumulative_pct": p.cumulative_pct} for p in points]
            for ticker, points in result.series.items()
        },
        "portfolio_series": [
            {"date": p.date, "cumulative_pct": p.cumulative_pct}
            for p in result.portfolio_series
        ],
        "metrics": {
            ticker: {
                "ticker": m.ticker,
                "total_return": m.total_return,
                "cagr": m.cagr,
                "sharpe": m.sharpe,
                "max_drawdown": m.max_drawdown,
                "start_price": m.start_price,
                "end_price": m.end_price,
            }
            for ticker, m in result.metrics.items()
        },
        "portfolio_metrics": {
            "ticker": result.portfolio_metrics.ticker,
            "total_return": result.portfolio_metrics.total_return,
            "cagr": result.portfolio_metrics.cagr,
            "sharpe": result.portfolio_metrics.sharpe,
            "max_drawdown": result.portfolio_metrics.max_drawdown,
            "start_price": result.portfolio_metrics.start_price,
            "end_price": result.portfolio_metrics.end_price,
        },
    }


def _to_out(run: SimulationRun) -> SimRunOut:
    result = run.result_json or {}
    raw_metrics = result.get("metrics", {})
    raw_pm = result.get("portfolio_metrics")
    raw_series = result.get("series", {})
    raw_ps = result.get("portfolio_series", [])

    return SimRunOut(
        id=run.id,
        positions=run.positions,
        start_date=run.start_date,
        end_date=run.end_date,
        benchmark=run.benchmark,
        status=run.status,
        series={k: [SimDailyPoint(**p) for p in v] for k, v in raw_series.items()} if raw_series else None,
        portfolio_series=[SimDailyPoint(**p) for p in raw_ps] if raw_ps else None,
        metrics={k: SimMetricsOut(**v) for k, v in raw_metrics.items()} if raw_metrics else None,
        portfolio_metrics=SimMetricsOut(**raw_pm) if raw_pm else None,
    )


async def _load_owned(db, run_id: UUID, user_id: UUID) -> SimulationRun:
    run = (
        await db.execute(
            select(SimulationRun).where(
                SimulationRun.id == run_id,
                SimulationRun.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="simulation not found")
    return run
