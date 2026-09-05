import asyncio
import json
import logging

import openai

from app.config import settings

logger = logging.getLogger(__name__)

client = openai.AsyncOpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_ENDPOINT,
)


async def extract_entities(
    raw_text: str,
    patient_era: str | None = None,
    language: str = "zh-CN",
) -> dict:
    """LLM 实体抽取

    输入：家属端发送的文本
    输出：结构化 JSON
    {
        "era": "1980s",
        "location": ["广州", "北京"],
        "event": "去北京旅游",
        "preference": ["听粤剧"],
        "photo_people": [],
        "confidence": 0.85,
        "missing": []
    }

    降级策略：指数退避重试 2 次 -> 降级为原文入库
    """
    system_prompt = (
        "你是\"记忆实体抽取器\"。从家属描述的老人生活片段中，提取实体并输出 JSON。\n"
        "输出格式必须为如下 JSON（无额外说明，只输出 JSON）：\n"
        "{\n"
        '  "era": "",           # 年代，如 "1980s", "1990s"，未知则空字符串\n'
        '  "location": [],      # 地点列表，如 ["广州", "北京"]\n'
        '  "event": "",         # 事件描述，如 "去北京旅游"，未知则空字符串\n'
        '  "preference": [],    # 偏好列表，如 ["听粤剧", "下象棋"]\n'
        '  "photo_people": [],  # 照片中人物姓名，无则空列表\n'
        '  "confidence": 0.0,   # 置信度 0-1\n'
        '  "missing": []        # 无法抽取的字段名列表\n'
        "}\n"
        "注意：如果原文中完全没有可提取的信息，设置 confidence 为 0，missing 中包含所有字段。"
    )

    context_block = ""
    if patient_era:
        context_block = f"患者出生年代：{patient_era}\n患者语言：{language}\n"

    user_message = f"{context_block}原文：{raw_text}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    return await _llm_call_with_retry(messages)


async def _llm_call_with_retry(
    messages: list[dict],
    max_retries: int = 2,
) -> dict:
    """执行 LLM 调用，含指数退避重试。

    重试 2 次后仍失败则降级，返回空实体结构。
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                timeout=30,
            )
            content = response.choices[0].message.content.strip()
            # 尝试解析 JSON
            try:
                result = json.loads(content)
                # 验证必填字段
                if isinstance(result, dict):
                    for key in ("era", "location", "event", "preference", "confidence"):
                        if key not in result:
                            result[key] = [] if key in ("location", "preference") else (0.0 if key == "confidence" else "")
                    return result
            except json.JSONDecodeError:
                # 非 JSON 输出，重试 1 次带纠正提示
                if attempt < max_retries:
                    logger.warning(
                        "LLM 输出非 JSON (attempt=%d), 重试带纠正提示",
                        attempt + 1,
                    )
                    messages.append(
                        {
                            "role": "assistant",
                            "content": content,
                        }
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": "请只输出 JSON 格式，不要包含其他文字。",
                        }
                    )
                    continue
                # 最后一次仍非 JSON，降级
                logger.error("LLM 输出非 JSON 已达最大重试，降级为原文入库")
                return _empty_entities(raw_text=messages[-1]["content"])

        except openai.RateLimitError as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning("LLM 限流 (attempt=%d), 等待 %ds", attempt + 1, wait)
            await asyncio.sleep(wait)

        except openai.APIError as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning("LLM API 错误 (attempt=%d), 等待 %ds", attempt + 1, wait)
            await asyncio.sleep(wait)

        except Exception as e:
            last_error = e
            logger.error("LLM 调用异常 (attempt=%d): %s", attempt + 1, e)
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
            else:
                logger.error("LLM 调用已达最大重试，降级为原文入库")
                return _empty_entities(raw_text=messages[-1]["content"])

    # 所有重试耗尽
    logger.error("LLM 调用全部失败: %s", last_error)
    return _empty_entities(raw_text=messages[-1]["content"])


def _empty_entities(raw_text: str = "") -> dict:
    """降级时返回的空实体结构。"""
    return {
        "era": "",
        "location": [],
        "event": "",
        "preference": [],
        "photo_people": [],
        "confidence": 0.0,
        "missing": ["era", "location", "event", "preference"],
    }


async def generate_embedding(text: str) -> list:
    """生成文本向量嵌入（占位，后续接入嵌入模型）

    当前返回虚拟 1536 维向量（全 0）
    """
    return [0.0] * 1536


_vision_client = None


def _get_vision_client() -> openai.AsyncOpenAI:
    """懒加载图片识别客户端（独立的 endpoint/key）"""
    global _vision_client
    if _vision_client is None:
        _vision_client = openai.AsyncOpenAI(
            api_key=settings.LLM_VISION_API_KEY,
            base_url=settings.LLM_VISION_ENDPOINT,
            timeout=180,
        )
    return _vision_client


def _resize_for_vision(
    photo_bytes: bytes, mime: str, max_side: int = 1280
) -> tuple[bytes, str]:
    """发送前压缩/缩放图片，避免超大图片导致视觉模型返回空。

    返回 (bytes, mime)。任何异常都回退为原始字节，不抛出。
    """
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(photo_bytes))
        if img.width > max_side or img.height > max_side:
            img.thumbnail((max_side, max_side))
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.warning("图片预处理失败，使用原图: %s", e)
        return photo_bytes, mime


async def describe_image(photo_bytes: bytes, mime: str = "image/jpeg") -> str:
    """用视觉模型生成图片的一句话中文描述。

    未配置 vision key 或调用失败时返回空串，不抛异常。

    Args:
        photo_bytes: 图片文件字节
        mime: 图片 MIME 类型，如 image/png

    Returns:
        图片内容的中文描述；失败为空串
    """
    import base64

    if not settings.LLM_VISION_API_KEY:
        logger.warning("未配置 LLM_VISION_API_KEY，跳过图片描述")
        return ""

    payload_bytes, payload_mime = _resize_for_vision(photo_bytes, mime)
    data_url = f"data:{payload_mime};base64,{base64.b64encode(payload_bytes).decode()}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "用一句中文描述这张照片里的内容，只输出描述本身，不要加引号。"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    try:
        response = await _get_vision_client().chat.completions.create(
            model=settings.LLM_VISION_MODEL,
            messages=messages,
            max_tokens=300,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            logger.warning("图片描述返回为空 (model=%s, image_bytes=%d)", settings.LLM_VISION_MODEL, len(photo_bytes))
        return content
    except Exception as e:
        logger.error("图片描述生成失败: %s", e)
        return ""
