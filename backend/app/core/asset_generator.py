"""资产包生成（LLM 调用）"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import openai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.asset_pack import AssetPack

logger = logging.getLogger(__name__)


def _build_asset_pack_prompt(era: str, region: dict) -> list[dict]:
    """构造资产包生成的 Prompt"""
    region_desc = f"{region.get('country', '')} {region.get('province', '')} {region.get('city', '')}".strip()
    system_prompt = (
        "你是年代记忆资产生成器。根据指定的年代和地区，生成一套该年代的生活记忆资产包。\n"
        "请严格按照 JSON 格式输出，不要包含 markdown 代码块标记。\n"
        "输出 JSON 结构如下：\n"
        "{\n"
        '  "photo_urls": ["图片来源描述或占位URL列表"],\n'
        '  "topic_library": ["该年代常见话题1", "话题2", ...],\n'
        '  "prompt_anchors": ["记忆锚点描述1", "锚点2", ...]\n'
        "}"
    )
    user_prompt = (
        f"年代：{era}\n"
        f"地区：{region_desc}\n"
        "请为该年代和地区的老人生成记忆资产包，包含：\n"
        "1. 年代照片 URL 列表（描述性占位，如 '1980s_canton_factory'）\n"
        "2. 话题库（10-15 个该年代常见聊天话题）\n"
        "3. 记忆锚点（5-8 个能唤起回忆的具象场景描述）\n"
        "返回纯 JSON，不要附带其他文字。"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def generate_asset_pack(
    patient_id: UUID, era: str, region: dict
) -> AssetPack:
    """调用 LLM 生成年代资产包并写入数据库。

    1. 构造 prompt
    2. 调用 openai API（指数退避重试）
    3. 解析返回的 JSON
    4. 写入 asset_packs 表
    5. 状态标记为 ready
    """
    # 构造 region_key
    region_key = (
        f"{region.get('country', 'XX')}-"
        f"{region.get('province', '')}-"
        f"{region.get('city', '')}"
    )

    async with async_session_factory() as db:
        # 先创建 asset_pack 记录（status=generating）
        asset_pack = AssetPack(
            patient_id=patient_id,
            era=era,
            region_key=region_key,
            status="generating",
        )
        db.add(asset_pack)
        await db.commit()
        await db.refresh(asset_pack)

        pack_id = asset_pack.id

        # 调用 LLM（指数退避重试）
        messages = _build_asset_pack_prompt(era, region)
        max_retries = 3

        for attempt in range(max_retries):
            try:
                client = openai.AsyncOpenAI(
                    api_key=settings.LLM_API_KEY,
                    base_url=settings.LLM_ENDPOINT,
                )
                response = await client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"},
                    timeout=60,
                )

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("LLM 返回空内容")

                data = json.loads(content)

                # 更新 asset_pack 记录
                async with async_session_factory() as update_db:
                    result = await update_db.execute(
                        select(AssetPack).where(AssetPack.id == pack_id)
                    )
                    pack = result.scalar_one_or_none()
                    if pack:
                        pack.photo_urls = data.get("photo_urls", [])
                        pack.topic_library = data.get("topic_library", [])
                        pack.prompt_anchors = data.get("prompt_anchors", [])
                        pack.status = "ready"
                        pack.generated_at = datetime.now(timezone.utc)
                        await update_db.commit()

                logger.info(
                    "资产包生成成功 patient_id=%s pack_id=%s",
                    patient_id, pack_id,
                )
                return asset_pack

            except (openai.APIError, json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    "资产包生成失败 attempt=%d/%d pack_id=%s error=%s",
                    attempt + 1, max_retries, pack_id, e,
                )
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                else:
                    # 最后一次失败，标记为 failed
                    async with async_session_factory() as fail_db:
                        result = await fail_db.execute(
                            select(AssetPack).where(AssetPack.id == pack_id)
                        )
                        pack = result.scalar_one_or_none()
                        if pack:
                            pack.status = "failed"
                            await fail_db.commit()
                    logger.error(
                        "资产包生成最终失败 patient_id=%s pack_id=%s",
                        patient_id, pack_id,
                    )
                    raise

    return asset_pack
