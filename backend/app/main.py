import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import Base, engine, AsyncSessionLocal
from app.routes import (
    bloomberg,
    dashboard,
    descriptions,
    indices,
    peer_valuation,
    template,
    upload,
    valuation,
)
from app.services.bloomberg_service import BloombergService
from app.services import index_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup; optionally start Bloomberg session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed indices from indices.json
    try:
        async with AsyncSessionLocal() as db:
            await index_service.seed_indices(db)
            logger.info("Indices seeded successfully")
    except Exception:
        logger.warning("Failed to seed indices", exc_info=True)

    # Try to start Bloomberg service (non-fatal if Bloomberg Terminal is not running)
    bbg_service: BloombergService | None = None
    try:
        bbg_service = BloombergService()
        bbg_service.start()
        bloomberg.set_service(bbg_service)
        indices.set_service(bbg_service)
        descriptions.set_service(bbg_service)
        logger.info("Bloomberg service initialized successfully")
    except Exception:
        logger.warning(
            "Bloomberg service unavailable — Bloomberg Terminal may not be running. "
            "The /api/bloomberg/fetch endpoint will return 503."
        )
        bbg_service = None

    yield

    if bbg_service is not None:
        bbg_service.stop()
    await engine.dispose()


app = FastAPI(
    title="Epicenter Valuation Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware — allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(upload.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(template.router, prefix="/api")
app.include_router(bloomberg.router, prefix="/api")
app.include_router(valuation.router, prefix="/api")
app.include_router(indices.router, prefix="/api")
app.include_router(descriptions.router, prefix="/api")
app.include_router(peer_valuation.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Mount frontend static files if the build directory exists (production)
# In Docker: /app/frontend/out, in dev: ../../frontend/out
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "out")
if not os.path.isdir(frontend_dir):
    frontend_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "out"
    )
frontend_dir = os.path.normpath(frontend_dir)
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
