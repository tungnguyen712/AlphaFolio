"""Response schemas for notification endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.db.enums import NotificationKind


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    kind: NotificationKind
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime
