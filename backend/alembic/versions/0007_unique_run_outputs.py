"""Make run output persistence unique by run_id.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-03
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Older duplicate executions may have produced multiple output rows for
    # one run. Keep the newest row so the unique constraints can be applied.
    op.execute(
        """
        DELETE FROM research_reports rr
        USING (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY run_id
                       ORDER BY created_at DESC, id DESC
                   ) AS duplicate_rank
            FROM research_reports
            WHERE run_id IS NOT NULL
        ) ranked
        WHERE rr.id = ranked.id
          AND ranked.duplicate_rank > 1
        """
    )
    op.execute(
        """
        DELETE FROM portfolio_recommendations pr
        USING (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY run_id
                       ORDER BY created_at DESC, id DESC
                   ) AS duplicate_rank
            FROM portfolio_recommendations
            WHERE run_id IS NOT NULL
        ) ranked
        WHERE pr.id = ranked.id
          AND ranked.duplicate_rank > 1
        """
    )

    op.create_unique_constraint(
        "uq_research_reports_run_id",
        "research_reports",
        ["run_id"],
    )
    op.create_unique_constraint(
        "uq_portfolio_recommendations_run_id",
        "portfolio_recommendations",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_portfolio_recommendations_run_id",
        "portfolio_recommendations",
        type_="unique",
    )
    op.drop_constraint("uq_research_reports_run_id", "research_reports", type_="unique")
