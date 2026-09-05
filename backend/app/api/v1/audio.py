import logging
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.asr_service import ASRError, speech_to_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["语音转写"])


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    patient_id: UUID | None = Form(None),
    language: str = Form("zh"),
):
    """音频转文字（家属端语音录记忆 / 患者端语音对话共用）"""
    audio_bytes = await file.read()
    try:
        text = await speech_to_text(audio_bytes, language=language)
    except ASRError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"text": text, "language": language}
