"""
Procurement Platform — Main Application

Assembles all routes under /api/v1 prefix.
Run with: uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Logging MUST be set up before any import that logs
from app.core.logger import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

from app.api.v1.routes.auth_routes import auth_router
from app.api.v1.routes.supplier_routes import supplier_router
from app.api.v1.routes.tender_routes import tender_router
from app.api.v1.routes.user_routes import user_router
from app.core.config import settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.middleware.logger_middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Procurement system API starting",
        extra={"version": settings.APP_VERSION, "environment": settings.ENVIRONMENT},
    )
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Procurement system API shut down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-grade procurement platform for Kenya. "
        "Hybrid rule + ML scoring engine with full explainability, case management, and audit trails."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────────────────────────
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"

app.include_router(auth_router, prefix=PREFIX)
app.include_router(user_router, prefix=PREFIX)
app.include_router(tender_router, prefix=PREFIX)
app.include_router(supplier_router, prefix=PREFIX)


@app.get("/", tags=["Health"])
def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
