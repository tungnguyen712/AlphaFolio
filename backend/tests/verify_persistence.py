"""End-to-end smoke for stage 3.5 — real agents, real Anthropic, real DB writes.

Run by hand:

    docker compose exec backend uv run python tests/verify_persistence.py NVDA

Creates a throwaway user, runs the research flow through the persistence
wrapper, then re-queries and pretty-prints what landed in agent_runs /
agent_run_steps / research_reports so you can eyeball the DB state.
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.db import (
    AgentRun,
    AgentRunStep,
    ResearchReport,
    User,
)
from app.services.runs.persistence import run_research


async def _create_user() -> tuple:
    clerk_id = f"smoke_{uuid.uuid4()}"
    async with SessionLocal() as session:
        user = User(clerk_id=clerk_id, email=f"{clerk_id}@example.com")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id, clerk_id


async def _cleanup_user(clerk_id: str) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(User).where(User.clerk_id == clerk_id))
        await session.commit()


def _banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


async def main(ticker: str) -> None:
    user_id, clerk_id = await _create_user()
    try:
        _banner(f"run_research({ticker}) — real agents, writing to DB")
        run_id, synth = await run_research(user_id=user_id, ticker=ticker)
        print(f"  run_id: {run_id}")
        print(f"  synthesis.verdict: {synth.layers.verdict}")
        print(f"  synthesis.confidence: {synth.layers.confidence:.2f}")

        async with SessionLocal() as session:
            run = (
                await session.execute(select(AgentRun).where(AgentRun.id == run_id))
            ).scalar_one()

            _banner("agent_runs row")
            print(f"  flow:        {run.flow}")
            print(f"  status:      {run.status}")
            print(f"  ticker:      {run.ticker}")
            print(f"  started_at:  {run.started_at}")
            print(f"  completed_at:{run.completed_at}")
            print(f"  graph_state keys: {sorted((run.graph_state or {}).keys())}")

            steps = (
                await session.execute(
                    select(AgentRunStep)
                    .where(AgentRunStep.run_id == run_id)
                    .order_by(AgentRunStep.completed_at)
                )
            ).scalars().all()

            _banner(f"agent_run_steps ({len(steps)} rows)")
            for s in steps:
                keys = sorted((s.output or {}).keys()) if s.output else []
                print(f"  [{s.completed_at.isoformat()}] {s.agent_name}: output_keys={keys}")

            report = (
                await session.execute(
                    select(ResearchReport).where(ResearchReport.run_id == run_id)
                )
            ).scalar_one()
            _banner("research_reports row")
            print(f"  ticker:     {report.ticker}")
            print(f"  signal:     {report.signal}")
            print(f"  confidence: {report.confidence:.2f}")
            print(f"  report_json.layers.top_3_signals:")
            for s in report.report_json["layers"]["top_3_signals"]:
                print(f"    - {s}")
            print(
                "\n  report_json sample (first 400 chars):\n    "
                f"{json.dumps(report.report_json, default=str)[:400]}..."
            )

    finally:
        await _cleanup_user(clerk_id)
        print("\n(cleanup: test user and cascaded rows removed)")


if __name__ == "__main__":
    ticker_arg = sys.argv[1].upper() if len(sys.argv) > 1 else "NVDA"
    print(f"Running persistence smoke for ticker: {ticker_arg}\n")
    asyncio.run(main(ticker_arg))
