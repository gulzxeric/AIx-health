import logging
import uuid
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.core.audio_utils import ensure_reference_wav
from app.core.gpt_sovits import TTSError, synthesize
from app.core.minio_service import get_presigned_url, upload_audio

logger = logging.getLogger(__name__)


async def synthesize_speech(
    text: str,
    language: str,
    patient_id: UUID,
    voice: str = "default",
    persona_id: UUID | None = None,
    ref_audio_url: str | None = None,
    ref_text: str | None = None,
) -> str | None:
    """合成语音 -> MinIO -> presigned URL；任何失败返回 None（不阻断对话）。

    voice="default"  用默认参考音（DEFAULT_VOICE_REF，须已放置）
    voice="persona"  用克隆参考音（persona_id + ref_audio_url + ref_text）
    """
    if not text.strip():
        return None
    try:
        if voice == "persona" and persona_id is not None and ref_audio_url:
            ref_path = await ensure_reference_wav(persona_id, ref_audio_url)
            prompt_text = ref_text or ""
        else:
            ref_path = settings.default_voice_ref
            if not Path(ref_path).exists():
                logger.warning("默认音色未配置（%s 不存在），跳过 TTS", ref_path)
                return None
            # prompt 文本：env 优先，其次同名 default.prompt.txt
            prompt_text = settings.DEFAULT_VOICE_REF_TEXT
            if not prompt_text:
                prompt_file = ref_path.with_name(ref_path.stem + ".prompt.txt")
                if prompt_file.exists():
                    prompt_text = prompt_file.read_text(encoding="utf-8").strip()

        wav = await synthesize(
            text=text,
            text_lang=language,
            ref_audio_path=str(ref_path),
            prompt_text=prompt_text,
            prompt_lang=language,
        )
        filename = f"tts-{uuid.uuid4()}.wav"
        object_url = await upload_audio(
            patient_id, wav, filename, content_type="audio/wav",
        )
        return await get_presigned_url(object_url, expires=3600)
    except TTSError as e:
        logger.error("TTS 合成失败: %s", e)
        return None
    except Exception as e:
        logger.error("TTS 流程异常: %s", e, exc_info=True)
        return None
