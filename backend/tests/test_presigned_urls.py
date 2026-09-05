"""照片 URL 签名：后端返回的 photo_url/object_url 必须是浏览器可直接加载的地址。

根因：返回的是 MinIO 对象路径（/memories/...），前端 <img> 把它当相对路径打到
页面源（Live Server :8081）上必然 404。修复 = 响应中签名成 presigned URL。
"""
import uuid
from datetime import datetime, timezone

import app.api.v1.memories as memories_mod
import app.api.v1.photos as photos_mod
from app.models.memory import Memory
from app.models.photo import Photo


class _FakeResult:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _SeqDB:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, stmt):
        return self.results.pop(0)


def _now():
    return datetime.now(timezone.utc)


def _memory(photo_url):
    m = Memory(
        patient_id=uuid.uuid4(),
        caregiver_id=uuid.uuid4(),
        raw_text="测试记忆",
        photo_url=photo_url,
        entities={},
        sync_status="synced",
    )
    m.id = uuid.uuid4()
    m.created_at = _now()
    m.updated_at = _now()
    return m


async def test_list_memories_presigns_relative_photo(monkeypatch):
    async def fake_presign(url, expires=3600):
        assert url == "/memories/x/a.jpg"
        return "http://minio/signed/x/a.jpg"

    monkeypatch.setattr(memories_mod, "get_presigned_url", fake_presign)
    m = _memory("/memories/x/a.jpg")
    db = _SeqDB([_FakeResult(scalar=1), _FakeResult(rows=[m])])

    resp = await memories_mod.list_memories(
        patient_id=m.patient_id, tag=None, page=1, page_size=20, db=db,
    )
    assert resp.memories[0].photo_url == "http://minio/signed/x/a.jpg"


async def test_list_memories_keeps_external_url(monkeypatch):
    called = []

    async def fake_presign(url, expires=3600):
        called.append(url)
        return "http://minio/signed"

    monkeypatch.setattr(memories_mod, "get_presigned_url", fake_presign)
    m = _memory("http://example.com/1.jpg")
    db = _SeqDB([_FakeResult(scalar=1), _FakeResult(rows=[m])])

    resp = await memories_mod.list_memories(
        patient_id=m.patient_id, tag=None, page=1, page_size=20, db=db,
    )
    assert resp.memories[0].photo_url == "http://example.com/1.jpg"
    assert called == []


async def test_photos_list_presigns(monkeypatch):
    async def fake_presign(url, expires=3600):
        return "http://minio/signed" + url

    monkeypatch.setattr(photos_mod, "get_presigned_url", fake_presign)
    p = Photo(
        patient_id=uuid.uuid4(),
        uploaded_by=uuid.uuid4(),
        object_url="/memories/x/p.jpg",
        thumbnail_url=None,
        persona_name="阿珍",
        persona_relation="老伴",
    )
    p.id = uuid.uuid4()
    p.created_at = _now()
    db = _SeqDB([_FakeResult(rows=[p])])

    resp = await photos_mod.get_photos(patient_id=p.patient_id, db=db)
    assert resp[0].object_url == "http://minio/signed/memories/x/p.jpg"
