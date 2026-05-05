"""Add per-step LLM cost and latency accounting.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_run_steps", sa.Column("llm_model", sa.String(128), nullable=True))
    op.add_column("agent_run_steps", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("agent_run_steps", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("agent_run_steps", sa.Column("latency_ms", sa.Float(), nullable=True))
    op.add_column(
        "agent_run_steps",
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_run_steps", "estimated_cost_usd")
    op.drop_column("agent_run_steps", "latency_ms")
    op.drop_column("agent_run_steps", "output_tokens")
    op.drop_column("agent_run_steps", "input_tokens")
    op.drop_column("agent_run_steps", "llm_model")
