"""Clerk JWT verification + FastAPI current-user dependency.

Verifies session JWTs minted by Clerk using their published JWKS. The JWKS
itself is fetched once and cached for an hour — Clerk rotates keys but slowly,
and a stale cache just means the next rotation triggers a 401 once and refetch.

User rows are lazy-created: the first authenticated request from a given
clerk_id inserts a `users` row with the email claim. No webhook needed.

`DEV_BYPASS_AUTH=true` short-circuits to a single dev user for local
curl-testing without hitting Clerk. Logs a startup warning so this never
gets quietly enabled in prod.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

from app.config import get_settings
from app.db.session import SessionLocal
from app.models.db import User

logger = logging.getLogger(__name__)

_JWKS_CACHE_TTL_SECONDS = 60 * 60
_DEV_USER_CLERK_ID = "dev-user"
_DEV_USER_EMAIL = "dev@alphafolio.local"

# In-memory JWKS cache. Single-process — fine for a Docker-Compose backend.
# Re-fetches on TTL expiry or on `kid` miss (rotation).
_jwks_cache: dict[str, Any] = {"keys": {}, "fetched_at": 0.0}


# ---------------------------------------------------------------------------
# JWKS + JWT verification
# ---------------------------------------------------------------------------


async def _fetch_jwks(force: bool = False) -> dict[str, Any]:
    """Return a {kid: PyJWK} mapping for Clerk's signing keys.

    `force=True` bypasses the TTL — used when verification fails because of a
    `kid` we've never seen (likely a key rotation).
    """
    settings = get_settings()
    if not settings.clerk_jwks_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_JWKS_URL is not configured",
        )

    now = time.monotonic()
    if (
        not force
        and _jwks_cache["keys"]
        and (now - _jwks_cache["fetched_at"]) < _JWKS_CACHE_TTL_SECONDS
    ):
        return _jwks_cache["keys"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(settings.clerk_jwks_url)
        resp.raise_for_status()
        jwk_set = resp.json()

    keys: dict[str, Any] = {}
    for key in jwk_set.get("keys", []):
        kid = key.get("kid")
        if not kid:
            continue
        keys[kid] = jwt.PyJWK(key)

    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = now
    return keys


async def _verify_jwt(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        unverified = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="malformed token"
        ) from exc

    kid = unverified.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no kid"
        )

    keys = await _fetch_jwks()
    pyjwk = keys.get(kid)
    if pyjwk is None:
        # Rotation: refetch JWKS once before giving up.
        keys = await _fetch_jwks(force=True)
        pyjwk = keys.get(kid)
    if pyjwk is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"unknown signing key kid={kid}",
        )

    try:
        # Clerk uses the issuer URL as `iss`. We do not validate `aud` because
        # Clerk's session tokens don't carry one by default.
        claims = jwt.decode(
            token,
            pyjwk.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer or None,
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token expired"
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {exc}"
        ) from exc

    return claims


# ---------------------------------------------------------------------------
# User lazy-create
# ---------------------------------------------------------------------------


async def _get_or_create_user(clerk_id: str, email: str) -> User:
    """Return the User row for this clerk_id, inserting it if absent.

    Concurrent first-request races are handled by the unique index on
    users.clerk_id — the second concurrent insert raises IntegrityError, we
    rollback and re-select.
    """
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.clerk_id == clerk_id))
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        try:
            user = User(clerk_id=clerk_id, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
        except Exception:  # noqa: BLE001 — race with another request creating same clerk_id
            await session.rollback()
            raced = (
                await session.execute(select(User).where(User.clerk_id == clerk_id))
            ).scalar_one_or_none()
            if raced is None:
                raise
            return raced


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_current_user(request: Request) -> User:
    """Resolve the authenticated user for this request.

    Reads `Authorization: Bearer <jwt>` from the request, verifies the JWT
    against Clerk's JWKS, and returns the matching `users` row (lazy-created
    on first sight).

    `DEV_BYPASS_AUTH=true` skips the JWT path entirely and returns a single
    dev user. Useful for local curl-testing without minting tokens.
    """
    settings = get_settings()
    if settings.dev_bypass_auth:
        return await _get_or_create_user(_DEV_USER_CLERK_ID, _DEV_USER_EMAIL)

    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Authorization: Bearer <token>",
        )
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="empty bearer token"
        )

    claims = await _verify_jwt(token)
    clerk_id = claims.get("sub")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no sub claim"
        )
    email = claims.get("email") or f"{clerk_id}@unknown.invalid"

    return await _get_or_create_user(clerk_id, email)


def require_auth_configured_or_dev_bypass() -> None:
    """Startup check: refuse to run if neither real Clerk nor dev bypass is set.

    Catches the embarrassing failure mode where the API silently 500s on
    every request because clerk_jwks_url is empty.
    """
    settings = get_settings()
    if settings.dev_bypass_auth:
        logger.warning(
            "DEV_BYPASS_AUTH is enabled — every request resolves to a single "
            "shared dev user. Do NOT enable this in production."
        )
        return
    if not settings.clerk_jwks_url or not settings.clerk_issuer:
        raise RuntimeError(
            "Clerk auth is not configured. Set CLERK_JWKS_URL + CLERK_ISSUER "
            "(or DEV_BYPASS_AUTH=true for local development)."
        )


# Annotated alias used across api/* routers.
CurrentUser = User
"""Type alias for clarity at call sites: `current_user: CurrentUser = Depends(get_current_user)`."""

CurrentUserDep = Depends(get_current_user)
"""Reusable dependency object, so routers don't have to import Depends + get_current_user."""
