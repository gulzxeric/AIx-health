from fastapi import APIRouter

from app.api.v1.health import router as health_router

router = APIRouter()

# Mount all v1 route modules
router.include_router(health_router)
