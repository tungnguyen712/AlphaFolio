"""Shared FastAPI dependencies for the API layer.

Annotated aliases so routers don't have to repeat `Depends(...)` boilerplate.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.db.session import get_db
from app.models.db import User

DBSessionDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
