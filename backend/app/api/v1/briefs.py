from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.daily_brief import DailyBrief
from app.schemas.brief import BriefListResponse, BriefResponse, TopicItem

router = APIRouter(prefix="/briefs", tags=["每日简报"])


@router.get("/latest", response_model=BriefResponse)
async def get_latest_brief(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取最新简报"""
    stmt = (
        select(DailyBrief)
        .where(DailyBrief.patient_id == patient_id)
        .order_by(DailyBrief.date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    brief = result.scalar_one_or_none()

    if brief is None:
        raise HTTPException(status_code=404, detail="暂无简报数据")

    return _brief_to_response(brief)


@router.get("/{date}", response_model=BriefResponse)
async def get_brief_by_date(
    date: str,
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取指定日期简报"""
    from datetime import date as date_type

    try:
        target_date = date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")

    stmt = select(DailyBrief).where(
        DailyBrief.patient_id == patient_id,
        DailyBrief.date == target_date,
    )
    result = await db.execute(stmt)
    brief = result.scalar_one_or_none()

    if brief is None:
        raise HTTPException(status_code=404, detail="该日期暂无简报数据")

    return _brief_to_response(brief)


@router.get("", response_model=BriefListResponse)
async def list_briefs(
    patient_id: UUID,
    limit: int = 7,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """获取简报列表（最近 N 条）"""
    stmt = (
        select(DailyBrief)
        .where(DailyBrief.patient_id == patient_id)
        .order_by(DailyBrief.date.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    briefs = list(result.scalars().all())

    return BriefListResponse(
        briefs=[_brief_to_response(b) for b in briefs],
        total=len(briefs),
    )


def _brief_to_response(brief: DailyBrief) -> BriefResponse:
    """将 ORM 模型转换为 Pydantic response"""
    topics = []
    for t in (brief.top_topics or []):
        if isinstance(t, dict):
            topics.append(TopicItem(
                topic_name=t.get("topic_name", ""),
                gaze_duration=t.get("gaze_duration", 0.0),
                dialogue_turns=t.get("dialogue_turns", 0),
                active_vocalizations=t.get("active_vocalizations", 0),
            ))

    return BriefResponse(
        id=str(brief.id),
        date=brief.date,
        vitality_index=brief.vitality_index,
        vitality_trend_pct=brief.vitality_trend_pct,
        baseline_status=brief.baseline_status,
        baseline_days_remaining=brief.baseline_days_remaining,
        top_topics=topics,
        advice_text=brief.advice_text,
        created_at=brief.created_at,
    )
