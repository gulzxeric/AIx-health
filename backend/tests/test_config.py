def test_settings_defaults():
    from app.config import Settings

    s = Settings(
        DATABASE_URL="x", MINIO_ENDPOINT="x", MINIO_ACCESS_KEY="x",
        MINIO_SECRET_KEY="x", JWT_SECRET_KEY="x", LLM_ENDPOINT="x",
        LLM_API_KEY="x", LLM_MODEL="x", LLM_PROVIDER="x",
    )
    assert s.ASR_ENDPOINT == "http://localhost:8200"
    assert s.TTS_ENDPOINT == "http://localhost:8300"
    assert s.TTS_DEFAULT_SPEED == 0.85
    assert s.voice_runtime_dir.name == "voice-runtime"
    assert s.default_voice_ref.name == "default.wav"


def test_voice_runtime_dir_override(tmp_path):
    from app.config import Settings

    s = Settings(
        DATABASE_URL="x", MINIO_ENDPOINT="x", MINIO_ACCESS_KEY="x",
        MINIO_SECRET_KEY="x", JWT_SECRET_KEY="x", LLM_ENDPOINT="x",
        LLM_API_KEY="x", LLM_MODEL="x", LLM_PROVIDER="x",
        VOICE_RUNTIME_DIR=str(tmp_path),
    )
    assert s.voice_runtime_dir == tmp_path.resolve()
