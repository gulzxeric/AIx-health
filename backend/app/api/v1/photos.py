from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.photo import Photo
from app.schemas.photo import PhotoResponse

router = APIRouter(prefix="/photos", tags=["照片"])


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
