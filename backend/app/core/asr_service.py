import logging

logger = logging.getLogger(__name__)


async def speech_to_text(audio_file: bytes, language: str = "zh-CN") -> str:
    """语音转文字

    当前返回占位文本，后续接入 FunASR / Whisper。

    Args:
        audio_file: 音频文件字节数据
        language: 语言代码，默认 zh-CN

    Returns:
        转写的文本内容
    """
    logger.info("ASR 服务被调用 (占位模式): language=%s, audio_size=%d bytes", language, len(audio_file))
    return "(语音转写占位)"
