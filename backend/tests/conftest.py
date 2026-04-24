"""Shared pytest fixtures.

The module-level async engine in `app.db.session` binds connection-pool state
to whichever event loop first uses it. pytest-asyncio's default is a fresh
loop per test, so we dispose the pool after each test — new connections on
the next test's loop work fine.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio

from app.db.session import engine


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_test() -> AsyncIterator[None]:
    yield
    await engine.dispose()
