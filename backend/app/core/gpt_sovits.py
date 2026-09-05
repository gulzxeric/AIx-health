import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TTSError(Exception):
    """GPT-SoVITS 调用失败"""


def map_language(language: str | None) -> str:
    """zh-CN -> zh；en* -> en；其余按 zh（MVP 仅 zh/en）"""
    lang = (language or "zh").lower()
    if lang.startswith("en"):
        return "en"
    return "zh"


def build_payload(text, text_lang, ref_audio_path, prompt_text, prompt_lang,
                  speed_factor) -> dict:
    """构造 GPT-SoVITS api_v2 POST /tts 的 JSON body"""
    return {
        "text": text,
        "text_lang": map_language(text_lang),
        "ref_audio_path": ref_audio_path,
        "prompt_text": prompt_text or "",
        "prompt_lang": map_language(prompt_lang),
        "speed_factor": speed_factor if speed_factor else settings.TTS_DEFAULT_SPEED,
        "text_split_method": "cut5",
        "media_type": "wav",
        "streaming_mode": False,
    }


async def _post_tts(payload: dict) -> httpx.Response:
    async with httpx.AsyncClient(timeout=settings.TTS_TIMEOUT) as client:
        return await client.post(f"{settings.TTS_ENDPOINT}/tts", json=payload)


async def synthesize(
    text: str,
    text_lang: str,
    ref_audio_path: str,
    prompt_text: str,
    prompt_lang: str,
    speed_factor: float | None = None,
) -> bytes:
    """调用 GPT-SoVITS /tts 合成，返回 wav 字节。失败抛 TTSError。"""
    payload = build_payload(text, text_lang, ref_audio_path, prompt_text,
                            prompt_lang, speed_factor)
    try:
        resp = await _post_tts(payload)
    except httpx.HTTPError as e:
        logger.error("GPT-SoVITS 连接失败: %s", e)
        raise TTSError("GPT-SoVITS 服务不可用") from e

    if resp.status_code != 200:
        logger.error("GPT-SoVITS 返回 %s: %s", resp.status_code, resp.text[:300])
        raise TTSError(f"GPT-SoVITS 返回 {resp.status_code}")
    return resp.content
