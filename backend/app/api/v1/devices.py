from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.patient import Patient
from app.schemas.device import DeviceStatusResponse, HeartbeatResponse

router = APIRouter(prefix="/devices", tags=["设备"])

# 心跳超时阈值（秒）
HEARTBEAT_TIMEOUT_SECONDS = 30


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """患者端心跳

    更新 patients.updated_at。
    """
    stmt = select(Patient).where(Patient.id == patient_id)
    result = await db.execute(stmt)
    patient = result.scalar_one_or_none()

    if patient is None:
        return HeartbeatResponse(
            status="patient_not_found",
            server_time=datetime.now(timezone.utc),
        )

    now = datetime.now(timezone.utc)
    patient.updated_at = now
    await db.commit()

    return HeartbeatResponse(
        status="ok",
        server_time=now,
    )


@router.get("/status", response_model=DeviceStatusResponse)
async def device_status(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取患者端在线状态

    根据 updated_at 判断是否在线（30s 内为在线）。
    """
    stmt = select(Patient).where(Patient.id == patient_id)
    result = await db.execute(stmt)
    patient = result.scalar_one_or_none()

    if patient is None:
        return DeviceStatusResponse(
            online=False,
            current_state="unknown",
            last_heartbeat=None,
            version="0.1.0",
        )

    now = datetime.now(timezone.utc)
    last_heartbeat = patient.updated_at
    elapsed = (now - last_heartbeat).total_seconds()
    online = elapsed < HEARTBEAT_TIMEOUT_SECONDS

    return DeviceStatusResponse(
        online=online,
        current_state="active" if online else "offline",
        last_heartbeat=last_heartbeat,
        version="0.1.0",
    )
