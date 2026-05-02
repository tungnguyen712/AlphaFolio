"""User profile endpoints.

GET  /users/me                 → current user profile + Telegram connection status
PATCH /users/me                → update telegram_chat_id (pass null to disconnect)
GET  /users/me/telegram-token  → short-lived HMAC token for Telegram deep-link registration
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, DBSessionDep
from app.config import get_settings

router = APIRouter(prefix="/users", tags=["users"])

_TOKEN_TTL = 600  # 10 minutes


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
    """Return a short-lived HMAC token the user can use to link Telegram.

    The token encodes ``{clerk_id}:{expiry_unix}`` and is signed with
    ``TELEGRAM_WEBHOOK_SECRET`` so the webhook can verify it without a DB
    round-trip.  The consumer opens::

        https://t.me/{BOT_USERNAME}?start={token}

    The Telegram bot receives ``/start {token}`` and calls PATCH /users/me
    via our webhook handler after validating the HMAC.
    """
    settings = get_settings()
    expiry = int(time.time()) + _TOKEN_TTL
    payload = f"{user.clerk_id}:{expiry}"
    sig = hmac.new(
        settings.telegram_webhook_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    token = f"{payload}:{sig}"

    deep_link = f"https://t.me/{settings.telegram_bot_username}?start={token}"
    return TelegramTokenOut(
        token=token,
        bot_username=settings.telegram_bot_username,
        deep_link=deep_link,
        expires_in=_TOKEN_TTL,
    )
