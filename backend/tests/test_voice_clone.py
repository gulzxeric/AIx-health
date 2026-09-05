import uuid

import app.core.voice_clone as vc


async def test_clone_ok(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "VOICE_RUNTIME_DIR", str(tmp_path))

    async def fake_download(url):
        return b"RAW"

    async def fake_convert(data, sample_rate, channel_count=1):
        return b"WAV", 5.2

    async def fake_stt(audio, language="zh"):
        return "你好，我是阿珍"

    monkeypatch.setattr(vc, "download_object", fake_download)
    monkeypatch.setattr(vc, "convert_to_wav", fake_convert)
    monkeypatch.setattr(vc, "speech_to_text", fake_stt)

    pid = uuid.uuid4()
    cfg = await vc.trigger_voice_clone(pid, "/voice/x/audio/a.webm")

    assert cfg["ok"] is True
    assert cfg["prompt_text"] == "你好，我是阿珍"
    assert cfg["prompt_language"] == "zh"
    assert cfg["duration"] == 5.2
    assert (tmp_path / "refs" / f"{pid}.wav").exists()


async def test_clone_too_short(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "VOICE_RUNTIME_DIR", str(tmp_path))

    async def fake_download(url):
        return b"RAW"

    async def fake_convert(data, sample_rate, channel_count=1):
        return b"WAV", 0.4

    monkeypatch.setattr(vc, "download_object", fake_download)
    monkeypatch.setattr(vc, "convert_to_wav", fake_convert)

    cfg = await vc.trigger_voice_clone(uuid.uuid4(), "/voice/x/audio/a.webm")
    assert cfg["ok"] is False
    assert "时长" in cfg["error"]


async def test_clone_english_sample(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "VOICE_RUNTIME_DIR", str(tmp_path))

    async def fake_download(url):
        return b"RAW"

    async def fake_convert(data, sample_rate, channel_count=1):
        return b"WAV", 6.0

    async def fake_stt(audio, language="zh"):
        return "Hello, it is me"

    monkeypatch.setattr(vc, "download_object", fake_download)
    monkeypatch.setattr(vc, "convert_to_wav", fake_convert)
    monkeypatch.setattr(vc, "speech_to_text", fake_stt)

    cfg = await vc.trigger_voice_clone(uuid.uuid4(), "/voice/x/audio/a.webm")
    assert cfg["ok"] is True
    assert cfg["prompt_language"] == "en"


async def test_clone_asr_fails(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "VOICE_RUNTIME_DIR", str(tmp_path))

    async def fake_download(url):
        return b"RAW"

    async def fake_convert(data, sample_rate, channel_count=1):
        return b"WAV", 5.0

    from app.core.asr_service import ASRError

    async def fake_stt(audio, language="zh"):
        raise ASRError("ASR 服务不可用")

    monkeypatch.setattr(vc, "download_object", fake_download)
    monkeypatch.setattr(vc, "convert_to_wav", fake_convert)
    monkeypatch.setattr(vc, "speech_to_text", fake_stt)

    cfg = await vc.trigger_voice_clone(uuid.uuid4(), "/voice/x/audio/a.webm")
    assert cfg["ok"] is False
    assert "转写失败" in cfg["error"]
