"""患者配置路由"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.asset_pack import AssetPack
from app.models.patient_config import PatientConfig
from app.schemas.config import PatientConfigResponse, UpdateConfigRequest

router = APIRouter(prefix="/patients", tags=["患者配置"])


@router.get("/config")
async def get_patient_config(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """患者端拉取配置 + 资产包

    1. 查 patient_configs
    2. 查 asset_packs
    3. 返回 { config, asset_pack }
    """
    # 1. 查配置
    result = await db.execute(
        select(PatientConfig).where(PatientConfig.patient_id == patient_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该患者的配置，请先完成初始化配置",
        )

    # 2. 查资产包
    result = await db.execute(
        select(AssetPack)
        .where(
            AssetPack.patient_id == patient_id,
            AssetPack.status == "ready",
        )
        .order_by(AssetPack.created_at.desc())
        .limit(1)
    )
    asset_pack = result.scalar_one_or_none()

    config_data = PatientConfigResponse(
        patient_id=config.patient_id,
        era=config.era,
        region=config.region,
        language=config.language,
        timezone=config.timezone,
        persona_name=config.persona_name,
        privacy_consent=config.privacy_consent,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )

    asset_pack_data = None
    if asset_pack:
        asset_pack_data = {
            "id": asset_pack.id,
            "era": asset_pack.era,
            "region_key": asset_pack.region_key,
            "status": asset_pack.status,
            "photo_urls": asset_pack.photo_urls,
            "topic_library": asset_pack.topic_library,
            "prompt_anchors": asset_pack.prompt_anchors,
        }

    return {
        "config": config_data.model_dump(),
        "asset_pack": asset_pack_data,
    }


@router.post("/config")
async def update_patient_config(
    patient_id: UUID,
    req: UpdateConfigRequest,
    db: AsyncSession = Depends(get_db),
):
    """管理员更新患者配置"""
    result = await db.execute(
        select(PatientConfig).where(PatientConfig.patient_id == patient_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该患者的配置",
        )

    # 更新非空字段
    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)

    return PatientConfigResponse(
        patient_id=config.patient_id,
        era=config.era,
        region=config.region,
        language=config.language,
        timezone=config.timezone,
        persona_name=config.persona_name,
        privacy_consent=config.privacy_consent,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )
