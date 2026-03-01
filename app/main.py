from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers.auth_router import auth_router
from app.api.v1.routers.tender_router import tender_router
from app.api.v1.routers.supplier_router import supplier_router

app = FastAPI(
    title="Uwazi API",
    version="0.1.0",
    description="API for Uwazi application",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "https://uwazi-frontend-two.vercel.app",
]  # Add frontend domains here

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# API Prefixes
BASE_URL_PREFIX = "/api/v1"
# Include API Routes
app.include_router(
    auth_router,
    prefix=f"{BASE_URL_PREFIX}",
    tags=["Users - Authentication"],
)
app.include_router(
    tender_router,
    prefix=f"{BASE_URL_PREFIX}/tenders",
    tags=["Tenders"],
)
app.include_router(
    supplier_router,
    prefix=f"{BASE_URL_PREFIX}/suppliers",
    tags=["Suppliers"],
)
