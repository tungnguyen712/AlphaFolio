"""Add price-watch triggers and Telegram notification support.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-02

Changes:
- Add PRICE_BELOW, PRICE_ABOVE, EARNINGS_BEAT_CHECK values to rebalance_trigger_kind_enum
- Add PRICE_ALERT, EARNINGS_RESULT, WATCH_REMINDER values to notification_kind_enum
- Add telegram_chat_id column to users
- Add user_id column to rebalance_triggers (NOT NULL, FK → users)
- Make rebalance_triggers.portfolio_id nullable
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Extend Postgres enums with new values
    # ALTER TYPE ... ADD VALUE is transactional in PG 12+ but must be
    # outside an explicit transaction block — Alembic runs DDL outside
    # transactions for us. IF NOT EXISTS guards against reruns.
    # ------------------------------------------------------------------
    op.execute("ALTER TYPE rebalance_trigger_kind_enum ADD VALUE IF NOT EXISTS 'price_below'")
    op.execute("ALTER TYPE rebalance_trigger_kind_enum ADD VALUE IF NOT EXISTS 'price_above'")
    op.execute("ALTER TYPE rebalance_trigger_kind_enum ADD VALUE IF NOT EXISTS 'earnings_beat_check'")
    op.execute("ALTER TYPE notification_kind_enum ADD VALUE IF NOT EXISTS 'price_alert'")
    op.execute("ALTER TYPE notification_kind_enum ADD VALUE IF NOT EXISTS 'earnings_result'")
    op.execute("ALTER TYPE notification_kind_enum ADD VALUE IF NOT EXISTS 'watch_reminder'")

    # ------------------------------------------------------------------
    # 2. Add telegram_chat_id to users
    # ------------------------------------------------------------------
    op.add_column("users", sa.Column("telegram_chat_id", sa.String(32), nullable=True))

    # ------------------------------------------------------------------
    # 3. Add user_id to rebalance_triggers
    #    Step A: add nullable so backfill can run on existing rows.
    #    Step B: backfill from portfolios (handles existing data).
    #    Step C: make NOT NULL.
    #    Step D: add FK + index.
    # ------------------------------------------------------------------
    op.add_column(
        "rebalance_triggers",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Backfill existing rows that have a portfolio_id
    op.execute(
        """
        UPDATE rebalance_triggers rt
        SET    user_id = p.user_id
        FROM   portfolios p
        WHERE  rt.portfolio_id = p.id
          AND  rt.user_id IS NULL
        """
    )

    op.alter_column("rebalance_triggers", "user_id", nullable=False)

    op.create_foreign_key(
        "fk_rebalance_triggers_user_id",
        "rebalance_triggers",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_rebalance_triggers_user_id", "rebalance_triggers", ["user_id"])

    # ------------------------------------------------------------------
    # 4. Make portfolio_id nullable on rebalance_triggers
    #    (price-watch and research-report triggers are not portfolio-bound)
    # ------------------------------------------------------------------
    op.alter_column("rebalance_triggers", "portfolio_id", nullable=True)


def downgrade() -> None:
    # Restore portfolio_id NOT NULL (rows without portfolio_id would fail)
    op.alter_column("rebalance_triggers", "portfolio_id", nullable=False)

    op.drop_index("ix_rebalance_triggers_user_id", table_name="rebalance_triggers")
    op.drop_constraint("fk_rebalance_triggers_user_id", "rebalance_triggers", type_="foreignkey")
    op.drop_column("rebalance_triggers", "user_id")
    op.drop_column("users", "telegram_chat_id")

    # Note: Postgres does not support removing enum values.
    # The added values (price_below, price_above, etc.) remain in the DB type
    # after downgrade but are harmless since no rows use them.
