from datetime import date, datetime

from pydantic import BaseModel, Field


class TopicItem(BaseModel):
    topic_name: str = Field(..., description="话题名")
    gaze_duration: float = Field(0.0, description="注视时长（秒）")
    dialogue_turns: int = Field(0, description="对话轮次")
    active_vocalizations: int = Field(0, description="主动发声次数")


class BriefResponse(BaseModel):
    id: str
    date: date
    vitality_index: int | None = Field(None, description="活力指数，null 表示基线期")
    vitality_trend_pct: int | None = Field(None, description="较昨日变化百分比")
    baseline_status: str = Field("ready", description="基线状态: collecting | ready")
    baseline_days_remaining: int = Field(0, description="基线剩余天数")
    top_topics: list[TopicItem] = Field(default_factory=list)
    advice_text: str | None = Field(None, description="LLM 生成沟通建议")
    created_at: datetime


class BriefListResponse(BaseModel):
    briefs: list[BriefResponse] = Field(default_factory=list)
    total: int = 0
