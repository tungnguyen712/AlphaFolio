# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product shape (non-negotiable)

AlphaFolio is a multi-agent stock research + portfolio tool. Two design rules govern every endpoint, graph, schema, and UI:

1. **Three flows, not one.** Stock Research ("is this ticker worth holding?"), Portfolio Builder ("how should I allocate / review my portfolio?"), and Supply Chain ("who are the related players?") are distinct user intents. Keep them separate. Do not collapse them into a single pipeline.
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

## Pipeline quality improvements (added 2026-04, updated 2026-05)

These are live in production and must be preserved. Do not revert.

**News filtering** (`app/services/data_providers/news_filter.py`):
- Called inside `market_intel.run()` after Tavily fetch, before LLM call
- Drops: unrelated ticker, stale articles, mirror domains, low-quality sources, near-duplicate headlines
- `FilteredNewsItem` list + `news_filter_summary` stored in `MarketIntelOutput`

**Form 4 aggregation** (`app/services/data_providers/sec_edgar.py`):
- `aggregate_insider_transactions()` — counts unique filers, not raw transaction rows
- `_detect_planned_status()` — reads footnote text for "10b5-1" references
- `InsiderSummary` in `DataRetrievalOutput`; Signal Analysis prompt uses it instead of raw rows

**Validation gate** (`app/services/pipeline/validation.py`):
- Pure Python, no LLM. Runs as LangGraph node between `devils_advocate` and `synthesis`
- Returns `ValidationResult` with `warnings`, `errors`, `confidence_penalty` (5% per warning, 15% per error, cap 50%)
- Synthesis subtracts `confidence_penalty` from `layers.confidence`

**Valuation bridge** (`app/services/pipeline/valuation_bridge.py`):
- Pure Python. Assembles bull (+25%) / base (+8%) / bear (−18%) price anchors from `PriceSummary.latest`
- Lists `missing_fields` (market_cap, forward_pe, ev_revenue, 52w range) explicitly

**Report sections** (`app/services/agents/synthesis.py`):
- Rationale format: `N. Section Name: content...` (numbered inline, one paragraph per section)
- `_parse_rationale_sections()` extracts → `SynthesisOutput.report_sections: dict[str, str]`
- 8 canonical headings in `SECTION_HEADINGS` constant in `app/models/agents/synthesis.py`
- Frontend uses `ReportSectionsRenderer` when `report_sections` present; `RationaleText` fallback for old reports

**Analyst Consensus Layer** (`app/services/data_providers/yahoo_consensus.py`, added 2026-05):
- `fetch_consensus(ticker) -> ConsensusData | None` via yahooquery (sync, runs in executor)
- `ConsensusData` in `app/models/agents/common.py`: target prices, recommendation_key/mean, buy/hold/sell counts, EPS estimates, `implied_upside_pct`
- Field added to `DataRetrievalOutput`; Signal Analysis prompt interprets consensus signals with coverage thresholds
- Skipped in historical mode (`as_of is not None`) to prevent look-ahead bias
- **consensus_task runs inside `asyncio.gather()` in data_retrieval** — do not await it separately
- 24-hour TTL in `signal_cache`

**Portfolio Optimization Solver** (`app/services/pipeline/portfolio_solver.py`, added 2026-05):
- Pure scipy (SLSQP) mean-variance and max-Sharpe optimizer; runs in thread pool before the LLM call
- `solve_async(tickers, risk_profile, lookback_days=90) -> SolverResult`
- Method selection: conservative → min-variance; moderate/aggressive → max-Sharpe
- Max single-position caps: conservative 20%, moderate 30%, aggressive 45%
- Fallback to equal-weight when < 2 tickers or insufficient price history
- `SolverResult` injected into `PortfolioConstructionInput.solver_result`; LLM uses weights as baseline and must explain any deviation
- Dependencies: `numpy>=1.26`, `scipy>=1.13` added to `pyproject.toml`

**LangGraph graph is now 6 nodes** (was 5):
`data_retrieval + market_intel → signal_analysis → devils_advocate → validation → synthesis`

