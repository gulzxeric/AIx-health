from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SessionStartRequest(BaseModel):
    patient_id: UUID | None = None  # 可从设备 token 提取


class SessionStartResponse(BaseModel):
    session_id: UUID
    started_at: datetime


class ChatMessageRequest(BaseModel):
    session_id: UUID
    asr_text: str
    photo_context: str | None = None
    photo_id: UUID | None = None  # 当前轮播照片（有人物标注时触发照片亲人模式）


class ChatMessageResponse(BaseModel):
    reply_text: str
    reply_audio_url: str | None = None
    persona: str
    voice_source: str


class SessionEndRequest(BaseModel):
    session_id: UUID
    gaze_data: dict | None = None
    acoustic_data: dict | None = None


class SessionEndResponse(BaseModel):
    session_id: UUID
    duration_seconds: float
    status: str
