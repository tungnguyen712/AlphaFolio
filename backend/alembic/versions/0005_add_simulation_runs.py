"""Add simulation_runs table for portfolio backtest / simulation flow

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "simulation_runs" not in existing_tables:
        op.create_table(
            "simulation_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("positions", postgresql.JSONB(), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("benchmark", sa.String(16), nullable=False, server_default="VOO"),
            sa.Column("result_json", postgresql.JSONB(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    # `index=True` on user_id creates this index as part of create_table on a
    # fresh database, so re-inspect after table creation before adding it.
    existing_indexes = {
        idx["name"] for idx in sa.inspect(bind).get_indexes("simulation_runs")
    }
    if "ix_simulation_runs_user_id" not in existing_indexes:
        op.create_index("ix_simulation_runs_user_id", "simulation_runs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_simulation_runs_user_id", table_name="simulation_runs")
    op.drop_table("simulation_runs")
