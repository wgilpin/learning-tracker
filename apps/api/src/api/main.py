from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from documentlm_core.config import settings
from documentlm_core.db.session import AsyncSessionFactory, engine
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

_LEVEL_COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[1;31m",# bold red
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{_RESET}" if color else record.levelname
        return super().format(record)


_handler = logging.StreamHandler()
_handler.setFormatter(
    _ColorFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
)
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    handlers=[_handler],
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

    # Auth guard: redirect unauthenticated requests to /login
    _PUBLIC_PATHS = {"/login", "/register", "/logout"}

    @app.middleware("http")
    async def require_auth(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        if path not in _PUBLIC_PATHS and not path.startswith("/static"):
            if not request.session.get("user_id"):
                from starlette.responses import RedirectResponse
                return RedirectResponse(url="/login", status_code=302)
        return await call_next(request)

    # SessionMiddleware must be added LAST so it is outermost and runs before
    # any middleware that accesses request.session.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        max_age=604800,
        https_only=not settings.debug,
        same_site="lax",
    )

    # Static files
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    from api.routers import auth, bibliography, chapters, sources, syllabus, topics

    app.include_router(auth.router)
    app.include_router(topics.router)
    app.include_router(syllabus.router)
    app.include_router(chapters.router)
    app.include_router(sources.router)
    app.include_router(bibliography.router)

    return app


app = create_app()
