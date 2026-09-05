from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


class PatientConfigResponse(BaseModel):
    patient_id: UUID
    era: str
    region: dict
    language: str
    timezone: str
    persona_name: str
    privacy_consent: dict | None = None
    created_at: datetime
    updated_at: datetime


class UpdateConfigRequest(BaseModel):
    era: str | None = None
    region: dict | None = None
    language: str | None = None
    persona_name: str | None = None
