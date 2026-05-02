"""Telegram Bot API client.

Thin async wrapper around the sendMessage endpoint. Designed to be a
no-op when ``TELEGRAM_BOT_TOKEN`` is not configured so the app runs
without Telegram in development.

Usage::

    from app.services.telegram import send_message
    ok = await send_message(chat_id="123456789", text="AAPL hit $185")
"""
from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_BASE = "https://api.telegram.org"
_TIMEOUT = httpx.Timeout(10.0)


async def send_message(chat_id: str | int, text: str) -> bool:
    """Send a text message to a Telegram chat.

    Returns True on success, False if the token is not configured or the
    request fails. Never raises — callers should not crash on notification
    failure.

    Args:
        chat_id: Telegram chat ID (integer or string).
        text: Message body; HTML parse_mode is used so <b>, <i>, <code>
              tags work. Keep messages under 4096 chars (Telegram limit).
    """
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        logger.debug("telegram.send_message: TELEGRAM_BOT_TOKEN not set, skipping")
        return False

    url = f"{_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            if not resp.is_success:
                logger.warning(
                    "telegram.send_message: HTTP %d — %s", resp.status_code, resp.text[:200]
                )
                return False
        return True
    except Exception as exc:
        logger.warning("telegram.send_message: failed — %s", exc)
        return False


async def set_webhook(webhook_url: str) -> bool:
    """Register the Bot API webhook URL.  Called once at deploy time.

    The webhook secret (``TELEGRAM_WEBHOOK_SECRET``) is sent so Telegram
    includes it in every incoming update as ``X-Telegram-Bot-Api-Secret-Token``,
    which ``/telegram/webhook`` verifies before processing.
    """
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        return False

    url = f"{_BASE}/bot{token}/setWebhook"
    payload = {
        "url": webhook_url,
        "secret_token": settings.telegram_webhook_secret,
        "allowed_updates": ["message"],
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            ok = resp.is_success and resp.json().get("ok", False)
            if not ok:
                logger.warning("telegram.set_webhook failed: %s", resp.text[:300])
            return bool(ok)
    except Exception as exc:
        logger.warning("telegram.set_webhook error: %s", exc)
        return False
