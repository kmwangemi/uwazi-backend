from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers.auth_router import auth_router

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


# API Prefixes
BASE_URL_PREFIX = "/api/v1"
# Include API Routes
app.include_router(
    auth_router,
    prefix=f"{BASE_URL_PREFIX}",
    tags=["Users - Authentication"],
)
