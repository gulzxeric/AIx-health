from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.push_subscription import PushSubscription
from app.schemas.push import (
    PushSubscriptionRequest,
    PushSubscriptionResponse,
)

router = APIRouter(prefix="/push", tags=["推送"])


@router.post("/subscribe", response_model=PushSubscriptionResponse)
async def subscribe(
    req: PushSubscriptionRequest,
    caregiver_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """家属端注册推送订阅

    1. 写入 push_subscriptions 表
    2. 返回 subscription id
    """
    stmt = select(PushSubscription).where(
        PushSubscription.caregiver_id == caregiver_id,
        PushSubscription.endpoint == req.endpoint,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.p256dh_key = req.p256dh_key
        existing.auth_key = req.auth_key
        await db.commit()
        await db.refresh(existing)
        return PushSubscriptionResponse(
            id=str(existing.id),
            created_at=existing.created_at,
        )

    subscription = PushSubscription(
        caregiver_id=caregiver_id,
        endpoint=req.endpoint,
        p256dh_key=req.p256dh_key,
        auth_key=req.auth_key,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)

    return PushSubscriptionResponse(
        id=str(subscription.id),
        created_at=subscription.created_at,
    )


@router.delete("/unsubscribe/{subscription_id}", status_code=204)
async def unsubscribe(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """取消订阅"""
    stmt = select(PushSubscription).where(
        PushSubscription.id == subscription_id,
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if subscription is None:
        raise HTTPException(status_code=404, detail="订阅不存在")

    await db.delete(subscription)
    await db.commit()
    return None


@router.get("/subscriptions/{patient_id}")
async def list_subscriptions(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """查询某患者所有家属的订阅"""
    from app.models.care_binding import CareBinding

    binding_stmt = select(CareBinding).where(
        CareBinding.patient_id == patient_id,
    )
    binding_result = await db.execute(binding_stmt)
    bindings = list(binding_result.scalars().all())

    if not bindings:
        return {"subscriptions": [], "total": 0}

    caregiver_ids = [b.caregiver_id for b in bindings]

    sub_stmt = select(PushSubscription).where(
        PushSubscription.caregiver_id.in_(caregiver_ids),
    )
    sub_result = await db.execute(sub_stmt)
    subscriptions = list(sub_result.scalars().all())

    return {
        "subscriptions": [
            {
                "id": str(s.id),
                "caregiver_id": str(s.caregiver_id),
                "endpoint": s.endpoint,
                "created_at": s.created_at.isoformat(),
            }
            for s in subscriptions
        ],
        "total": len(subscriptions),
    }
