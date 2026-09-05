import io
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from starlette.datastructures import Headers, UploadFile

import app.api.v1.personas as personas_mod
from app.models.persona import Persona


def _upload():
    # starlette UploadFile 无 content_type 参数，经 headers 提供
    return UploadFile(
        file=io.BytesIO(b"AUDIO"),
        filename="a.webm",
        headers=Headers({"content-type": "audio/webm"}),
    )


class _FakeExec:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeDB:
    def __init__(self, results):
        self.results = list(results)
        self.commits = 0

    async def execute(self, stmt):
        return _FakeExec(self.results.pop(0))

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        pass


def _persona():
    # id/created_at 为 DB server_default，内存构造时需显式提供（FakeDB.refresh 不回填）
    return Persona(
        id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        name="阿珍",
        relation="老伴",
        voice_cloned=False,
        created_at=datetime.now(timezone.utc),
    )


async def test_upload_voice_cloned(monkeypatch):
    persona = _persona()
    db = _FakeDB([persona])

    async def fake_upload(patient_id, file_bytes, filename, content_type="audio/webm"):
        return "/voice/x/audio/a.webm"

    async def fake_clone(pid, url):
        return {"ok": True, "prompt_text": "你好，我是阿珍",
                "prompt_language": "zh", "ref_audio_path": "x", "duration": 5.0}

    monkeypatch.setattr(personas_mod, "upload_audio", fake_upload)
    monkeypatch.setattr(personas_mod, "trigger_voice_clone", fake_clone)

    resp = await personas_mod.upload_voice_sample(persona.id, _upload(), db=db)

    assert persona.voice_cloned is True
    assert persona.voice_clone_cfg["prompt_text"] == "你好，我是阿珍"
    assert resp.voice_cloned is True
    assert db.commits == 1


async def test_upload_voice_clone_failed(monkeypatch):
    persona = _persona()
    db = _FakeDB([persona])

    async def fake_upload(patient_id, file_bytes, filename, content_type="audio/webm"):
        return "/voice/x/audio/a.webm"

    async def fake_clone(pid, url):
        return {"ok": False, "error": "样本时长 0.4s 不在 1~30s 范围"}

    monkeypatch.setattr(personas_mod, "upload_audio", fake_upload)
    monkeypatch.setattr(personas_mod, "trigger_voice_clone", fake_clone)

    resp = await personas_mod.upload_voice_sample(persona.id, _upload(), db=db)

    assert persona.voice_cloned is False
    assert persona.voice_clone_cfg["ok"] is False
    assert "时长" in persona.voice_clone_cfg["error"]
