"""Add historical research support: as_of_date on research_reports, backtest flow enum value

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block in Postgres.
    # We commit the Alembic-managed transaction, run the DDL in autocommit, then
    # the subsequent op.add_column() opens a new implicit transaction.
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(sa.text("ALTER TYPE agent_run_flow_enum ADD VALUE IF NOT EXISTS 'backtest'"))

    op.add_column(
        "research_reports",
        sa.Column("as_of_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_reports", "as_of_date")
    # Postgres does not support removing enum values; leave 'backtest' in place.
