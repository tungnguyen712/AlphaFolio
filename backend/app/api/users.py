"""User profile endpoints.

GET  /users/me                 → current user profile + Telegram connection status
PATCH /users/me                → update telegram_chat_id (pass null to disconnect)
GET  /users/me/telegram-token  → short-lived token for Telegram deep-link registration
"""
from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, DBSessionDep
from app.config import get_settings
from app.services.redis_client import get_redis

router = APIRouter(prefix="/users", tags=["users"])

_TOKEN_TTL = 600  # 10 minutes
_REDIS_PREFIX = "tg_link:"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UserOut(BaseModel):
    id: str
    clerk_id: str
    email: str | None = None
    telegram_chat_id: str | None = None
    telegram_connected: bool

    model_config = {"from_attributes": True}


class UserPatch(BaseModel):
    telegram_chat_id: str | None = Field(default=..., description="Pass null to disconnect")


class TelegramTokenOut(BaseModel):
    token: str
    bot_username: str
    deep_link: str
    expires_in: int  # seconds


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUserDep) -> Any:
    return {
        "id": str(user.id),
        "clerk_id": user.clerk_id,
        "email": getattr(user, "email", None),
        "telegram_chat_id": user.telegram_chat_id,
        "telegram_connected": bool(user.telegram_chat_id),
    }


@router.patch("/me", response_model=UserOut)
async def patch_me(
    body: UserPatch,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> Any:
    user.telegram_chat_id = body.telegram_chat_id
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "id": str(user.id),
        "clerk_id": user.clerk_id,
        "email": getattr(user, "email", None),
        "telegram_chat_id": user.telegram_chat_id,
        "telegram_connected": bool(user.telegram_chat_id),
    }


@router.get("/me/telegram-token", response_model=TelegramTokenOut)
async def get_telegram_token(user: CurrentUserDep) -> TelegramTokenOut:
    """Return a short-lived token stored in Redis for Telegram deep-link registration.

    Generates a 24-char random token (≤64 chars, within Telegram's ?start= limit).
    Stored in Redis as ``tg_link:{token}`` → ``clerk_id`` with 10-minute TTL.
    """
    settings = get_settings()
    token = secrets.token_urlsafe(16)  # 22 chars, URL-safe, no colons
    redis = get_redis()
    await redis.setex(f"{_REDIS_PREFIX}{token}", _TOKEN_TTL, user.clerk_id)

    deep_link = f"https://t.me/{settings.telegram_bot_username}?start={token}"
    return TelegramTokenOut(
        token=token,
        bot_username=settings.telegram_bot_username,
        deep_link=deep_link,
        expires_in=_TOKEN_TTL,
    )
