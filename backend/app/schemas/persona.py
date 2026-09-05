from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PersonaCreateRequest(BaseModel):
    patient_id: UUID
    name: str
    relation: str | None = None
    # sample_photo is UploadFile, not part of Pydantic model


class PersonaResponse(BaseModel):
    id: UUID
    name: str
    relation: str | None
    sample_photo_url: str | None
    voice_sample_url: str | None
    voice_cloned: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PersonaVoiceUploadRequest(BaseModel):
    # voice_sample is UploadFile, not part of Pydantic model
    pass


class PersonaListResponse(BaseModel):
    personas: list[PersonaResponse]
