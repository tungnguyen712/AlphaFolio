from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import notifications, portfolios, research, runs, simulation, supply_chain
from app.auth.clerk import require_auth_configured_or_dev_bypass
from app.config import get_settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast if Clerk env isn't configured AND DEV_BYPASS_AUTH isn't set.
    # Logs a warning when bypass is on so it's never silently active in prod.
    require_auth_configured_or_dev_bypass()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AlphaFolio", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(portfolios.router)
    app.include_router(research.router)
    app.include_router(runs.research_runs_router)
    app.include_router(runs.runs_router)
    app.include_router(notifications.router)
    app.include_router(supply_chain.router)
    app.include_router(simulation.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
