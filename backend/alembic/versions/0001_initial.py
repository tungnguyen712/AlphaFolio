"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> postgresql.ENUM:
    # create_type=False: types are created explicitly up front; column usages must not re-emit CREATE TYPE.
    return postgresql.ENUM(*values, name=name, create_type=False)


risk_profile_enum = _enum("conservative", "moderate", "aggressive", name="risk_profile_enum")
asset_class_enum = _enum("ipo", "established", "private", name="asset_class_enum")
research_signal_enum = _enum("buy", "hold", "sell", name="research_signal_enum")
agent_run_flow_enum = _enum("research", "portfolio", name="agent_run_flow_enum")
agent_run_status_enum = _enum(
    "queued", "running", "complete", "failed", name="agent_run_status_enum"
)
pending_position_status_enum = _enum(
    "pending", "accepted", "rejected", name="pending_position_status_enum"
)
rebalance_trigger_kind_enum = _enum(
    "macro_event",
    "lockup_expiry",
    "earnings_date",
    "drift_threshold",
    "custom",
    name="rebalance_trigger_kind_enum",
)
notification_kind_enum = _enum(
    "rebalance_trigger", "run_complete", "other", name="notification_kind_enum"
)

_ALL_ENUMS = (
    risk_profile_enum,
    asset_class_enum,
    research_signal_enum,
    agent_run_flow_enum,
    agent_run_status_enum,
    pending_position_status_enum,
    rebalance_trigger_kind_enum,
    notification_kind_enum,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    for e in _ALL_ENUMS:
        # checkfirst=True guards against reruns; each enum's CREATE TYPE happens exactly here.
        postgresql.ENUM(*e.enums, name=e.name).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clerk_id", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "portfolios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("cash_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("risk_profile", risk_profile_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"])

    op.create_table(
        "portfolio_holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("shares", sa.Numeric(18, 6), nullable=False),
        sa.Column("avg_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("asset_class", asset_class_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_portfolio_holdings_portfolio_id", "portfolio_holdings", ["portfolio_id"])
    op.create_index("ix_portfolio_holdings_ticker", "portfolio_holdings", ["ticker"])

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=True),
        sa.Column("flow", agent_run_flow_enum, nullable=False),
        sa.Column("status", agent_run_status_enum, nullable=False, server_default="queued"),
        sa.Column("graph_state", postgresql.JSONB(), nullable=True),
        sa.Column("langsmith_trace_id", sa.String(128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_ticker", "agent_runs", ["ticker"])

    op.create_table(
        "agent_run_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_run_steps_run_id", "agent_run_steps", ["run_id"])

    op.create_table(
        "research_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("signal", research_signal_enum, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("report_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_research_reports_user_id", "research_reports", ["user_id"])
    op.create_index("ix_research_reports_portfolio_id", "research_reports", ["portfolio_id"])
    op.create_index("ix_research_reports_ticker", "research_reports", ["ticker"])

    op.create_table(
        "portfolio_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recommendation_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_portfolio_recommendations_portfolio_id",
                    "portfolio_recommendations", ["portfolio_id"])

    op.create_table(
        "signal_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cache_key", sa.String(512), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_signal_cache_expires_at", "signal_cache", ["expires_at"])

    op.create_table(
        "transcript_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("quarter", sa.String(16), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transcript_embeddings_ticker", "transcript_embeddings", ["ticker"])
    op.execute(
        "CREATE INDEX ix_transcript_embeddings_embedding_hnsw "
        "ON transcript_embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "portfolio_position_pending",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("target_pct", sa.Numeric(6, 4), nullable=False),
        sa.Column("source_report_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research_reports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", pending_position_status_enum, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_portfolio_position_pending_portfolio_id",
                    "portfolio_position_pending", ["portfolio_id"])
    op.create_index("ix_portfolio_position_pending_ticker",
                    "portfolio_position_pending", ["ticker"])
    op.create_index("ix_portfolio_position_pending_status",
                    "portfolio_position_pending", ["status"])

    op.create_table(
        "rebalance_triggers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", rebalance_trigger_kind_enum, nullable=False),
        sa.Column("condition_json", postgresql.JSONB(), nullable=False),
        sa.Column("fires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_rebalance_triggers_portfolio_id", "rebalance_triggers", ["portfolio_id"])
    op.create_index("ix_rebalance_triggers_fires_at", "rebalance_triggers", ["fires_at"])
    op.create_index("ix_rebalance_triggers_active", "rebalance_triggers", ["active"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", notification_kind_enum, nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("rebalance_triggers")
    op.drop_table("portfolio_position_pending")
    op.drop_table("transcript_embeddings")
    op.drop_table("signal_cache")
    op.drop_table("portfolio_recommendations")
    op.drop_table("research_reports")
    op.drop_table("agent_run_steps")
    op.drop_table("agent_runs")
    op.drop_table("portfolio_holdings")
    op.drop_table("portfolios")
    op.drop_table("users")

    for e in reversed(_ALL_ENUMS):
        postgresql.ENUM(name=e.name).drop(op.get_bind(), checkfirst=True)
