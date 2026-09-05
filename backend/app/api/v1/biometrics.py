import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.biometric_raw import BiometricRaw
from app.models.chat_session import ChatSession
from app.schemas.biometrics import (
    AcousticDataRequest,
    BiometricsResponse,
    GazeDataRequest,
    SessionSummaryRequest,
)

router = APIRouter(prefix="/biometrics", tags=["埋点上报"])


@router.post("/gaze", response_model=BiometricsResponse)
async def report_gaze(
    data: GazeDataRequest,
    db: AsyncSession = Depends(get_db),
):
    """上报眼动数据

    将原始眼动数据存储到 biometrics_raw 表。
    """
    patient_id = uuid.uuid4()  # TODO: 从设备 token 提取真实 patient_id

    session_uuid: uuid.UUID | None = None
    if data.session_id:
        try:
            session_uuid = uuid.UUID(data.session_id)
        except ValueError:
            session_uuid = None

    record = BiometricRaw(
        patient_id=patient_id,
        session_id=session_uuid,
        data_type="gaze",
        payload={
            "gaze_events": [e.model_dump() for e in data.gaze_events],
            "avg_fixation_ms": data.avg_fixation_ms,
            "avg_saccade_ms": data.avg_saccade_ms,
        },
    )
    db.add(record)
    await db.commit()

    return BiometricsResponse(recorded_at=datetime.now(timezone.utc))


@router.post("/acoustic", response_model=BiometricsResponse)
async def report_acoustic(
    data: AcousticDataRequest,
    db: AsyncSession = Depends(get_db),
):
    """上报声学数据

    将原始声学数据存储到 biometrics_raw 表。
    """
    patient_id = uuid.uuid4()  # TODO: 从设备 token 提取真实 patient_id

    session_uuid: uuid.UUID | None = None
    if data.session_id:
        try:
            session_uuid = uuid.UUID(data.session_id)
        except ValueError:
            session_uuid = None

    record = BiometricRaw(
        patient_id=patient_id,
        session_id=session_uuid,
        data_type="acoustic",
        payload={
            "acoustic_events": [e.model_dump() for e in data.acoustic_events],
            "avg_pause_ms": data.avg_pause_ms,
            "voice_duration_ms": data.voice_duration_ms,
        },
    )
    db.add(record)
    await db.commit()

    return BiometricsResponse(recorded_at=datetime.now(timezone.utc))


@router.post("/session", response_model=BiometricsResponse)
async def report_session(
    data: SessionSummaryRequest,
    db: AsyncSession = Depends(get_db),
):
    """上报会话级汇总

    更新 chat_sessions 表的 gaze_data 和 acoustic_data 字段。
    """
    try:
        session_uuid = uuid.UUID(data.session_id)
    except ValueError:
        return BiometricsResponse(
            success=False,
            recorded_at=datetime.now(timezone.utc),
        )

    from sqlalchemy import select

    stmt = select(ChatSession).where(ChatSession.id == session_uuid)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        return BiometricsResponse(
            success=False,
            recorded_at=datetime.now(timezone.utc),
        )

    session.gaze_data = data.gaze_metrics
    session.acoustic_data = data.acoustic_metrics
    await db.commit()

    return BiometricsResponse(recorded_at=datetime.now(timezone.utc))
