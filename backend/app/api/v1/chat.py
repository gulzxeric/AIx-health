import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chat_engine import chat_engine
from app.core.tts_service import synthesize_speech
from app.database import get_db
from app.models.chat_session import ChatSession
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    SessionEndRequest,
    SessionEndResponse,
    SessionStartRequest,
    SessionStartResponse,
)

router = APIRouter(prefix="/chat", tags=["对话引擎"])


@router.post("/session/start", response_model=SessionStartResponse)
async def start_session(
    req: SessionStartRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """开始对话 session

    生成 session_id，创建对话 session 记录。
    """
    patient_id = req.patient_id if req else None
    if patient_id is None:
        patient_id = uuid.uuid4()  # TODO: 从设备 token 提取真实 patient_id

    session = ChatSession(
        patient_id=patient_id,
        status="active",
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionStartResponse(
        session_id=session.id,
        started_at=session.started_at,
    )


@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(
    req: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """发送对话消息，返回数字人回复

    1. 检索相关记忆
    2. 检索当前轮播照片上下文
    3. 构造 LLM prompt（老街坊角色）
    4. 调用 LLM 生成回复
    5. TTS 合成语音（占位）
    6. 更新 session 消息计数
    """
    # 验证 session 存在且 active
    stmt = select(ChatSession).where(ChatSession.id == req.session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        return ChatMessageResponse(
            reply_text="你好呀，今天想聊点什么？",
            reply_audio_url=None,
            persona="老街坊",
            voice_source="default",
        )

    # 生成回复
    reply = await chat_engine.generate_reply(
        patient_id=session.patient_id,
        asr_text=req.asr_text,
        photo_context=req.photo_context,
    )

    # TTS 合成
    audio_url = await synthesize_speech(reply["reply_text"], language="zh-CN")

    # 更新 session 消息计数
    session.message_count += 1
    await db.commit()

    return ChatMessageResponse(
        reply_text=reply["reply_text"],
        reply_audio_url=audio_url,
        persona=reply["persona"],
        voice_source=reply["voice_source"],
    )


@router.post("/session/end", response_model=SessionEndResponse)
async def end_session(
    req: SessionEndRequest,
    db: AsyncSession = Depends(get_db),
):
    """结束对话 session，上报埋点

    1. 计算会话时长
    2. 存储埋点数据
    3. 返回 session 汇总
    """
    stmt = select(ChatSession).where(ChatSession.id == req.session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        return SessionEndResponse(
            session_id=req.session_id,
            duration_seconds=0.0,
            status="not_found",
        )

    now = datetime.now(timezone.utc)
    duration = (now - session.started_at).total_seconds()

    session.status = "ended"
    session.ended_at = now
    session.gaze_data = req.gaze_data
    session.acoustic_data = req.acoustic_data
    await db.commit()

    return SessionEndResponse(
        session_id=session.id,
        duration_seconds=duration,
        status="ended",
    )
