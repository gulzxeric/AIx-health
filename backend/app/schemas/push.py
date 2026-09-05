from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PushSubscriptionRequest(BaseModel):
    """家属端注册推送订阅请求"""
    endpoint: str = Field(..., description="Push endpoint URL")
    p256dh_key: str = Field(..., description="P-256 DH 公钥（base64）")
    auth_key: str = Field(..., description="Auth 密钥（base64）")


class PushSubscriptionResponse(BaseModel):
    """推送订阅响应"""
    id: str = Field(..., description="订阅 ID")
    created_at: datetime = Field(..., description="创建时间")


class PushSendRequest(BaseModel):
    """手动推送请求"""
    patient_id: UUID = Field(..., description="患者 ID")
    title: str = Field(..., description="推送标题")
    body: str = Field(..., description="推送内容")
    tag: str | None = Field(None, description="推送标签（用于去重）")
