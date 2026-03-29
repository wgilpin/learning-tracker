from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from documentlm_core.db.session import AsyncSessionFactory, engine
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: verify DB connectivity. Shutdown: dispose engine."""
    logger.info("Starting up — verifying DB connection")
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        logger.info("DB connection verified")
    except Exception:
        logger.exception("DB connection failed at startup")
        raise
    yield
    await engine.dispose()
    logger.info("Engine disposed — shutdown complete")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(title="Academic Learning Tracker", lifespan=lifespan)

    # Structured request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "request method=%s path=%s status=%d duration_ms=%.1f",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "unhandled exception method=%s path=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                duration_ms,
            )
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Static files
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    from api.routers import bibliography, chapters, sources, syllabus, topics

    app.include_router(topics.router)
    app.include_router(syllabus.router)
    app.include_router(chapters.router)
    app.include_router(sources.router)
    app.include_router(bibliography.router)

    return app


app = create_app()
