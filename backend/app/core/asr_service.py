import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class ASRError(Exception):
    """ASR 服务调用失败"""


async def speech_to_text(audio_file: bytes, language: str = "zh") -> str:
    """调用旁路 ASR 服务（SenseVoice）转写音频。

    Args:
        audio_file: 音频字节（webm/wav 等 ffmpeg 可解码格式）
        language: zh / en / auto

    Returns:
        转写文本（可能为空字符串，表示没识别到内容）

    Raises:
        ASRError: 服务不可用 / 超时 / 非 200
    """
    try:
        async with httpx.AsyncClient(timeout=settings.ASR_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.ASR_ENDPOINT}/asr",
                files={"file": ("audio.webm", audio_file, "application/octet-stream")},
                data={"language": language},
            )
    except httpx.HTTPError as e:
        logger.error("ASR 服务连接失败: %s", e)
        raise ASRError("ASR 服务不可用") from e

    if resp.status_code != 200:
        logger.error("ASR 服务返回 %s: %s", resp.status_code, resp.text[:200])
        raise ASRError(f"ASR 服务返回 {resp.status_code}")

    text = (resp.json().get("text") or "").strip()
    if not text:
        logger.info("ASR 未识别到内容（返回空文本）")
    return text
