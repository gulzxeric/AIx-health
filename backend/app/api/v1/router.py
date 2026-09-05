from fastapi import APIRouter

from app.api.v1.bindings import router as binding_router
from app.api.v1.chat import router as chat_router
from app.api.v1.consents import router as consent_router
from app.api.v1.devices import router as devices_router
from app.api.v1.health import router as health_router
from app.api.v1.patient_config import router as config_router
from app.api.v1.photos import router as photos_router

router = APIRouter()

# Mount all v1 route modules
router.include_router(health_router)
router.include_router(binding_router)
router.include_router(consent_router)
router.include_router(config_router)
router.include_router(chat_router)
router.include_router(photos_router)
router.include_router(devices_router)