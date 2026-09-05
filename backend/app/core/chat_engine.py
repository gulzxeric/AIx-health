import uuid
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.chat_session import ChatSession
from app.models.memory import Memory
from app.models.patient_config import PatientConfig
from app.models.persona import Persona
from app.models.photo import Photo


class ChatEngine:
    """对话引擎 - 老街坊/照片亲人模式"""

    def __init__(self):
        self._llm_client: AsyncOpenAI | None = None

    @property
    def llm_client(self) -> AsyncOpenAI:
        if self._llm_client is None:
            self._llm_client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_ENDPOINT,
            )
        return self._llm_client

    async def retrieve_memories(
        self,
        patient_id: uuid.UUID,
        query: str,
        top_k: int = 3,
    ) -> list[Memory]:
        """检索相关记忆（先用 JSON 字段模拟向量检索）

        后续替换为 pgvector 余弦相似度语义检索。
        """
        async with async_session_factory() as db:
            stmt = (
                select(Memory)
                .where(Memory.patient_id == patient_id)
                .order_by(Memory.created_at.desc())
                .limit(top_k * 2)  # 多取一些，后面用关键词过滤
            )
            result = await db.execute(stmt)
            memories = list(result.scalars().all())

        # 简单关键词匹配（临时模拟语义检索）
        keywords = set(query.lower().split())
        scored: list[tuple[Memory, int]] = []
        for m in memories:
            score = 0
            m_lower = m.raw_text.lower()
            for kw in keywords:
                if kw in m_lower:
                    score += 1
            if score > 0:
                scored.append((m, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [m for m, _ in scored[:top_k]]

    async def get_photo_context(
        self,
        patient_id: uuid.UUID,
        limit: int = 5,
    ) -> str:
        """获取当前轮播照片上下文"""
        async with async_session_factory() as db:
            stmt = (
                select(Photo)
                .where(Photo.patient_id == patient_id)
                .order_by(Photo.created_at.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            photos = list(result.scalars().all())

        if not photos:
            return "当前没有轮播照片"

        lines = ["当前轮播照片："]
        for p in photos:
            parts = []
            if p.persona_name:
                parts.append(f"人物：{p.persona_name}")
            if p.persona_relation:
                parts.append(f"关系：{p.persona_relation}")
            parts.append(f"上传时间：{p.created_at.strftime('%Y-%m-%d')}")
            lines.append(" - " + "，".join(parts))

        return "\n".join(lines)

    def build_prompt(
        self,
        patient_config: PatientConfig,
        memories: list[Memory],
        photo_context: str,
        asr_text: str,
        photo_persona: dict | None = None,
    ) -> list[dict]:
        """构造 LLM prompt（photo_persona 命中时以照片亲人身份）"""
        memory_lines = [f"{i}. {m.raw_text}" for i, m in enumerate(memories, 1)]

        if photo_persona:
            p_name = photo_persona.get("persona_name", "亲人")
            p_relation = photo_persona.get("persona_relation") or "亲人"
            system_prompt = f"""你是{p_name}，患者的{p_relation}。你正通过数字相框和患者说话。
你和患者共同经历过下面这些事，像你亲自记得一样自然引用。

【核心对话规则】
1. 时空错位不纠错：顺着患者的话说，禁止出现"退休/你不是/你记错了"之类的否定和纠错。
2. 引用记忆：把下面的记忆自然穿插在对话中。
3. 语言一致：使用患者使用的语言（{patient_config.language or 'zh-CN'}）。
4. 简洁回复：回复严格控制在 40 字以内（中文）。

【记忆上下文】
{chr(10).join(memory_lines) if memory_lines else '暂无相关记忆'}

【照片上下文】
{photo_context}"""
        else:
            system_prompt = f"""你是{patient_config.persona_name or '强叔'}，一个{patient_config.era or '1980s'}年代的同龄街坊。你和患者是老相识、老街坊，一起在那个年代生活过。

【核心对话规则】
1. 时空错位不纠错：患者说"我要去上班"时回复"今天厂里排休呢"，禁止出现"退休/你不是/你记错了"之类的否定和纠错。
2. 引用记忆：将以下记忆自然穿插在对话中，仿佛你也记得这些事。
3. 语言一致：使用患者使用的语言（{patient_config.language or 'zh-CN'}）。
4. 简洁回复：回复严格控制在 40 字以内（中文）。

【患者画像】
- 年代：{patient_config.era or '未知'}
- 地区：{patient_config.region or '未知'}
- 语言：{patient_config.language or 'zh-CN'}

【记忆上下文】
{chr(10).join(memory_lines) if memory_lines else '暂无相关记忆'}

【照片上下文】
{photo_context}"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": asr_text},
        ]

    async def _call_llm_with_retry(
        self,
        messages: list[dict],
        max_retries: int = 2,
    ) -> str:
        """调用 LLM 并带指数退避重试"""
        import asyncio

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = await self.llm_client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=messages,
                    max_tokens=100,
                    temperature=0.7,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                continue

        raise last_error  # type: ignore[misc]

    async def _resolve_photo_persona(
        self,
        patient_id: uuid.UUID,
        photo_id: uuid.UUID,
    ) -> tuple[dict, Persona | None] | None:
        """照片有人物标注时返回 (照片人物信息, 人物库同名条目或None)"""
        info = await self.check_photo_persona_mode(patient_id, photo_id)
        if not info:
            return None
        async with async_session_factory() as db:
            stmt = select(Persona).where(
                Persona.patient_id == patient_id,
                Persona.name == info["persona_name"],
            )
            row = (await db.execute(stmt)).scalar_one_or_none()
        return info, row

    async def generate_reply(
        self,
        patient_id: uuid.UUID,
        asr_text: str,
        photo_context: str | None = None,
        photo_id: uuid.UUID | None = None,
    ) -> dict:
        """生成回复的完整流程

        Returns:
            {"reply_text": str, "persona": str,
             "persona_id": UUID | None, "voice_source": "cloned" | "default"}
        """
        async with async_session_factory() as db:
            cfg_stmt = select(PatientConfig).where(
                PatientConfig.patient_id == patient_id
            )
            cfg_result = await db.execute(cfg_stmt)
            patient_config = cfg_result.scalar_one_or_none()

        if patient_config is None:
            return {
                "reply_text": "你好呀，今天想聊点什么？",
                "persona": "老街坊",
                "persona_id": None,
                "voice_source": "default",
            }

        # 0. 照片亲人模式解析（photo_id 命中人物标注）
        photo_persona_info = None
        persona_row = None
        if photo_id is not None:
            resolved = await self._resolve_photo_persona(patient_id, photo_id)
            if resolved:
                photo_persona_info, persona_row = resolved

        # 1. 检索记忆
        memories = await self.retrieve_memories(patient_id, asr_text)

        # 2. 获取照片上下文
        if photo_context is None:
            photo_context = await self.get_photo_context(patient_id)

        # 3. 构建 prompt（照片亲人模式用人物身份）
        messages = self.build_prompt(
            patient_config, memories, photo_context, asr_text,
            photo_persona=photo_persona_info,
        )

        # 4. 调用 LLM
        reply_text = await self._call_llm_with_retry(messages)

        # 5. 确保不超过 40 字
        if len(reply_text) > 40:
            reply_text = reply_text[:40]

        # 6. 角色与音色来源
        if photo_persona_info:
            persona = photo_persona_info["persona_name"]
            if persona_row is not None and persona_row.voice_cloned:
                return {
                    "reply_text": reply_text,
                    "persona": persona,
                    "persona_id": persona_row.id,
                    "voice_source": "cloned",
                }
            return {
                "reply_text": reply_text,
                "persona": persona,
                "persona_id": None,
                "voice_source": "default",
            }

        return {
            "reply_text": reply_text,
            "persona": patient_config.persona_name or "老街坊",
            "persona_id": None,
            "voice_source": "default",
        }

    async def check_photo_persona_mode(
        self,
        patient_id: uuid.UUID,
        photo_id: uuid.UUID,
    ) -> dict | None:
        """检查是否触发照片亲人模式

        如果照片有 persona_name，切换角色。

        Returns:
            {"persona_name": str, "persona_relation": str | None} 或 None
        """
        async with async_session_factory() as db:
            stmt = select(Photo).where(
                Photo.id == photo_id,
                Photo.patient_id == patient_id,
            )
            result = await db.execute(stmt)
            photo = result.scalar_one_or_none()

        if photo and photo.persona_name:
            return {
                "persona_name": photo.persona_name,
                "persona_relation": photo.persona_relation,
            }
        return None


# 单例
chat_engine = ChatEngine()
