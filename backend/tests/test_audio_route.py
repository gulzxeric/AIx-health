import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.audio import router as audio_router


def _app():
    app = FastAPI()
    app.include_router(audio_router, prefix="/api/v1")
    return app


def test_transcribe_ok(monkeypatch):
    import app.api.v1.audio as audio_mod

    async def fake_stt(audio, language="zh"):
        assert language == "zh"
        return "我爸在广州造船厂上班"

    monkeypatch.setattr(audio_mod, "speech_to_text", fake_stt)
    client = TestClient(_app())
    r = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("a.webm", b"BYTES", "audio/webm")},
        data={"language": "zh"},
    )
    assert r.status_code == 200
    assert r.json()["text"] == "我爸在广州造船厂上班"


def test_transcribe_asr_down(monkeypatch):
    import app.api.v1.audio as audio_mod

    async def boom(audio, language="zh"):
        raise audio_mod.ASRError("ASR 服务不可用")

    monkeypatch.setattr(audio_mod, "speech_to_text", boom)
    client = TestClient(_app())
    r = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("a.webm", b"BYTES", "audio/webm")},
    )
    assert r.status_code == 503
    assert "不可用" in r.json()["detail"]


@pytest.mark.asyncio
async def test_speech_to_text_service_down(monkeypatch):
    from app.config import settings
    from app.core.asr_service import ASRError, speech_to_text

    monkeypatch.setattr(settings, "ASR_ENDPOINT", "http://127.0.0.1:1")
    monkeypatch.setattr(settings, "ASR_TIMEOUT", 1.0)
    with pytest.raises(ASRError):
        await speech_to_text(b"x")
