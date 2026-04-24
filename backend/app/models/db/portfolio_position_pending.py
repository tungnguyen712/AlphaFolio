from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin, pg_enum
from app.models.db.enums import PendingPositionStatus


class PortfolioPositionPending(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "portfolio_position_pending"

    portfolio_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    target_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    source_report_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("research_reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[PendingPositionStatus] = mapped_column(
        pg_enum(PendingPositionStatus, name="pending_position_status_enum"),
        nullable=False,
        default=PendingPositionStatus.PENDING,
        index=True,
    )
