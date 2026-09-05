import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import cast, select, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.memory import Memory
from app.schemas.memory import (
    MemoryCreateRequest,
    MemoryListResponse,
    MemoryResponse,
    MemoryUpdateRequest,
)
from app.core.asr_service import speech_to_text
from app.core.face_service import detect_faces, compare_faces
from app.core.llm_pipeline import extract_entities, generate_embedding
from app.core.minio_service import upload_photo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["记忆管理"])


@router.post("", response_model=MemoryResponse)
async def create_memory(
    patient_id: UUID = Form(...),
    raw_text: str = Form(...),
    caregiver_id: UUID = Form(...),
    photo: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    """提交记忆（语音转文本/直接输入/照片）

    完整 Pipeline:
    1. 如有照片 -> 上传至 MinIO
    2. 如有照片 -> 人脸检测+比对（调用 face_service）
    3. LLM 实体抽取（调用 llm_pipeline）
    4. 生成向量嵌入（占位）
    5. 写入 memories 表
    6. 返回记忆卡片
    """
    photo_url: str | None = None
    photo_people: list = []

    # Step 1: 如有照片 -> 上传至 MinIO
    if photo and photo.filename:
        try:
            photo_bytes = await photo.read()
            photo_url = await upload_photo(patient_id, photo_bytes, photo.filename)

            # Step 2: 人脸检测+比对
            face_embeddings = await detect_faces(photo_bytes)
            for face_emb in face_embeddings:
                matches = await compare_faces(face_emb, patient_id, db)
                for match in matches:
                    if match.get("name"):
                        photo_people.append(match["name"])
        except Exception as e:
            logger.error("照片处理失败: %s", e)
            # 照片处理失败不阻断整个流程
            photo_url = None

    # Step 3: LLM 实体抽取
    entities = await extract_entities(raw_text)

    # 如果人脸识别有结果，合并到 entities
    if photo_people:
        entities["photo_people"] = list(set(entities.get("photo_people", []) + photo_people))

    # Step 4: 生成向量嵌入（占位）
    vector_embedding = await generate_embedding(raw_text)

    # Step 5: 写入 memories 表
    memory = Memory(
        patient_id=patient_id,
        caregiver_id=caregiver_id,
        raw_text=raw_text,
        photo_url=photo_url,
        entities=entities,
        vector_embedding=vector_embedding,
        sync_status="synced",
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)

    logger.info("记忆已创建: id=%s, patient_id=%s", memory.id, patient_id)

    # Step 6: 返回记忆卡片
    return MemoryResponse(
        id=memory.id,
        raw_text=memory.raw_text,
        entities=memory.entities,
        photo_url=memory.photo_url,
        sync_status=memory.sync_status,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    patient_id: UUID = Query(...),
    tag: str | None = Query(None, description="按实体标签筛选（如 era, location, event, preference）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """查询记忆列表（按患者+标签筛选，分页）"""
    # 基础查询
    base_query = select(Memory).where(Memory.patient_id == patient_id)

    # 按实体标签筛选
    if tag:
        # 在 entities JSONB 中筛选包含 tag 值（全文检索字段值）
        base_query = base_query.where(
            cast(Memory.entities, JSONB).contains([tag])
        )

    # 总数
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    stmt = (
        base_query
        .order_by(Memory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    memories = list(result.scalars().all())

    return MemoryListResponse(
        memories=[
            MemoryResponse(
                id=m.id,
                raw_text=m.raw_text,
                entities=m.entities,
                photo_url=m.photo_url,
                sync_status=m.sync_status,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in memories
        ],
        total=total,
    )


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: UUID,
    req: MemoryUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """编辑记忆实体"""
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory = result.scalar_one_or_none()

    if not memory:
        raise HTTPException(status_code=404, detail="记忆条目不存在")

    if req.entities is not None:
        memory.entities = req.entities

    await db.commit()
    await db.refresh(memory)

    return MemoryResponse(
        id=memory.id,
        raw_text=memory.raw_text,
        entities=memory.entities,
        photo_url=memory.photo_url,
        sync_status=memory.sync_status,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """硬删除记忆"""
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory = result.scalar_one_or_none()

    if not memory:
        raise HTTPException(status_code=404, detail="记忆条目不存在")

    await db.delete(memory)
    await db.commit()

    return {"detail": "记忆已删除"}
