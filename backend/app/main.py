"""Main FastAPI application for Clover."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.endpoints import router as api_router, memory_service, db_service, optimization_engine
from .core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure initial sample history if clean start
    existing = memory_service.get_history(limit=1)
    if not existing:
        # Pre-seed one explainable initial recommendation to provide immediate context
        optimization_engine.run_optimization(workload_id="CHECKOUT")
    yield


app = FastAPI(
    title="Clover API",
    description="Carbon-Aware Database Optimization System using YugabyteDB, Meko Memory, and Gemini AI",
    version=settings.app_version,
    lifespan=lifespan,
)

# Enable CORS for frontend Vite development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST routes
app.include_router(api_router, prefix="/api")


@app.get("/")
def read_root():
    return {
        "system": "Clover",
        "description": "Carbon-Aware Database Optimization Engine",
        "version": settings.app_version,
        "operating_mode": settings.operating_mode.value,
        "documentation": "/docs",
        "health": "/api/health",
    }
