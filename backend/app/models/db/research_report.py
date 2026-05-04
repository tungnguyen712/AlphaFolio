from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin, pg_enum
from app.models.db.enums import ResearchSignal


class ResearchReport(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_reports"
    __table_args__ = (UniqueConstraint("run_id", name="uq_research_reports_run_id"),)

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    portfolio_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    signal: Mapped[ResearchSignal] = mapped_column(
        pg_enum(ResearchSignal, name="research_signal_enum"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    report_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
