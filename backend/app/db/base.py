from datetime import datetime
from enum import Enum as PyEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def pg_enum(py_enum: type[PyEnum], *, name: str, **kwargs: Any) -> Enum:
    """SQLAlchemy Enum column wired to send `.value` (not `.name`) to Postgres.

    The PG enum types in the initial migration were created with our StrEnum
    `.value`s (lowercase: 'research', 'moderate', …). Without `values_callable`
    SQLAlchemy defaults to sending `.name` (uppercase), which Postgres rejects.
    Every enum column in the ORM routes through this helper to stay consistent.
    """
    return Enum(
        py_enum,
        name=name,
        values_callable=lambda e: [member.value for member in e],
        **kwargs,
    )


class UUIDPKMixin:
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
