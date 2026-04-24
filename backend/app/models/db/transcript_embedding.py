from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin

EMBEDDING_DIM = 1536


class TranscriptEmbedding(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "transcript_embeddings"

    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    quarter: Mapped[str] = mapped_column(String(16), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
