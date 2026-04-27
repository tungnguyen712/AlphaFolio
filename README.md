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

**Supply Chain**
- Descriptive relationship map for any ticker: suppliers, customers, manufacturers
- 6 parallel data sources: GLEIF (regulatory parent/subsidiary structure), Wikidata, SEC 10-K Item 1, Wikipedia, SEC EDGAR Full-Text Search (EFTS), Tavily
- Interactive React Flow graph view with dotted group boundaries per category and draggable nodes; cards view for detail
- Results cached 24 h in Redis; no LLM call — pure extraction pipeline

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

**Frontend** — Next.js 14 (App Router) · React 18 · TypeScript strict · Tailwind CSS · Clerk · @xyflow/react

## Infrastructure

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

## Observability

LangSmith traces every LangGraph execution end-to-end.

| What is captured | Where |
|---|---|
| Every agent node input/output (JSON) | LangSmith run tree |
| Per-node latency and token counts | LangSmith run tree |
| `langsmith_trace_id` stored on `agent_runs` row | Postgres — links DB record → LangSmith UI |
| Full `graph_state` checkpoint (LangGraph) | `agent_runs.graph_state` JSONB |

