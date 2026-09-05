import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.persona import Persona
from app.schemas.persona import (
    PersonaListResponse,
    PersonaResponse,
)
from app.core.minio_service import upload_photo, upload_audio
from app.core.face_comparison import detect_and_extract
from app.core.voice_clone import trigger_voice_clone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/personas", tags=["人物库"])


@router.post("", response_model=PersonaResponse)
async def create_persona(
    patient_id: UUID = Form(...),
    name: str = Form(...),
    relation: str = Form(None),
    sample_photo: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    """创建人物库条目（首次标注）

    1. 如有照片 -> 上传至 MinIO
    2. 提取 face_embedding（占位）
    3. 写入 personas 表
    """
    sample_photo_url: str | None = None

    # Step 1: 如有照片 -> 上传至 MinIO
    if sample_photo and sample_photo.filename:
        try:
            photo_bytes = await sample_photo.read()
            sample_photo_url = await upload_photo(patient_id, photo_bytes, sample_photo.filename)

            # Step 2: 提取 face_embedding（占位模式，返回空列表）
            faces = await detect_and_extract(photo_bytes)
            # TODO: 当 face_embedding 可用时写入
        except Exception as e:
            logger.error("照片处理失败: %s", e)
            sample_photo_url = None

    # Step 3: 写入 personas 表
    persona = Persona(
        patient_id=patient_id,
        name=name,
        relation=relation,
        sample_photo_url=sample_photo_url,
        face_embedding=None,
        voice_cloned=False,
    )
    db.add(persona)
    await db.commit()
    await db.refresh(persona)

    logger.info("人物库条目已创建: id=%s, name=%s, patient_id=%s", persona.id, name, patient_id)

    return PersonaResponse(
        id=persona.id,
        name=persona.name,
        relation=persona.relation,
        sample_photo_url=persona.sample_photo_url,
        voice_sample_url=persona.voice_sample_url,
        voice_cloned=persona.voice_cloned,
        created_at=persona.created_at,
    )


@router.put("/{persona_id}/voice", response_model=PersonaResponse)
async def upload_voice_sample(
    persona_id: UUID,
    voice_sample: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传语音样本 + 触发克隆（占位）

    1. 上传至 MinIO
    2. 更新 voice_sample_url
    3. 异步触发声音克隆（占位）
    """
    # 查询人物库条目
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()

    if not persona:
        raise HTTPException(status_code=404, detail="人物库条目不存在")

    # Step 1: 上传语音样本至 MinIO
    try:
        audio_bytes = await voice_sample.read()
        filename = f"{persona_id}_voice_{voice_sample.filename}"
        voice_sample_url = await upload_audio(persona.patient_id, audio_bytes, filename)

        # Step 2: 更新 voice_sample_url
        persona.voice_sample_url = voice_sample_url

        # Step 3: 异步触发声音克隆（占位模式返回 False，不阻塞）
        cloned = await trigger_voice_clone(persona_id, voice_sample_url)
        if cloned:
            persona.voice_cloned = True
        else:
            logger.info("声音克隆占位模式，未实际执行: persona_id=%s", persona_id)

        await db.commit()
        await db.refresh(persona)

        logger.info("语音样本已上传: persona_id=%s, url=%s", persona_id, voice_sample_url)
    except Exception as e:
        logger.error("语音样本上传失败: %s", e)
        raise HTTPException(status_code=500, detail="语音样本上传失败")

    return PersonaResponse(
        id=persona.id,
        name=persona.name,
        relation=persona.relation,
        sample_photo_url=persona.sample_photo_url,
        voice_sample_url=persona.voice_sample_url,
        voice_cloned=persona.voice_cloned,
        created_at=persona.created_at,
    )


@router.get("", response_model=PersonaListResponse)
async def list_personas(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """查询人物库"""
    stmt = (
        select(Persona)
        .where(Persona.patient_id == patient_id)
        .order_by(Persona.created_at.desc())
    )
    result = await db.execute(stmt)
    personas = list(result.scalars().all())

    return PersonaListResponse(
        personas=[
            PersonaResponse(
                id=p.id,
                name=p.name,
                relation=p.relation,
                sample_photo_url=p.sample_photo_url,
                voice_sample_url=p.voice_sample_url,
                voice_cloned=p.voice_cloned,
                created_at=p.created_at,
            )
            for p in personas
        ]
    )


@router.delete("/{persona_id}")
async def delete_persona(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """删除人物（级联删除音色/视频）"""
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()

    if not persona:
        raise HTTPException(status_code=404, detail="人物库条目不存在")

    # TODO: 级联删除 MinIO 中的语音样本、克隆音色、微动视频
    await db.delete(persona)
    await db.commit()

    logger.info("人物库条目已删除: id=%s", persona_id)

    return {"detail": "人物库条目已删除"}
