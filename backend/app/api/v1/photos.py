import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.photo import Photo
from app.schemas.photo import PhotoResponse
from app.core.minio_service import upload_photo
from app.core.face_comparison import detect_and_extract, match_persona, auto_label_photo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/photos", tags=["照片"])


@router.post("", response_model=PhotoResponse)
async def upload_photo_endpoint(
    patient_id: UUID = Form(...),
    uploaded_by: UUID = Form(...),
    photo: UploadFile = File(...),
    persona_name: str = Form(None),
    persona_relation: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """上传照片（含人物标注可选）

    1. 上传原始照片至 MinIO
    2. 生成缩略图（占位）
    3. 人脸检测 + 特征提取（占位）
    4. 与人物库比对
    5. 写入 photos 表
    """
    # Step 1: 上传原始照片至 MinIO
    try:
        photo_bytes = await photo.read()
        object_url = await upload_photo(patient_id, photo_bytes, photo.filename)
    except Exception as e:
        logger.error("照片上传失败: %s", e)
        raise HTTPException(status_code=500, detail="照片上传失败")

    # Step 2: 生成缩略图（占位，先使用原图 URL）
    thumbnail_url = None
    # TODO: 接入缩略图生成

    # Step 3-4: 人脸检测 + 比对
    detected_persona_name = persona_name
    detected_persona_relation = persona_relation

    if not persona_name:
        # 自动标注
        try:
            label_result = await auto_label_photo(patient_id, photo_bytes, db)
            if label_result["faces_detected"] > 0 and label_result["labels"]:
                detected_persona_name = label_result["labels"][0]
                if label_result["matches"] and len(label_result["matches"]) > 0:
                    detected_persona_relation = label_result["matches"][0].get("relation")
        except Exception as e:
            logger.error("自动人脸标注失败: %s", e)
            # 不阻断流程

    # Step 5: 写入 photos 表
    new_photo = Photo(
        patient_id=patient_id,
        uploaded_by=uploaded_by,
        object_url=object_url,
        thumbnail_url=thumbnail_url,
        persona_name=detected_persona_name,
        persona_relation=detected_persona_relation,
        face_embedding=None,  # TODO: 提取后写入
    )
    db.add(new_photo)
    await db.commit()
    await db.refresh(new_photo)

    logger.info(
        "照片已上传: id=%s, patient_id=%s, persona=%s",
        new_photo.id, patient_id, detected_persona_name,
    )

    return PhotoResponse(
        id=new_photo.id,
        object_url=new_photo.object_url,
        thumbnail_url=new_photo.thumbnail_url,
        persona_name=new_photo.persona_name,
        persona_relation=new_photo.persona_relation,
        created_at=new_photo.created_at,
    )


@router.get("", response_model=list[PhotoResponse])
async def get_photos(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取患者照片列表

    查询 photos 表，按 created_at 降序。
    """
    stmt = (
        select(Photo)
        .where(Photo.patient_id == patient_id)
        .order_by(Photo.created_at.desc())
    )
    result = await db.execute(stmt)
    photos = list(result.scalars().all())

    return [
        PhotoResponse(
            id=p.id,
            object_url=p.object_url,
            thumbnail_url=p.thumbnail_url,
            persona_name=p.persona_name,
            persona_relation=p.persona_relation,
            created_at=p.created_at,
        )
        for p in photos
    ]
