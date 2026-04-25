"""Auth package — Clerk JWT verification + FastAPI current-user dependency."""
from app.auth.clerk import get_current_user

__all__ = ["get_current_user"]
