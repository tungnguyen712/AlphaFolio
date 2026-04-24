# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product shape (non-negotiable)

AlphaFolio is a multi-agent stock research + portfolio tool. Two design rules govern every endpoint, graph, schema, and UI:

1. **Two flows, not one.** Stock Research ("is this ticker worth holding?") and Portfolio Builder ("how should I allocate / review my portfolio?") are distinct user intents. Keep them separate even when they share agents underneath. Do not collapse them into a single pipeline.
2. **Every recommendation surface has three layers: verdict → top 3 signals → key uncertainty.** Bake these fields into the Pydantic output schema of any synthesis/recommendation agent; render them via a shared `VerdictCard` component. Reject any report model that omits one.
3. **The flows cross-link.** Research → "Add to portfolio" feeds into the Portfolio graph. A Portfolio holding clicks through to Research with `portfolio_id` context. Rebalance triggers persist and fire notifications. The `rebalance_triggers`, `portfolio_position_pending`, and `research_reports.portfolio_id` columns exist specifically to support this loop — treat them as first-class, not v2.

## Per-agent Claude model tiering

Cost-aware assignment — do not route everything to Opus.

| Tier   | Env var                   | Agents |
|--------|---------------------------|--------|
| Opus   | `ANTHROPIC_MODEL_OPUS`    | Signal Analysis, Devil's Advocate, Synthesis |
| Sonnet | `ANTHROPIC_MODEL_SONNET`  | Portfolio Construction, Market Intelligence |
| Haiku  | `ANTHROPIC_MODEL_HAIKU`   | Data Retrieval |

Reasoning: Opus reserved for open-ended reasoning, adversarial thinking, and final confidence-weighted judgment. Sonnet for schema-bound structured reasoning. Haiku for rigid extraction/parsing (Form 4 / 10-K / S-1 sections). If one Sonnet/Haiku agent degrades in eval, escalate that one agent — do not blanket-upgrade.

## Commands

All services run in Docker Compose; the backend container uses `uv` (not pip/poetry).

```bash
# Full stack (postgres + redis + backend + worker + beat + frontend)
docker compose up --build

# Backend only (inside the backend container — use `docker compose exec backend <cmd>`)
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "message"
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
uv run pytest                              # all tests
uv run pytest tests/path/to/test.py::name  # single test
uv run ruff check .
uv run ruff format .
uv run mypy app

# Celery (already wired in compose — worker consumes queues: agents_graph, ingest, maintenance)
uv run celery -A app.workers.celery_app worker -Q agents_graph,ingest,maintenance
uv run celery -A app.workers.celery_app beat

# Frontend (inside frontend container)
npm run dev
npm run build
npm run lint
npm run typecheck
```

Health check: `GET http://localhost:8000/health` — executes `SELECT 1` against Postgres.

## Architecture

**Backend** — FastAPI (async) + SQLAlchemy 2.0 async + asyncpg, Celery with Redis broker, LangGraph for agent orchestration, Clerk for auth (JWT via JWKS), Anthropic SDK for LLM calls, LangSmith for tracing.

- `app/main.py` — FastAPI factory (`create_app`), CORS from `settings.cors_origin_list`, lifespan disposes the engine on shutdown.
- `app/config.py` — Pydantic `BaseSettings`, `.env`-backed, cached via `@lru_cache`. Use `get_settings()` everywhere; never read env vars directly.
- `app/db/session.py` — async engine + `SessionLocal` + `get_db()` dependency. `DATABASE_URL` must use `postgresql+asyncpg://`.
- `app/db/base.py` — declarative `Base` + `UUIDPKMixin` + `TimestampMixin`. New models should compose these mixins for UUID PKs and `created_at`/`updated_at`.
- `app/models/db/` — one file per table. **All models must be imported into `app/models/db/__init__.py`** so `alembic/env.py` can register them on `Base.metadata` for autogenerate.

**Frontend** — Next.js 14 (App Router), React 18, Tailwind, Clerk (`@clerk/nextjs`), TypeScript strict. Single `app/` directory, dev server runs at 3000. Calls backend via `NEXT_PUBLIC_API_URL`.

**Infra** — Postgres 16 with pgvector (`pgvector/pgvector:pg16` image), Redis 7. `infra/postgres/init.sql` enables `vector` + `uuid-ossp` extensions on first boot; the initial migration re-enables them defensively.

### Data model — the connective-tissue tables

These exist because of product Rule 3. Do not "simplify" them away.

- `research_reports(portfolio_id nullable)` — research reports opportunistically tag the portfolio they were requested from, enabling the Portfolio graph to read the latest report per holding.
- `portfolio_position_pending` — Research → Portfolio handoff. A research BUY creates a pending position; the user accepts/rejects; accepted rows flow into `portfolio_holdings`.
- `rebalance_triggers` — persistent conditions (macro event, lockup expiry, earnings date, drift threshold, custom) with `fires_at` + `active`. Worker evaluates, writes `notifications`, which bring the user back into a flow.
- `agent_runs` + `agent_run_steps` — one `agent_runs` row per graph execution (flow ∈ {research, portfolio}), with per-agent `agent_run_steps` JSONB input/output for replay and debugging. `graph_state` holds the LangGraph checkpoint payload; `langsmith_trace_id` links to LangSmith.
- `signal_cache` — keyed cache for expensive provider calls (Polygon, Quiver, SEC), with `expires_at`.
- `transcript_embeddings` — pgvector(1536) with an HNSW cosine index for earnings-call RAG.

### Alembic conventions (watch for these)

- Postgres enums are created once, up front, via `postgresql.ENUM(...).create(bind, checkfirst=True)`. Column definitions use `_enum(..., create_type=False)` so CREATE TYPE is not re-emitted. When adding a new enum, follow the same pattern or autogenerate will produce duplicate-type errors.
- `alembic/env.py` imports `app.models.db` to register models. If you add a new model file, add it to `app/models/db/__init__.py` or autogenerate will silently miss it.
- `ALEMBIC_DATABASE_URL` uses the sync `psycopg2` driver; `DATABASE_URL` uses `asyncpg`. Both point at the same DB — keep them in sync.

## Collaboration defaults

- Auto-accept routine edits and keep moving; only pause for real forks, sensitive/security changes, or hard-to-reverse actions.
- Terse responses; skip trailing "here's what I did" summaries — the diff speaks.
