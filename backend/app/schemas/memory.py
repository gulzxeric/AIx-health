from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MemoryCreateRequest(BaseModel):
    patient_id: UUID
    raw_text: str
    caregiver_id: UUID
    photo_url: str | None = None


class MemoryResponse(BaseModel):
    id: UUID
    raw_text: str
    entities: dict
    photo_url: str | None
    sync_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemoryUpdateRequest(BaseModel):
    entities: dict | None = None


class MemoryListResponse(BaseModel):
    memories: list[MemoryResponse]
    total: int
