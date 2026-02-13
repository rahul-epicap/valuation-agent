import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import Base, engine
from app.routes import dashboard, template, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
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


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Mount frontend static files if the build directory exists (production)
# In Docker: /app/frontend/out, in dev: ../../frontend/out
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "out")
if not os.path.isdir(frontend_dir):
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "out")
frontend_dir = os.path.normpath(frontend_dir)
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
