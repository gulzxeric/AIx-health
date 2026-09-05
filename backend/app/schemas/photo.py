from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PhotoResponse(BaseModel):
    id: UUID
    object_url: str
    thumbnail_url: str | None
    persona_name: str | None
    persona_relation: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
