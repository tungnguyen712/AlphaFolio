"""Telegram Bot API webhook handler.

Receives incoming updates from Telegram (via POST), verifies the shared
secret, and processes ``/start {token}`` commands to link a user's Telegram
chat to their AlphaFolio account.

Registration flow:
  1. User visits ``GET /users/me/telegram-token`` to get a deep-link URL.
  2. User opens the link: ``t.me/{BOT}?start={token}``.
  3. Telegram sends ``POST /telegram/webhook`` with the bot's received message.
  4. This handler verifies the HMAC token, finds the user by clerk_id, stores
     ``telegram_chat_id``, and replies with a confirmation message.

Security:
  - ``X-Telegram-Bot-Api-Secret-Token`` header must match ``TELEGRAM_WEBHOOK_SECRET``.
  - HMAC token is validated; expired tokens (> 10 minutes) are rejected.
  - Telegram always gets HTTP 200 to prevent retry storms — errors are logged
    but not surfaced as 4xx to avoid Telegram disabling the webhook.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time

from fastapi import APIRouter, Header, Request, Response
from sqlalchemy import select

from app.config import get_settings
from app.db.session import get_db
from app.models.db import User
from app.services.telegram import send_message as tg_send

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])

_TOKEN_TTL = 600  # must match users.py


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    """Receive and process a Telegram Bot API update.

    Always returns HTTP 200 so Telegram does not retry — real errors are
    logged, not propagated.
    """
    settings = get_settings()

    # Verify shared secret
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        logger.warning("telegram_webhook: invalid secret token — ignoring update")
        return Response(content='{"ok":false}', media_type="application/json", status_code=200)

    try:
        update: dict = await request.json()
    except Exception:
        return Response(content='{"ok":true}', media_type="application/json")

    message = update.get("message", {})
    text: str = message.get("text", "")
    from_data: dict = message.get("from", {})
    chat_id: int | None = message.get("chat", {}).get("id")

    if not text.startswith("/start ") or not chat_id:
        # Not a registration command — silently accept
        return Response(content='{"ok":true}', media_type="application/json")

    token_str = text[len("/start "):].strip()
    clerk_id, success = await _handle_registration(token_str, str(chat_id), settings)

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
    settings,
) -> tuple[str | None, bool]:
    """Validate HMAC token and store telegram_chat_id on the user.

    Returns (clerk_id, success).
    """
    # Decode base64url token
    try:
        padding = 4 - len(token_str) % 4
        token_decoded = base64.urlsafe_b64decode(token_str + "=" * (padding % 4)).decode()
    except Exception:
        logger.warning("telegram_webhook: failed to decode token")
        return None, False

    parts = token_decoded.split(":")
    if len(parts) != 3:
        logger.warning("telegram_webhook: malformed token (parts=%d)", len(parts))
        return None, False

    clerk_id, expiry_str, sig = parts

    # Expiry check
    try:
        expiry = int(expiry_str)
    except ValueError:
        return None, False

    if int(time.time()) > expiry:
        logger.info("telegram_webhook: expired token for clerk_id=%s", clerk_id)
        return clerk_id, False

    # HMAC verification — constant-time compare
    payload = f"{clerk_id}:{expiry_str}"
    expected = hmac.new(
        settings.telegram_webhook_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, sig):
        logger.warning("telegram_webhook: HMAC mismatch for clerk_id=%s", clerk_id)
        return clerk_id, False

    # Update DB
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
