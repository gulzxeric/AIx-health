from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.minio_client import ensure_buckets


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create database tables and MinIO buckets
    from app.database import engine, Base
    import app.models  # noqa: F401 — register all models on Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await ensure_buckets()

    yield

    # Shutdown: dispose engine
    await engine.dispose()


app = FastAPI(
    title="AIX Health API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware (allow all origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount v1 routes
app.include_router(v1_router, prefix="/api/v1")


# Root health check
@app.get("/health")
async def root_health():
    return {"status": "ok", "version": "0.1.0"}
