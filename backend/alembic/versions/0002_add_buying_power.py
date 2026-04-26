"""add buying_power to portfolios

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add buying_power column to portfolios table
    op.add_column(
        "portfolios",
        sa.Column(
            "buying_power",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("portfolios", "buying_power")
