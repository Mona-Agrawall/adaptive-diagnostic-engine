"""Application factory and lifecycle."""

from __future__ import annotations

import logging
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo.errors import PyMongoError

from . import __version__
from .api import router
from .assessment import AssessmentService
from .config import Settings, get_settings
from .db import Database
from .errors import NotFoundError, install_error_handlers
from .question_bank import load_bank, seed_questions
from .rate_limit import RateLimiter
from .study_plan import GroqStudyPlanProvider, StudyPlanProvider

logger = logging.getLogger("app")

CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def create_app(
    settings: Settings | None = None,
    *,
    ai_provider: StudyPlanProvider | None = None,
    use_default_ai_provider: bool = True,
    rng: random.Random | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = Database(settings)
        provider = ai_provider
        if provider is None and use_default_ai_provider and settings.ai_enabled:
            provider = GroqStudyPlanProvider(settings)
        app.state.db = db
        app.state.ai_provider = provider
        app.state.service = AssessmentService(db, settings, rng=rng)
        app.state.create_limiter = RateLimiter(settings.rate_limit_create_per_minute)
        app.state.answer_limiter = RateLimiter(settings.rate_limit_answer_per_minute)
        app.state.study_plan_limiter = RateLimiter(settings.rate_limit_study_plan_per_minute)
        logger.info("AI study plans: %s", "enabled" if provider else "disabled (rule-based fallback only)")
        try:
            db.ensure_indexes()
            if settings.seed_on_startup:
                stats = seed_questions(db.questions, db.topics, load_bank())
                logger.info("Question bank seeded: %s", stats)
        except PyMongoError as exc:
            logger.error("Database not reachable at startup (%s); will retry on first request", type(exc).__name__)
        try:
            yield
        finally:
            db.close()

    app = FastAPI(
        title="Adaptive Diagnostic Engine",
        version=__version__,
        description="Computerized adaptive GRE diagnostic built on a 2PL item response model.",
        lifespan=lifespan,
    )
    install_error_handlers(app)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if not request.url.path.startswith(DOCS_PATHS):
            response.headers.setdefault("Content-Security-Policy", CSP)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.include_router(router)
    if settings.serve_frontend:
        _mount_frontend(app, settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built single-page app, falling back to index.html for client-side routes."""
    index = dist / "index.html"
    if not index.is_file():
        logger.info("Frontend build not found at %s; serving the API only", dist)
        return
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/") or path == "api":
            raise NotFoundError("Endpoint not found.")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
