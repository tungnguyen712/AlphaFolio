from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin, pg_enum
from app.models.db.enums import AssetClass, RiskProfile


class Portfolio(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "portfolios"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    risk_profile: Mapped[RiskProfile] = mapped_column(
        pg_enum(RiskProfile, name="risk_profile_enum"), nullable=False
    )


class PortfolioHolding(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "portfolio_holdings"

    portfolio_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    asset_class: Mapped[AssetClass] = mapped_column(
        pg_enum(AssetClass, name="asset_class_enum"), nullable=False
    )
