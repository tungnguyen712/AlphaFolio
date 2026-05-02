"""Telegram Bot API webhook handler.

Receives incoming updates from Telegram (via POST), verifies the shared
secret, and processes ``/start {token}`` commands to link a user's Telegram
chat to their AlphaFolio account.

Registration flow:
  1. User visits ``GET /users/me/telegram-token`` to get a deep-link URL.
  2. User opens the link: ``t.me/{BOT}?start={token}`` (token is a short Redis key).
  3. Telegram sends ``POST /telegram/webhook`` with the bot's received message.
  4. This handler looks up clerk_id from Redis, finds the user, stores
     ``telegram_chat_id``, and replies with a confirmation message.

Security:
  - ``X-Telegram-Bot-Api-Secret-Token`` header must match ``TELEGRAM_WEBHOOK_SECRET``.
  - Redis key has a 10-minute TTL and is deleted after first use.
  - Telegram always gets HTTP 200 to prevent retry storms.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, Request, Response
from sqlalchemy import select

from app.db.session import get_db
from app.models.db import User
from app.services.redis_client import get_redis
from app.services.telegram import send_message as tg_send

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])

_REDIS_PREFIX = "tg_link:"


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    """Receive and process a Telegram Bot API update."""
    from app.config import get_settings
    settings = get_settings()

    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        logger.warning("telegram_webhook: invalid secret token — ignoring update")
        return Response(content='{"ok":false}', media_type="application/json", status_code=200)

    try:
        update: dict = await request.json()
    except Exception:
        return Response(content='{"ok":true}', media_type="application/json")

    message = update.get("message", {})
    text: str = message.get("text", "")
    chat_id: int | None = message.get("chat", {}).get("id")

    if not text.startswith("/start ") or not chat_id:
        return Response(content='{"ok":true}', media_type="application/json")

    token_str = text[len("/start "):].strip()
    clerk_id, success = await _handle_registration(token_str, str(chat_id))

    if success:
        await tg_send(
            chat_id,
            "✅ <b>AlphaFolio connected!</b>\n"
            "You'll receive price alerts and watch reminders here.",
        )
        logger.info("telegram_webhook: linked chat_id=%s to clerk_id=%s", chat_id, clerk_id)
    else:
        await tg_send(
            chat_id,
            "❌ <b>Link failed.</b> The registration link may have expired.\n"
            "Please generate a new link from AlphaFolio Settings.",
        )

    return Response(content='{"ok":true}', media_type="application/json")


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


async def _handle_registration(
    token_str: str,
    chat_id: str,
) -> tuple[str | None, bool]:
    """Look up clerk_id from Redis, store telegram_chat_id on the user."""
    redis = get_redis()
    redis_key = f"{_REDIS_PREFIX}{token_str}"
    clerk_id: str | None = await redis.get(redis_key)

    if not clerk_id:
        logger.warning("telegram_webhook: unknown or expired token")
        return None, False

    # Delete token immediately (one-time use)
    await redis.delete(redis_key)

    async for db in get_db():
        user = (
            await db.execute(select(User).where(User.clerk_id == clerk_id))
        ).scalar_one_or_none()
        if user is None:
            logger.warning("telegram_webhook: unknown clerk_id=%s", clerk_id)
            return clerk_id, False
        user.telegram_chat_id = chat_id
        db.add(user)
        await db.commit()
        return clerk_id, True

    return clerk_id, False

