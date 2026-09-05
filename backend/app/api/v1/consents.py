"""知情同意路由"""
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.binding_service import (
    create_caregiver,
    find_caregiver_by_phone,
    find_patient_by_code,
)
from app.database import get_db
from app.models.care_binding import CareBinding
from app.models.caregiver import Caregiver
from app.models.consent import Consent
from app.models.patient import Patient
from app.schemas.binding import ConsentSignRequest, ConsentSignResponse

router = APIRouter(prefix="/consents", tags=["知情同意"])


def _compute_content_hash(patient_id: UUID, caregiver_name: str, consent_version: str) -> str:
    """计算签署内容的 SHA256 哈希"""
    raw = json.dumps(
        {
            "patient_id": str(patient_id),
            "caregiver_name": caregiver_name,
            "consent_version": consent_version,
            "consent_text": "数字记忆相框知情同意书：采集语音、文字、照片、人脸特征、眼动数据、声学数据，用于记忆资产、认知简报、数字人对话、声音克隆。原始录音永久保存。照片中非本人人物的授权由上传者担保。",
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@router.post("", response_model=ConsentSignResponse)
async def sign_consent(
    req: ConsentSignRequest,
    db: AsyncSession = Depends(get_db),
):
    """签署知情同意

    1. 查找或创建家属
    2. 生成 consent_version (v1.0)
    3. 计算 content_hash (SHA256)
    4. 写入 consents 表
    5. 更新 care_bindings.consent_id
    """
    # 1. 检查患者是否存在
    result = await db.execute(
        select(Patient).where(Patient.id == req.patient_id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该患者",
        )

    # 2. 查找或创建家属
    caregiver = await find_caregiver_by_phone(db, req.caregiver_phone)
    if not caregiver:
        caregiver = await create_caregiver(db, req.caregiver_name, req.caregiver_phone)

    # 3. 生成 consent_version
    consent_version = "v1.0"

    # 4. 计算 content_hash
    content_hash = _compute_content_hash(req.patient_id, req.caregiver_name, consent_version)

    # 5. 写入 consents 表
    consent = Consent(
        caregiver_id=caregiver.id,
        patient_id=req.patient_id,
        consent_version=consent_version,
        content_hash=content_hash,
    )
    db.add(consent)
    await db.flush()

    # 6. 更新 care_bindings.consent_id
    result = await db.execute(
        select(CareBinding).where(
            CareBinding.patient_id == req.patient_id,
            CareBinding.caregiver_id == caregiver.id,
        )
    )
    binding = result.scalar_one_or_none()
    if binding:
        binding.consent_id = consent.id
    else:
        # 如果还没有绑定关系，创建一条（角色默认为 member）
        binding = CareBinding(
            patient_id=req.patient_id,
            caregiver_id=caregiver.id,
            role="member",
            consent_id=consent.id,
        )
        db.add(binding)

    await db.commit()

    return ConsentSignResponse(
        id=consent.id,
        signed_at=consent.signed_at.isoformat(),
        consent_version=consent_version,
    )


@router.get("/{patient_id}")
async def get_consents(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """查询某患者的所有同意记录"""
    result = await db.execute(
        select(Consent).where(
            Consent.patient_id == patient_id
        ).order_by(Consent.signed_at.desc())
    )
    consents = result.scalars().all()

    return [
        {
            "id": c.id,
            "caregiver_id": c.caregiver_id,
            "consent_version": c.consent_version,
            "content_hash": c.content_hash,
            "signed_at": c.signed_at.isoformat(),
        }
        for c in consents
    ]
