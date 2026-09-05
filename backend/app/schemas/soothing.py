from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SoothingEventRequest(BaseModel):
    """上报舒缓事件请求"""
    patient_id: UUID = Field(..., description="患者 ID")
    event_type: str = Field(
        ...,
        description="事件类型: settled_20min | time_window_end | negative_signal",
    )
    session_id: UUID | None = Field(None, description="关联的对话 session ID")
    metadata: dict | None = Field(None, description="附带元数据")


class SoothingEventResponse(BaseModel):
    """舒缓事件响应"""
    success: bool = Field(..., description="是否成功")
    event_id: str = Field("", description="事件记录 ID")
    recorded_at: datetime = Field(..., description="记录时间")


class SoothingConfig(BaseModel):
    """舒缓配置"""
    patient_id: UUID = Field(..., description="患者 ID")
    sunset_start: str = Field("17:00", description="日落窗口开始时间 (HH:MM)")
    sunset_end: str = Field("19:30", description="日落窗口结束时间 (HH:MM)")
    auto_soothing: bool = Field(True, description="是否自动触发舒缓模式")


class SunsetWindowResponse(BaseModel):
    """日落窗口检查响应"""
    in_window: bool = Field(..., description="当前是否在日落时间窗口内")
    window_start: str = Field("", description="窗口开始时间")
    window_end: str = Field("", description="窗口结束时间")
    remaining_minutes: int = Field(0, description="窗口剩余分钟数")


class NegativeSignalResponse(BaseModel):
    """负面信号检测响应"""
    has_negative: bool = Field(..., description="是否检测到负面信号")
    signals: list[dict] = Field(default_factory=list, description="检测到的信号详情")
    confidence: float = Field(0.0, description="检测置信度 0-1")


class SoothingAutoTriggerResponse(BaseModel):
    """自动触发舒缓模式响应"""
    triggered: bool = Field(..., description="是否触发")
    in_window: bool = Field(False, description="是否在日落窗口内")
    has_negative_signal: bool = Field(False, description="是否检测到负面信号")
    reason: str = Field("", description="未触发的原因说明")
