async def synthesize_speech(
    text: str,
    language: str,
    voice: str = "default",
) -> str | None:
    """TTS 语音合成

    当前返回 None（占位），后续接入 Coqui TTS / GPT-SoVITS。

    Args:
        text: 待合成文本
        language: 语言代码（zh-CN / en）
        voice: 音色标识（default / 克隆音色 ID）

    Returns:
        合成音频的 URL，暂返回 None
    """
    # TODO: 接入真实 TTS 服务
    _ = text, language, voice  # suppress unused warnings
    return None
