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

# from app.api.v1.routes.auth_routes import auth_router
# from app.api.v1.routes.bid_routes import bid_router
# from app.api.v1.routes.entity_routes import entity_router
# from app.api.v1.routes.supplier_routes import supplier_router
# from app.api.v1.routes.tender_routes import tender_router
# from app.api.v1.routes.user_routes import user_router

from app.api.v1.routes.analyze_routes import router as analyze_router
from app.api.v1.routes.auth_routes import router as auth_router
from app.api.v1.routes.benchmark_routes import router as benchmarks_router
from app.api.v1.routes.dashboard_routes import router as dashboard_router
from app.api.v1.routes.ml_routes import collusion_router
from app.api.v1.routes.ml_routes import router as ml_router

# from app.api.v1.routes.scraper import router as scraper_router
from app.api.v1.routes.supplier_routes import router as suppliers_router
from app.api.v1.routes.tender_routes import router as tenders_router
from app.api.v1.routes.whistleblower_routes import router as whistleblower_router
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
        "Real-time detection and prevention of fraudulent practices "
        "in Kenya's public procurement. Powered by AI + ML."
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

app.include_router(
    auth_router, prefix=PREFIX
)  # POST /api/auth/login|register|logout  GET /api/auth/me
app.include_router(
    tenders_router, prefix=PREFIX
)  # GET|POST /api/tenders  + /{id} sub-routes
app.include_router(suppliers_router, prefix=PREFIX)  # GET /api/suppliers + /{id}
app.include_router(
    dashboard_router, prefix=PREFIX
)  # GET /api/dashboard/stats|heatmap|top-risk-suppliers|risk-trend  POST /ai-query
app.include_router(
    whistleblower_router, prefix=PREFIX
)  # POST /api/whistleblower/submit  GET|PATCH /reports
app.include_router(benchmarks_router, prefix=PREFIX)  # GET|POST /api/benchmarks
app.include_router(
    analyze_router, prefix=PREFIX
)  # POST /api/analyze/price-check|specifications  GET /county-risk
# app.include_router(scraper_router)  # POST /api/scraper/run
app.include_router(
    ml_router, prefix=PREFIX
)  # GET /api/ml/status  POST /api/ml/train/*  GET /spending-forecast
app.include_router(
    collusion_router, prefix=PREFIX
)  # GET /api/tenders/{id}/collusion-analysis


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
    return {"status": "ok"}
