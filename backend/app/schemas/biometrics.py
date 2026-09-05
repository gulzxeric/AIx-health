from datetime import datetime

from pydantic import BaseModel, Field


class GazeEvent(BaseModel):
    timestamp: float = Field(..., description="事件时间戳（毫秒）")
    x: float = Field(..., description="注视点 X 坐标")
    y: float = Field(..., description="注视点 Y 坐标")
    duration: float = Field(..., description="注视持续时间（毫秒）")


class AcousticEvent(BaseModel):
    timestamp: float = Field(..., description="事件时间戳（毫秒）")
    amplitude: float = Field(..., description="振幅值")
    is_voice: bool = Field(..., description="是否为人声")


class GazeDataRequest(BaseModel):
    session_id: str | None = Field(None, description="关联对话 session ID")
    gaze_events: list[GazeEvent] = Field(default_factory=list)
    avg_fixation_ms: float = Field(0.0, description="注视维持时长均值（毫秒）")
    avg_saccade_ms: float = Field(0.0, description="扫视潜伏期均值（毫秒）")


class AcousticDataRequest(BaseModel):
    session_id: str | None = Field(None, description="关联对话 session ID")
    acoustic_events: list[AcousticEvent] = Field(default_factory=list)
    avg_pause_ms: float = Field(0.0, description="声学停顿延迟均值（毫秒）")
    voice_duration_ms: float = Field(0.0, description="主动发声总时长（毫秒）")


class SessionSummaryRequest(BaseModel):
    session_id: str = Field(..., description="对话 session ID")
    total_duration_ms: float = Field(0.0, description="会话总时长（毫秒）")
    gaze_metrics: dict = Field(default_factory=dict, description="眼动汇总指标")
    acoustic_metrics: dict = Field(default_factory=dict, description="声学汇总指标")


class BiometricsResponse(BaseModel):
    success: bool = True
    recorded_at: datetime
