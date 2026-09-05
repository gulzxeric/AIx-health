import io
import uuid

import app.core.minio_service as ms


async def test_upload_audio_wraps_bytesio(monkeypatch):
    calls = {}

    def fake_put(bucket, obj, data, length, content_type=None):
        calls.update(bucket=bucket, obj=obj, data=data,
                     length=length, ct=content_type)

    monkeypatch.setattr(ms.minio_client, "put_object", fake_put)
    url = await ms.upload_audio(
        uuid.uuid4(), b"12345", "a.wav", content_type="audio/wav",
    )
    assert isinstance(calls["data"], io.BytesIO)
    assert calls["length"] == 5
    assert calls["ct"] == "audio/wav"
    assert url.startswith("/voice/")
    assert "/audio/" in url
