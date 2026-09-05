import uuid
from types import SimpleNamespace

import pytest

import app.core.tts_service as tts
from app.core import gpt_sovits


def test_map_language():
    assert gpt_sovits.map_language("zh-CN") == "zh"
    assert gpt_sovits.map_language("en") == "en"
    assert gpt_sovits.map_language("en-US") == "en"
    assert gpt_sovits.map_language("yue") == "zh"
    assert gpt_sovits.map_language(None) == "zh"


def test_build_payload():
    p = gpt_sovits.build_payload(
        "你好", "zh-CN", "C:/refs/a.wav", "我是阿珍", "zh-CN", None,
    )
    assert p == {
        "text": "你好",
        "text_lang": "zh",
        "ref_audio_path": "C:/refs/a.wav",
        "prompt_text": "我是阿珍",
        "prompt_lang": "zh",
        "speed_factor": 0.85,
        "text_split_method": "cut5",
        "media_type": "wav",
        "streaming_mode": False,
    }


async def test_synthesize_http_error_raises_tts_error(monkeypatch):
    import httpx

    async def raise_conn(*a, **k):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(gpt_sovits, "_post_tts", raise_conn)
    with pytest.raises(gpt_sovits.TTSError):
        await gpt_sovits.synthesize("t", "zh", "r.wav", "p", "zh")


async def test_synthesize_400_raises_tts_error(monkeypatch):
    import httpx

    resp = httpx.Response(
        400, text="err",
        request=httpx.Request("POST", "http://x/tts"),
    )

    async def fake_post(payload):
        return resp

    monkeypatch.setattr(gpt_sovits, "_post_tts", fake_post)
    with pytest.raises(gpt_sovits.TTSError):
        await gpt_sovits.synthesize("t", "zh", "r.wav", "p", "zh")


async def test_tts_default_missing_returns_none(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "DEFAULT_VOICE_REF", str(tmp_path / "none.wav"))
    assert await tts.synthesize_speech("你好", "zh-CN", uuid.uuid4()) is None


async def test_tts_default_success(monkeypatch, tmp_path):
    from app.config import settings

    ref = tmp_path / "default.wav"
    ref.write_bytes(b"RIFF")
    monkeypatch.setattr(settings, "DEFAULT_VOICE_REF", str(ref))
    monkeypatch.setattr(settings, "DEFAULT_VOICE_REF_TEXT", "你好呀")

    captured = {}

    async def fake_synthesize(text, text_lang, ref_audio_path, prompt_text,
                              prompt_lang, speed_factor=None):
        captured.update(text=text, ref=str(ref_audio_path), prompt=prompt_text)
        return b"WAVBYTES"

    async def fake_upload(patient_id, file_bytes, filename, content_type="audio/webm"):
        assert file_bytes == b"WAVBYTES"
        assert content_type == "audio/wav"
        return "/voice/x/tts/a.wav"

    async def fake_presign(url, expires=3600):
        return "http://minio/voice/x/tts/a.wav?sig=1"

    monkeypatch.setattr(tts, "synthesize", fake_synthesize)
    monkeypatch.setattr(tts, "upload_audio", fake_upload)
    monkeypatch.setattr(tts, "get_presigned_url", fake_presign)

    url = await tts.synthesize_speech("今天天气不错", "zh-CN", uuid.uuid4())
    assert url == "http://minio/voice/x/tts/a.wav?sig=1"
    assert captured["prompt"] == "你好呀"
