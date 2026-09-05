from fastapi.testclient import TestClient

import asr_server
import audio_utils


def test_health_ok():
    client = TestClient(asr_server.app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_asr_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(asr_server, "ffmpeg_available", lambda: False)
    client = TestClient(asr_server.app)
    r = client.post("/asr", files={"file": ("a.webm", b"X", "audio/webm")})
    assert r.status_code == 503


def test_asr_bad_audio(monkeypatch):
    monkeypatch.setattr(asr_server, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(asr_server, "convert_to_wav",
                        lambda *a, **k: (_ for _ in ()).throw(
                            audio_utils.AudioConversionError("bad")))
    client = TestClient(asr_server.app)
    r = client.post("/asr", files={"file": ("a.webm", b"X", "audio/webm")})
    assert r.status_code == 400


def test_clean_text():
    assert asr_server._clean_text("<|zh|><|NEUTRAL|>你好呀<|en|>") == "你好呀"


def test_wav_duration(tmp_path):
    import wave
    p = tmp_path / "a.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)
    assert abs(audio_utils.wav_duration(p) - 1.0) < 0.01
