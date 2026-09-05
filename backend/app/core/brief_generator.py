import uuid
from datetime import date, datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.daily_brief import DailyBrief
from app.models.patient_config import PatientConfig
from app.core.vitality_index import calculate_vitality_index, get_top_topics

# LLM 客户端（懒初始化）
_llm_client: AsyncOpenAI | None = None


def _get_llm_client() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_ENDPOINT,
        )
    return _llm_client


async def generate_advice(top_topics: list[dict], vitality: dict) -> str:
    """LLM 生成沟通建议

    Prompt：你是验证疗法沟通顾问，为家属提供沟通建议
    输入：高共鸣话题 + 活力指数
    输出：1-2 条建议，每条 <= 100 字
    """
    if not top_topics:
        return "今日暂无高共鸣话题，建议多陪伴老人。"

    topics_text = "\n".join(
        f"{i+1}. {t['topic_name']} - 注视 {t['gaze_duration']}s, "
        f"对话 {t['dialogue_turns']} 轮"
        for i, t in enumerate(top_topics)
    )

    vitality_text = f"活力指数：{vitality.get('vitality_index', '暂无')}"
    level_text = vitality.get("level_text", "")

    system_prompt = (
        "你是验证疗法沟通顾问，为家属提供今日与AD老人的沟通建议。\n\n"
        "沟通原则：\n"
        "1. 顺应老人的时空（不纠错）\n"
        "2. 基于高共鸣话题建议具体切入点\n"
        "3. 每条建议给出「聊什么」+「避坑提醒」\n\n"
        "输出1-2条建议，每条不超过100字。"
    )

    user_prompt = (
        f"今日高共鸣话题：\n{topics_text}\n\n"
        f"今日状态：{vitality_text}，{level_text}\n"
    )

    try:
        client = _get_llm_client()
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        advice = response.choices[0].message.content or ""
        return advice.strip()
    except Exception:
        # LLM 调用失败时返回兜底建议
        return (
            "今日老人有积极互动，建议多聊聊这些感兴趣的话题。"
            "注意顺应老人的时空认知，不刻意纠正。"
        )


async def generate_brief(
    patient_id: uuid.UUID,
) -> dict:
    """生成每日简报（完整流程）

    1. 计算活力指数
    2. 计算高共鸣话题 Top 3
    3. LLM 生成沟通建议
    4. 组装简报 JSON
    5. 写入 daily_briefs 表

    Returns:
        {"vitality_index": ..., "top_topics": ..., "advice_text": ...}
    """
    async with async_session_factory() as db:
        # 1. 计算活力指数
        vitality = await calculate_vitality_index(patient_id, db)

        # 2. 计算高共鸣话题 Top 3
        topics = await get_top_topics(patient_id, db)

        # 3. LLM 生成沟通建议
        advice = await generate_advice(topics, vitality)

        # 4. 组装简报
        today = date.today()
        yesterday = today  # 简报对应前一日数据，但日期标记为生成日

        # 5. 写入 daily_briefs 表
        brief = DailyBrief(
            patient_id=patient_id,
            date=yesterday,
            vitality_index=vitality.get("vitality_index"),
            vitality_trend_pct=vitality.get("vitality_trend_pct"),
            baseline_status=vitality.get("baseline_status", "ready"),
            baseline_days_remaining=vitality.get("baseline_days_remaining", 0),
            top_topics=[
                {
                    "topic_name": t["topic_name"],
                    "gaze_duration": t["gaze_duration"],
                    "dialogue_turns": t["dialogue_turns"],
                    "active_vocalizations": t["active_vocalizations"],
                }
                for t in topics
            ],
            advice_text=advice,
        )
        db.add(brief)
        await db.commit()
        await db.refresh(brief)

    return {
        "id": str(brief.id),
        "date": brief.date.isoformat(),
        "vitality_index": brief.vitality_index,
        "vitality_trend_pct": brief.vitality_trend_pct,
        "top_topics": topics,
        "advice_text": advice,
    }
