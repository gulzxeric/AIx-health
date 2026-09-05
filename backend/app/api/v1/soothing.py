from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.soothing_event import SoothingEvent
from app.schemas.soothing import (
    SoothingAutoTriggerResponse,
    SoothingConfig,
    SoothingEventRequest,
    SoothingEventResponse,
)
from app.core.soothing_service import (
    auto_trigger_soothing,
    check_sunset_window,
    detect_negative_signal,
    get_soothing_config as get_soothing_cfg,
    update_soothing_config as update_soothing_cfg,
)

router = APIRouter(prefix="/soothing", tags=["舒缓模式"])


@router.post("/event", response_model=SoothingEventResponse)
async def report_soothing_event(
    req: SoothingEventRequest,
    db: AsyncSession = Depends(get_db),
):
    """上报舒缓事件

    1. 写入 soothing_events 表
    2. 如果事件类型需要通知家属 => 触发推送（占位）
    """
    event = SoothingEvent(
        patient_id=req.patient_id,
        event_type=req.event_type,
        session_id=req.session_id,
        metadata=req.metadata or {},
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    recorded_at = event.created_at

    # 占位：如果需要通知家属，触发推送
    # TODO: 集成推送通知

    return SoothingEventResponse(
        success=True,
        event_id=str(event.id),
        recorded_at=recorded_at,
    )


@router.get("/config/{patient_id}", response_model=SoothingConfig)
async def get_soothing_config(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取患者舒缓配置"""
    config = await get_soothing_cfg(patient_id, db)
    return SoothingConfig(
        patient_id=config["patient_id"],
        sunset_start=config["sunset_start"],
        sunset_end=config["sunset_end"],
        auto_soothing=config["auto_soothing"],
    )


@router.put("/config/{patient_id}", response_model=SoothingConfig)
async def update_soothing_config(
    patient_id: UUID,
    req: SoothingConfig,
    db: AsyncSession = Depends(get_db),
):
    """更新舒缓配置"""
    try:
        config = await update_soothing_cfg(
            patient_id,
            {
                "sunset_start": req.sunset_start,
                "sunset_end": req.sunset_end,
                "auto_soothing": req.auto_soothing,
            },
            db,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return SoothingConfig(
        patient_id=config["patient_id"],
        sunset_start=config["sunset_start"],
        sunset_end=config["sunset_end"],
        auto_soothing=config["auto_soothing"],
    )


@router.get("/sunset-window/{patient_id}")
async def get_sunset_window(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """检查当前是否在日落时间窗口内"""
    return await check_sunset_window(patient_id, db)


@router.get("/negative-signal/{patient_id}")
async def get_negative_signal(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """检测负面信号"""
    return await detect_negative_signal(patient_id, db)


@router.post("/auto-trigger/{patient_id}", response_model=SoothingAutoTriggerResponse)
async def trigger_soothing(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """触发自动舒缓模式检查

    条件：17:00-19:30 + 负面信号检测阳性
    """
    return await auto_trigger_soothing(patient_id, db)
