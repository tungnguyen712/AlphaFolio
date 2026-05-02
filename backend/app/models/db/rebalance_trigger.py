from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin, pg_enum
from app.models.db.enums import RebalanceTriggerKind


class RebalanceTrigger(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "rebalance_triggers"

    # Direct FK to the owner — populated on creation; no join needed to find the user.
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable: price-watch and research-report triggers are not tied to a portfolio.
    portfolio_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    kind: Mapped[RebalanceTriggerKind] = mapped_column(
        pg_enum(RebalanceTriggerKind, name="rebalance_trigger_kind_enum"), nullable=False
    )
    condition_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
