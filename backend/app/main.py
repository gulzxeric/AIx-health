import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.bindings import router as binding_router
from app.api.v1.consents import router as consent_router
from app.api.v1.patient_config import router as config_router
from app.api.v1.chat import router as chat_router
from app.api.v1.photos import router as photos_router
from app.api.v1.devices import router as devices_router
from app.core.minio_client import ensure_buckets

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create database tables and MinIO buckets
    from app.database import engine, Base
    import app.models  # noqa: F401 — register all models on Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await ensure_buckets()

    # Start scheduler for periodic tasks
    from app.core.scheduler import setup_scheduler
    setup_scheduler(app)
    logger.info("定时调度器已启动")

    yield

    # Shutdown: stop scheduler and dispose engine
    from app.core.scheduler import scheduler
    scheduler.shutdown(wait=False)
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

# Mount all v1 routes
app.include_router(health_router, prefix="/api/v1")
app.include_router(binding_router, prefix="/api/v1")
app.include_router(consent_router, prefix="/api/v1")
app.include_router(config_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(photos_router, prefix="/api/v1")
app.include_router(devices_router, prefix="/api/v1")
app.include_router(push_router, prefix="/api/v1")


# Root health check
@app.get("/health")
async def root_health():
    return {"status": "ok", "version": "0.1.0"}
