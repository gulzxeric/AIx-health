"""声音克隆（参考音频即克隆 MVP）

流程：下载样本 -> ffmpeg 转 24k wav -> ASR 转写得 prompt_text -> 校验时长
     -> 缓存到 voice-runtime/refs/{persona_id}.wav -> 返回 cfg dict
不产生新模型文件；GPT-SoVITS 推理时按参考音频 + prompt_text 使用该音色。
"""
import logging
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.core.asr_service import ASRError, speech_to_text
from app.core.audio_utils import (
    AudioConversionError,
    convert_to_wav,
    download_object,
)

logger = logging.getLogger(__name__)

MIN_SAMPLE_SECONDS = 1.0
MAX_SAMPLE_SECONDS = 30.0


def _detect_language(text: str) -> str:
    """简单启发式：ASCII 占比高判 en，否则 zh"""
    if not text:
        return "zh"
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return "en" if ascii_chars / len(text) > 0.6 else "zh"


async def trigger_voice_clone(persona_id: uuid.UUID, voice_sample_url: str) -> dict:
    """注册参考音色。返回 cfg dict（见模块 docstring / Task 接口）。"""
    try:
        data = await download_object(voice_sample_url)
    except Exception as e:
        logger.error("语音样本下载失败: %s", e)
        return {"ok": False, "error": f"语音样本下载失败: {e}"}

    try:
        wav, duration = await convert_to_wav(data, sample_rate=24000)
    except AudioConversionError as e:
        logger.error("样本转码失败: %s", e)
        return {"ok": False, "error": f"音频转换失败（ffmpeg）: {e}"}

    if duration < MIN_SAMPLE_SECONDS or duration > MAX_SAMPLE_SECONDS:
        msg = f"样本时长 {duration:.1f}s 不在 1~30s 范围"
        logger.warning(msg)
        return {"ok": False, "error": msg}

    refs_dir = settings.voice_runtime_dir / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    wav_path = refs_dir / f"{persona_id}.wav"
    wav_path.write_bytes(wav)

    try:
        prompt_text = await speech_to_text(wav, language="auto")
    except ASRError as e:
        logger.error("样本转写失败: %s", e)
        return {"ok": False, "error": f"样本转写失败: {e}"}

    if not prompt_text:
        return {"ok": False, "error": "样本转写结果为空，请上传含清晰人声的样本"}

    cfg = {
        "ok": True,
        "prompt_text": prompt_text,
        "prompt_language": _detect_language(prompt_text),
        "ref_audio_path": str(wav_path),
        "duration": round(duration, 3),
        "cloned_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("声音克隆注册成功: persona_id=%s, duration=%.1fs", persona_id, duration)
    return cfg
