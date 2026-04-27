# AlphaFolio

Multi-agent AI stock research and portfolio management platform. A LangGraph pipeline of specialized Claude agents delivers structured equity research memos with source-backed signals, valuation analysis, data quality validation, and explainable confidence scoring.

## Features

**Stock Research**
- 6-node LangGraph pipeline: Data Retrieval → Market Intel → Signal Analysis → Devil's Advocate → Validation Gate → Synthesis
- Post-retrieval news filtering — ticker relevance (word-boundary), staleness, mirror domains, near-duplicate headlines
- Form 4 insider transaction aggregation — unique filers vs raw row counts, 10b5-1 plan detection
- Deterministic validation gate before LLM synthesis: flags missing price data, unsourced signals, stale analyst data
- Structured valuation bridge with bull/base/bear scenario anchors and explicit missing-data disclosure
- Equity research memo with 8 structured sections: Recommendation, Thesis, Top Signals, Valuation Bridge, Key Uncertainties, Devil's Advocate, Data Quality, Final Rationale
- Explainable confidence breakdown with positive/negative contributor strings

**Portfolio Builder**
- Holdings management with rebalance triggers (macro event, lockup expiry, earnings date, drift threshold)
- Research → Portfolio cross-link: BUY verdicts create pending positions; holdings link back to research reports

## Agent Pipeline

```
START ─► data_retrieval (Haiku) ─┐
      └─► market_intel (Sonnet)  ─┴─► signal_analysis (Opus) ─► devils_advocate (Opus) ─► validation ─► synthesis (Opus) ─► END
```

Data retrieval and market intel run in parallel (LangGraph fan-out). The validation node runs deterministic Python checks — no LLM — before the final Opus synthesis call.

| Tier | Model | Agents |
|------|-------|--------|
| Opus | claude-opus-4-7 | Signal Analysis, Devil's Advocate, Synthesis |
| Sonnet | claude-sonnet-4-6 | Market Intelligence, Portfolio Construction |
| Haiku | claude-haiku-4-5 | Data Retrieval |

## Tech Stack

**Backend** — FastAPI (async) · SQLAlchemy 2.0 · asyncpg · LangGraph 0.2 · Celery + Redis · PostgreSQL 16 + pgvector · Anthropic SDK · Clerk JWT · LangSmith · Alembic · uv

**Frontend** — Next.js 14 (App Router) · React 18 · TypeScript strict · Tailwind CSS · Clerk

## Infrastructure (Designed For)

```
Vercel (Next.js) ──► ALB ──► ECS Cluster (Fargate)
                              ├── alphafolio-api    (uvicorn,       DesiredCount ≥ 1)
                              ├── alphafolio-worker (celery worker, DesiredCount ≥ 1)
                              └── alphafolio-beat   (celery beat,   DesiredCount = 1)

RDS PostgreSQL 16 + pgvector ◄── ECS tasks
ElastiCache Redis 7          ◄── ECS tasks
ECR ──► ECS (shared image, CMD override per service)
GitHub Actions ──► ECR push ──► alembic upgrade head ──► ecs update-service
```

## Local Development

**Prerequisites:** Docker + Docker Compose

```bash
cp .env.example .env        # fill in API keys
docker compose up --build   # postgres + redis + backend + worker + beat + frontend
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

**Inside backend container:**
```bash
docker compose exec backend uv run pytest -v
docker compose exec backend uv run ruff check .
docker compose exec backend uv run mypy app
docker compose exec backend uv run alembic revision --autogenerate -m "your message"
docker compose exec backend uv run alembic upgrade head
```

## Environment Variables

Copy `.env.example` and fill in the required keys. Required for a working local run:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` |
| `ALEMBIC_DATABASE_URL` | `postgresql://...` (sync driver) |
| `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis connection strings |
| `CLERK_SECRET_KEY` / `CLERK_PUBLISHABLE_KEY` / `CLERK_JWKS_URL` / `CLERK_ISSUER` | Clerk auth |
| `ANTHROPIC_API_KEY` | Anthropic API |
| `TAVILY_API_KEY` | News search |

Optional (stubs used if absent):
- `POLYGON_API_KEY` — falls back to fixtures in `tests/fixtures/polygon/`
- `LANGCHAIN_API_KEY` + `LANGCHAIN_TRACING_V2=true` — LangSmith tracing
