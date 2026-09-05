"""设备绑定路由"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.asset_generator import generate_asset_pack
from app.core.binding_service import (
    create_caregiver,
    find_caregiver_by_phone,
    find_patient_by_code,
    get_binding_count,
)
from app.database import get_db
from app.models.care_binding import CareBinding
from app.models.patient_config import PatientConfig
from app.schemas.binding import (
    CompleteConfigRequest,
    CompleteConfigResponse,
    ScanRequest,
    ScanResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bindings", tags=["绑定"])


@router.post("/scan", response_model=ScanResponse)
async def scan_device_code(
    req: ScanRequest,
    caregiver_name: str | None = None,
    caregiver_phone: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """扫码绑定 — 用 6 位设备码查找患者

    1. 查 patients 表找 device_code
    2. 如果找到，检查 care_bindings 是否有绑定
    3. 无绑定 → 标记该家属为 admin，返回 is_new=true
    4. 已有绑定 → 返回 is_new=false
    5. 没找到 → 返回 404
    """
    # 1. 查找患者
    patient = await find_patient_by_code(db, req.device_code)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该设备码对应的患者，请确认设备码是否正确",
        )

    # 2. 检查该患者是否已有绑定
    existing_bindings_count = await get_binding_count(db, patient.id)

    # 3. 创建或查找家属
    if caregiver_phone and caregiver_name:
        caregiver = await find_caregiver_by_phone(db, caregiver_phone)
        if not caregiver:
            caregiver = await create_caregiver(db, caregiver_name, caregiver_phone)

        # 检查是否已绑定
        result = await db.execute(
            select(CareBinding).where(
                CareBinding.patient_id == patient.id,
                CareBinding.caregiver_id == caregiver.id,
            )
        )
        existing_binding = result.scalar_one_or_none()

        if not existing_binding:
            # 首位绑定者为 admin
            role = "admin" if existing_bindings_count == 0 else "member"
            binding = CareBinding(
                patient_id=patient.id,
                caregiver_id=caregiver.id,
                role=role,
            )
            db.add(binding)
            await db.commit()
        else:
            role = existing_binding.role

    else:
        caregiver = None
        role = "admin" if existing_bindings_count == 0 else "member"

    return ScanResponse(
        patient_id=patient.id,
        device_code=patient.device_code,
        is_new=(existing_bindings_count == 0),
        role=role,
        patient_name=patient.display_name,
    )


@router.post("/complete", response_model=CompleteConfigResponse)
async def complete_config(
    req: CompleteConfigRequest,
    db: AsyncSession = Depends(get_db),
):
    """完成初始化配置（仅admin）

    1. 写入 patient_configs
    2. 异步触发资产包生成
    3. 返回配置结果
    """
    # 1. 写入 patient_configs
    config = PatientConfig(
        patient_id=req.patient_id,
        era=req.era,
        region=req.region,
        language=req.language,
        persona_name=req.persona_name,
    )
    db.add(config)
    await db.commit()

    # 2. 异步触发资产包生成（不阻塞返回）
    try:
        await generate_asset_pack(req.patient_id, req.era, req.region)
    except Exception as e:
        logger.error("资产包生成失败 patient_id=%s error=%s", req.patient_id, e)
        # 不阻断流程，配置已写入
        return CompleteConfigResponse(
            success=True,
            patient_id=req.patient_id,
            config={
                "era": req.era,
                "region": req.region,
                "language": req.language,
                "persona_name": req.persona_name,
                "asset_pack_status": "failed",
            },
        )

    return CompleteConfigResponse(
        success=True,
        patient_id=req.patient_id,
        config={
            "era": req.era,
            "region": req.region,
            "language": req.language,
            "persona_name": req.persona_name,
            "asset_pack_status": "ready",
        },
    )