**New Pydantic types** in `app/models/agents/`:
- `common.py`: `SourceQuality`, `FilterReasonCode`, `InsiderSummary`, `FilteredNewsItem`, `ConsensusData`
- `synthesis.py`: `ScenarioCase`, `ValuationBridge`, `ConfidenceBreakdown`, `ValidationResult`, `SECTION_HEADINGS`
- `portfolio_construction.py`: `SolverResult` (from `portfolio_solver`), `solver_result` field on `PortfolioConstructionInput`
- `SynthesisOutput` has 4 new optional fields: `valuation_bridge`, `confidence_breakdown`, `validation_result`, `insider_summary`, `report_sections`
- All are backward-compatible (optional with defaults) — old DB rows deserialize fine

**`PriceTarget.extra = "ignore"`** (`app/models/agents/common.py`):
- LLMs occasionally hallucinate `secondary_sourced` into `entry_price_target`; override drops unknown fields silently instead of raising `extra_forbidden`

**Latency fixes** (2026-05):
- `consensus_task` in `asyncio.gather()` — saves ~2–3s vs serial await
- Synthesis `max_tokens` 16 000 → 10 000 — saves ~1–2s
- Retry `wait_exponential + wait_random(0, 1)` jitter — prevents thundering-herd retries

## Deployment

- **Actual**: Railway ($5/mo hobby) — Postgres plugin + Redis plugin + 3 services (api, worker, beat)
- **Documented in README.md**: AWS ECS Fargate architecture (keep for portfolio — do not remove from README)
- **Frontend**: Vercel (free tier)
- `railway.toml` at repo root — defines Dockerfile path and default start command
- Beat must stay at exactly 1 replica always

## Supply Chain flow (Stage 5.3, added 2026-04)

A dedicated 3rd flow distinct from Research and Portfolio. **Descriptive, not a recommendation** — the verdict/top-3-signals/key-uncertainty rule does NOT apply here.

**Architecture:** Simple async pipeline (no LangGraph). Three parallel fetches → merge → Haiku extraction → cached GET endpoint.

**Data sources:**
- Wikidata SPARQL (`app/services/data_providers/wikidata.py`) — subsidiaries (P355), parent org (P749). FREE. 30-day TTL.
- SEC 10-K Item 1 Business section (`sec_edgar.fetch_10k_item1_business`) — "significant customers", "sole-source suppliers". FREE + ~$0.002 Haiku per extraction. 7-day TTL.
- Tavily supply chain queries (`app/services/data_providers/tavily_supply_chain.py`) — fetched and cached; entity parsing deferred to v1.1.

**V1 relationship types:** supplier, customer, manufacturer, parent, subsidiary

**API:** `GET /supply-chain/{ticker}` — synchronous, cached 24h in `signal_cache`. No Celery, no SSE.

**Frontend:** `/supply-chain` (search), `/supply-chain/[ticker]` (dashboard). Cross-links to Research per product rule 3.

**Model:** `app/models/agents/supply_chain.py` — `RelatedCompany`, `SupplyChainReport`, `SupplyChainEntities`

**V2 roadmap (implement after V1 stable in production):**
1. Geography — `country: str | None` from Wikidata P17; display as flag in CompanyChip
2. Dependency % — extract from 10-K Item 7 (MD&A); store as `dependency_pct: float | None`
3. Numeric confidence score — replace `"high"|"medium"|"low"` with `float` (0.0–1.0); scoring: Wikidata=0.90, 10-K explicit+significant=0.80, 10-K unnamed=0.55, Tavily corroborated=0.40, Tavily-only=0.25

## Stage progression (updated 2026-05)

All stages complete:
- Stages 1–4.4: Backend pipeline, DB schema, agent graph, Celery workers, API endpoints, Clerk auth
- Stage 5.0: Next.js 14 frontend fully wired — research flow, portfolio flow, VerdictCard, report rendering, SSE run progress
- Stage 5.1: Pipeline quality — news filter, Form 4 aggregation + 10b5-1 detection, validation gate, valuation bridge, structured report sections
- Stage 5.2: Deployment — Railway + Vercel, AWS ECS architecture documented in README
- Stage 5.3: Supply Chain flow — 3rd flow, Wikidata + 10-K Item 1 + Tavily, `GET /supply-chain/{ticker}`, frontend at `/supply-chain/[ticker]`
- Stage 5.4: Analyst Consensus Layer — yahooquery provider, `ConsensusData` type, threaded through DataRetrievalOutput → SignalAnalysis prompt
- Stage 5.5: Portfolio Optimization Solver — scipy mean-variance / max-Sharpe, `SolverResult`, injected into PortfolioConstructionInput before LLM call
- Stage 5.6: UX — Chrome-style bulk delete for research runs and reports; research report limit increased to 20
