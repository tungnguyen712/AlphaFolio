"""drop buying_power from portfolios

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("portfolios", "buying_power")


def downgrade() -> None:
    op.add_column(
        "portfolios",
        sa.Column(
            "buying_power",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
            server_default="0",
        ),
    )
