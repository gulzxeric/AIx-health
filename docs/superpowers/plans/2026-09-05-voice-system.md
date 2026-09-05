# 语音系统落地 Implementation Plan

**Goal:** 将 ASR/TTS/声音克隆从占位落地为真实可用的语音闭环，覆盖家属端语音录记忆、患者端语音对话、人物库克隆音色。

**Architecture:** 旁路 HTTP 微服务架构（voice-services/ 目录独立环境）——后端通过 httpx 调用 ASR_ENDPOINT:8200 / TTS_ENDPOINT:8300。患者端实时 VAD 录音，照片亲人对话传 photo_id 触发克隆音色。

**Tech Stack:** FastAPI / funasr SenseVoiceSmall / GPT-SoVITS api_v2 / 原生 JS ES5 / pytest + pytest-asyncio。

**Spec:** `docs/superpowers/specs/2026-09-05-fix-photo-caption-voice-design.md` 第 3.2~3.5 节。

## Global Constraints

- 后端工作目录 `backend/`，测试 `python -m pytest tests -v`；voice-services 独立 venv。
- pytest.ini `asyncio_mode = auto`
- 端口：backend :8000、ASR :8200、GPT-SoVITS :8300。
- JS 一律 ES5（`var`/`function`），2 空格缩进，无构建。
- 提交风格：`feat:/fix:/docs:` + 中文摘要。
- 外部依赖：ffmpeg（PATH 里）、GPT-SoVITS 官方仓库自行克隆安装、default.wav 用户放置到 `voice-runtime/refs/`。

---

### Task 1: 配置默认值 + 测试基础设施

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/.env.example`
- Modify: `backend/.env.example`? (root .env.example)
- Modify: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Create: `backend/tests/conftest.py`

**Interfaces:**
- Produces: `settings.voice_runtime_dir` (Path property)、`settings.default_voice_ref` (Path property)、`settings.ASR_ENDPOINT`/`TTS_ENDPOINT` 有默认值不崩溃、`settings.ASR_TIMEOUT`/`TTS_TIMEOUT`/`TTS_DEFAULT_SPEED`

- [ ] **Step 1: config.py 加默认值与属性**

```python
# ASR/TTS
ASR_ENDPOINT: str = "http://localhost:8200"
TTS_ENDPOINT: str = "http://localhost:8300"
ASR_TIMEOUT: float = 30.0
TTS_TIMEOUT: float = 30.0
TTS_DEFAULT_SPEED: float = 0.85

# 语音运行时目录与默认音色
VOICE_RUNTIME_DIR: str = ""
DEFAULT_VOICE_REF: str = ""
DEFAULT_VOICE_REF_TEXT: str = ""
```

在 `Settings` 类 `model_config` 之前加属性：

```python
@property
def voice_runtime_dir(self) -> Path:
    """返回 voice-runtime 绝对路径（仓库根）"""
    from pathlib import Path
    if self.VOICE_RUNTIME_DIR:
        return Path(self.VOICE_RUNTIME_DIR).resolve()
    return Path(__file__).resolve().parent.parent.parent / "voice-runtime"

@property
def default_voice_ref(self) -> Path:
    """默认音色参考音频路径"""
    if self.DEFAULT_VOICE_REF:
        return Path(self.DEFAULT_VOICE_REF)
    return self.voice_runtime_dir / "refs" / "default.wav"
```

- [ ] **Step 2: 创建 backend/.env.example（补全所有键）**

```env
DATABASE_URL=postgresql+asyncpg://retinaecho:retinaecho_dev@localhost:5432/retinaecho

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_MEMORIES=memories
MINIO_BUCKET_VOICE=voice
MINIO_BUCKET_AVATARS=avatars
MINIO_BUCKET_ASSETS=asset-packs

JWT_SECRET_KEY=change-this-to-a-random-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=30

LLM_ENDPOINT=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-api-key
LLM_MODEL=deepseek-chat
LLM_PROVIDER=deepseek

LLM_VISION_ENDPOINT=https://api.openai-next.com/v1
LLM_VISION_API_KEY=sk-your-vision-key
LLM_VISION_MODEL=deepseek-v4-flash-vision-exp

ASR_ENDPOINT=http://localhost:8200
TTS_ENDPOINT=http://localhost:8300
ASR_TIMEOUT=30
TTS_TIMEOUT=30
TTS_DEFAULT_SPEED=0.85

VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_CONTACT=admin@example.com

SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

- [ ] **Step 3: 根 .env.example 替换为与 backend/.env.example 相同内容**

```bash
cp backend/.env.example .env.example
```

- [ ] **Step 4: requirements.txt 末尾追加**

```
pytest
pytest-asyncio
```

- [ ] **Step 5: pytest.ini**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 6: tests/conftest.py**

```python
import os

# 在应用模块导入前设好环境变量默认值
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/t")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("LLM_ENDPOINT", "https://api.test/v1")
os.environ.setdefault("LLM_API_KEY", "sk-test")
os.environ.setdefault("LLM_MODEL", "test-model")
os.environ.setdefault("LLM_PROVIDER", "test")
```

- [ ] **Step 7: 写失败测试 `tests/test_config.py`**

```python
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
```

- [ ] **Step 8: 运行测试**

```bash
cd backend && python -m pytest tests/test_config.py -v
```

预期：PASS（config 改动同任务内完成；如先写测试则 FAIL 于属性缺失）。

- [ ] **Step 9: Commit**

```bash
git add backend/app/config.py backend/.env.example .env.example backend/requirements.txt backend/pytest.ini backend/tests/conftest.py backend/tests/test_config.py
git commit -m "feat: 语音配置默认值与测试基础设施（ASR/TTS端点、voice-runtime目录）"
```

---

### Task 2: voice-services ASR 微服务（SenseVoice）

**Files:**
- Create: `voice-services/asr_server.py`
- Create: `voice-services/audio_utils.py`
- Create: `voice-services/requirements-asr.txt`
- Create: `voice-services/test_asr_server.py`

**Interfaces:**
- Produces: `POST /asr`（multipart `file` + form `language=zh|en|auto`）→ `{"text", "language", "duration"}`；`GET /health` → `{"status":"ok","ffmpeg":bool,"model_loaded":bool}`。Task 3 的 `speech_to_text` 按此契约调用。

- [ ] **Step 1: requirements-asr.txt**

```
fastapi
uvicorn
python-multipart
funasr
torch
torchaudio
modelscope
numpy
pytest
httpx
```

- [ ] **Step 2: audio_utils.py**

```python
"""ffmpeg 音频归一化工具（voice-services 独立用，不依赖 backend）"""
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path


class AudioConversionError(Exception):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate() or 1)


def convert_to_wav(data: bytes, sample_rate: int = 16000, channel_count: int = 1):
    """任意 ffmpeg 可解码音频 -> wav PCM s16le；返回 (wav_bytes, duration_seconds)"""
    if not ffmpeg_available():
        raise AudioConversionError("ffmpeg 未安装或不在 PATH")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.bin"
        out = Path(td) / "out.wav"
        src.write_bytes(data)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-ar", str(sample_rate),
             "-ac", str(channel_count), "-sample_fmt", "s16", str(out)],
            capture_output=True, timeout=60,
        )
        if proc.returncode != 0 or not out.exists():
            raise AudioConversionError(proc.stderr.decode("utf-8", "ignore")[-300:])
        return out.read_bytes(), wav_duration(out)
```

- [ ] **Step 3: asr_server.py**

```python
"""AIx-Health ASR 微服务（SenseVoiceSmall，懒加载，端口 8200）

启动: python asr_server.py   (或 ASR_PORT/ASR_HOST/ASR_DEVICE 环境变量覆盖)
"""
import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from audio_utils import AudioConversionError, convert_to_wav, ffmpeg_available

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("asr_server")

app = FastAPI(title="AIx-Health ASR Server (SenseVoice)")

_model = None
_model_lock = asyncio.Lock()


def _load_model():
    from funasr import AutoModel
    return AutoModel(
        model="iic/SenseVoiceSmall",
        trust_remote_code=True,
        remote_code="./model.pt",
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device=os.environ.get("ASR_DEVICE", "cpu"),
        disable_update=True,
    )


def _infer(wav_bytes: bytes, language: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        p = Path(f.name)
    try:
        res = _model.generate(
            input=str(p), cache={}, language=language, use_itn=True,
            batch_size_s=60, merge_vad=True, merge_length_s=15,
        )
        return res[0]["text"]
    finally:
        p.unlink(missing_ok=True)


def _clean_text(text: str) -> str:
    return re.sub(r"<\|[^|]+\|>", "", text or "").strip()


@app.get("/health")
async def health():
    return {"status": "ok", "ffmpeg": ffmpeg_available(), "model_loaded": _model is not None}


@app.post("/asr")
async def asr(file: UploadFile = File(...), language: str = Form("auto")):
    if not ffmpeg_available():
        return JSONResponse(status_code=503, content={"detail": "ffmpeg 未安装或不在 PATH"})
    if language not in ("zh", "en", "auto"):
        language = "auto"
    data = await file.read()
    try:
        wav, duration = convert_to_wav(data, sample_rate=16000)
    except AudioConversionError as e:
        return JSONResponse(status_code=400, content={"detail": f"音频转换失败: {e}"})

    global _model
    async with _model_lock:
        if _model is None:
            logger.info("首次请求，加载 SenseVoiceSmall ...")
            _model = await asyncio.to_thread(_load_model)
            logger.info("模型加载完成")
        raw = await asyncio.to_thread(_infer, wav, language)

    return {"text": _clean_text(raw), "language": language, "duration": round(duration, 3)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("ASR_HOST", "127.0.0.1"),
                port=int(os.environ.get("ASR_PORT", "8200")))
```

- [ ] **Step 4: test_asr_server.py**

```python
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
```

- [ ] **Step 5: 独立 venv 安装并跑测试**

```bash
cd voice-services
python -m venv .venv
.venv\Scripts\pip install -r requirements-asr.txt
.venv\Scripts\python -m pytest test_asr_server.py -v
```

预期：全部 PASS（不触发模型加载）。

- [ ] **Step 6: 手动冒烟（可选，首次会下载模型约 1GB）**

```bash
.venv\Scripts\python asr_server.py
# 另开终端
curl http://127.0.0.1:8200/health
```

- [ ] **Step 7: Commit**

```bash
git add voice-services/asr_server.py voice-services/audio_utils.py voice-services/requirements-asr.txt voice-services/test_asr_server.py
git commit -m "feat: ASR 微服务（funasr SenseVoiceSmall，懒加载+ffmpeg归一化）"
```

---

### Task 3: 后端 asr_service 转真 + /audio/transcribe 路由

**Files:**
- Modify: `backend/app/core/asr_service.py`（整体重写）
- Create: `backend/app/api/v1/audio.py`
- Modify: `backend/app/main.py`（挂载路由）
- Test: `backend/tests/test_audio_route.py`

**Interfaces:**
- Consumes: Task 2 的 `POST /asr` 契约；Task 1 的 `settings.ASR_ENDPOINT/ASR_TIMEOUT`。
- Produces: `speech_to_text(audio_file: bytes, language: str = "zh") -> str`（失败抛 `ASRError`，空文本返回 ""）；`POST /api/v1/audio/transcribe` → `{"text","language"}`，服务不可用返回 503。Task 6/9/10 复用。

- [ ] **Step 1: 重写 asr_service.py**

```python
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class ASRError(Exception):
    """ASR 服务调用失败"""


async def speech_to_text(audio_file: bytes, language: str = "zh") -> str:
    """调用旁路 ASR 服务（SenseVoice）转写音频。

    Args:
        audio_file: 音频字节（webm/wav 等 ffmpeg 可解码格式）
        language: zh / en / auto

    Returns:
        转写文本（可能为空字符串，表示没识别到内容）

    Raises:
        ASRError: 服务不可用 / 超时 / 非 200
    """
    try:
        async with httpx.AsyncClient(timeout=settings.ASR_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.ASR_ENDPOINT}/asr",
                files={"file": ("audio.webm", audio_file, "application/octet-stream")},
                data={"language": language},
            )
    except httpx.HTTPError as e:
        logger.error("ASR 服务连接失败: %s", e)
        raise ASRError("ASR 服务不可用") from e

    if resp.status_code != 200:
        logger.error("ASR 服务返回 %s: %s", resp.status_code, resp.text[:200])
        raise ASRError(f"ASR 服务返回 {resp.status_code}")

    text = (resp.json().get("text") or "").strip()
    if not text:
        logger.info("ASR 未识别到内容（返回空文本）")
    return text
```

- [ ] **Step 2: 写失败测试 tests/test_audio_route.py**

```python
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
```

- [ ] **Step 3: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_audio_route.py -v
```

预期：FAIL（`app.api.v1.audio` 不存在）。

- [ ] **Step 4: 创建 api/v1/audio.py**

```python
import logging
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.asr_service import ASRError, speech_to_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["语音转写"])


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    patient_id: UUID | None = Form(None),
    language: str = Form("zh"),
):
    """音频转文字（家属端语音录记忆 / 患者端语音对话共用）"""
    audio_bytes = await file.read()
    try:
        text = await speech_to_text(audio_bytes, language=language)
    except ASRError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"text": text, "language": language}
```

- [ ] **Step 5: main.py 挂载**

在 `from app.api.v1.push import router as push_router` 之后加：

```python
from app.api.v1.audio import router as audio_router
```

在 `app.include_router(push_router, prefix="/api/v1")` 之后加：

```python
app.include_router(audio_router, prefix="/api/v1")
```

- [ ] **Step 6: 运行测试通过**

```bash
cd backend && python -m pytest tests/test_audio_route.py -v
```

预期：3 PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/asr_service.py backend/app/api/v1/audio.py backend/app/main.py backend/tests/test_audio_route.py
git commit -m "feat: asr_service 转真（httpx 调 SenseVoice 服务）+ /audio/transcribe 共用转写接口"
```

---

### Task 4: minio upload_audio BytesIO 修复

**Files:**
- Modify: `backend/app/core/minio_service.py:48-75`
- Test: `backend/tests/test_minio_audio.py`

**Interfaces:**
- Produces: `upload_audio(patient_id, file_bytes, filename, content_type="audio/webm") -> str`（BytesIO 包装 + 真实 mime）。Task 5/7 依赖。

- [ ] **Step 1: 写失败测试 tests/test_minio_audio.py**

```python
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
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_minio_audio.py -v
```

预期：FAIL（现实现把 bytes 直接传 put_object，fake 收到的不是 BytesIO）。

- [ ] **Step 3: 修改 upload_audio**

```python
async def upload_audio(
    patient_id: UUID,
    file_bytes: bytes,
    filename: str,
    content_type: str = "audio/webm",
) -> str:
    """上传音频到 MinIO，返回 object_url

    路径: {patient_id}/audio/{filename}
    """
    bucket = settings.MINIO_BUCKET_VOICE
    object_name = f"{patient_id}/audio/{filename}"

    await asyncio.to_thread(
        minio_client.put_object,
        bucket,
        object_name,
        io.BytesIO(file_bytes),
        len(file_bytes),
        content_type=content_type,
    )
    object_url = f"/{bucket}/{object_name}"
    logger.info("音频已上传到 MinIO: %s", object_url)
    return object_url
```

- [ ] **Step 4: 运行测试通过**

```bash
cd backend && python -m pytest tests/test_minio_audio.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/minio_service.py backend/tests/test_minio_audio.py
git commit -m "fix: upload_audio 用 BytesIO 包装并支持真实 content_type（修复 put_object bytes 报错）"
```

---

### Task 5: GPT-SoVITS 适配器 + tts_service 转真 + 后端 audio_utils

**Files:**
- Create: `backend/app/core/gpt_sovits.py`
- Create: `backend/app/core/audio_utils.py`
- Modify: `backend/app/core/tts_service.py`（整体重写）
- Test: `backend/tests/test_tts_service.py`

**Interfaces:**
- Consumes: Task 1 的 `settings.TTS_ENDPOINT/TTS_TIMEOUT/TTS_DEFAULT_SPEED/default_voice_ref`；Task 4 的 `upload_audio`。
- Produces:
  - `gpt_sovits.synthesize(text, text_lang, ref_audio_path, prompt_text, prompt_lang, speed_factor=None) -> bytes`（失败抛 `TTSError`）
  - `gpt_sovits.map_language(language) -> "zh"|"en"`
  - `audio_utils.ensure_reference_wav(persona_id, voice_sample_url) -> Path`（24k wav 本地缓存）
  - `tts_service.synthesize_speech(text, language, patient_id, voice="default", persona_id=None, ref_audio_url=None, ref_text=None) -> str | None`（presigned URL，失败 None）。Task 6/8 依赖。

- [ ] **Step 1: 写失败测试 tests/test_tts_service.py**

```python
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
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_tts_service.py -v
```

预期：FAIL（模块不存在）。

- [ ] **Step 3: 创建 core/gpt_sovits.py**

```python
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TTSError(Exception):
    """GPT-SoVITS 调用失败"""


def map_language(language: str | None) -> str:
    """zh-CN -> zh；en* -> en；其余按 zh（MVP 仅 zh/en）"""
    lang = (language or "zh").lower()
    if lang.startswith("en"):
        return "en"
    return "zh"


def build_payload(text, text_lang, ref_audio_path, prompt_text, prompt_lang,
                  speed_factor) -> dict:
    """构造 GPT-SoVITS api_v2 POST /tts 的 JSON body"""
    return {
        "text": text,
        "text_lang": map_language(text_lang),
        "ref_audio_path": ref_audio_path,
        "prompt_text": prompt_text or "",
        "prompt_lang": map_language(prompt_lang),
        "speed_factor": speed_factor if speed_factor else settings.TTS_DEFAULT_SPEED,
        "text_split_method": "cut5",
        "media_type": "wav",
        "streaming_mode": False,
    }


async def _post_tts(payload: dict) -> httpx.Response:
    async with httpx.AsyncClient(timeout=settings.TTS_TIMEOUT) as client:
        return await client.post(f"{settings.TTS_ENDPOINT}/tts", json=payload)


async def synthesize(
    text: str,
    text_lang: str,
    ref_audio_path: str,
    prompt_text: str,
    prompt_lang: str,
    speed_factor: float | None = None,
) -> bytes:
    """调用 GPT-SoVITS /tts 合成，返回 wav 字节。失败抛 TTSError。"""
    payload = build_payload(text, text_lang, ref_audio_path, prompt_text,
                            prompt_lang, speed_factor)
    try:
        resp = await _post_tts(payload)
    except httpx.HTTPError as e:
        logger.error("GPT-SoVITS 连接失败: %s", e)
        raise TTSError("GPT-SoVITS 服务不可用") from e

    if resp.status_code != 200:
        logger.error("GPT-SoVITS 返回 %s: %s", resp.status_code, resp.text[:300])
        raise TTSError(f"GPT-SoVITS 返回 {resp.status_code}")
    return resp.content
```

- [ ] **Step 4: 创建 core/audio_utils.py（后端用）**

```python
"""后端音频工具：ffmpeg 转码 / MinIO 下载 / 参考音频本地缓存"""
import asyncio
import logging
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from uuid import UUID

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class AudioConversionError(Exception):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _convert_sync(data: bytes, sample_rate: int, channel_count: int):
    if not ffmpeg_available():
        raise AudioConversionError("ffmpeg 未安装或不在 PATH")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.bin"
        out = Path(td) / "out.wav"
        src.write_bytes(data)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-ar", str(sample_rate),
             "-ac", str(channel_count), "-sample_fmt", "s16", str(out)],
            capture_output=True, timeout=60,
        )
        if proc.returncode != 0 or not out.exists():
            raise AudioConversionError(proc.stderr.decode("utf-8", "ignore")[-300:])
        with wave.open(str(out), "rb") as w:
            duration = w.getnframes() / float(w.getframerate() or 1)
        return out.read_bytes(), duration


async def convert_to_wav(data: bytes, sample_rate: int, channel_count: int = 1):
    """转码为 wav PCM s16le，返回 (bytes, duration_seconds)"""
    return await asyncio.to_thread(_convert_sync, data, sample_rate, channel_count)


async def download_object(object_url: str) -> bytes:
    """从 MinIO 经 presigned URL 下载对象字节"""
    from app.core.minio_service import get_presigned_url

    presigned = await get_presigned_url(object_url)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(presigned)
    resp.raise_for_status()
    return resp.content


async def ensure_reference_wav(persona_id: UUID, voice_sample_url: str) -> Path:
    """确保 voice-runtime/refs/{persona_id}.wav 存在（24k mono），缺则从 MinIO 重建"""
    refs_dir = settings.voice_runtime_dir / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    wav_path = refs_dir / f"{persona_id}.wav"
    if wav_path.exists():
        return wav_path
    data = await download_object(voice_sample_url)
    wav, _ = await convert_to_wav(data, sample_rate=24000)
    wav_path.write_bytes(wav)
    logger.info("参考音频已缓存: %s", wav_path)
    return wav_path
```

- [ ] **Step 5: 重写 core/tts_service.py**

```python
import logging
import uuid
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.core.audio_utils import ensure_reference_wav
from app.core.gpt_sovits import TTSError, synthesize
from app.core.minio_service import get_presigned_url, upload_audio

logger = logging.getLogger(__name__)


async def synthesize_speech(
    text: str,
    language: str,
    patient_id: UUID,
    voice: str = "default",
    persona_id: UUID | None = None,
    ref_audio_url: str | None = None,
    ref_text: str | None = None,
) -> str | None:
    """合成语音 -> MinIO -> presigned URL；任何失败返回 None（不阻断对话）。

    voice="default"  用默认参考音（DEFAULT_VOICE_REF，须已放置）
    voice="persona"  用克隆参考音（persona_id + ref_audio_url + ref_text）
    """
    if not text.strip():
        return None
    try:
        if voice == "persona" and persona_id is not None and ref_audio_url:
            ref_path = await ensure_reference_wav(persona_id, ref_audio_url)
            prompt_text = ref_text or ""
        else:
            ref_path = settings.default_voice_ref
            if not Path(ref_path).exists():
                logger.warning("默认音色未配置（%s 不存在），跳过 TTS", ref_path)
                return None
            # prompt 文本：env 优先，其次同名 default.prompt.txt
            prompt_text = settings.DEFAULT_VOICE_REF_TEXT
            if not prompt_text:
                prompt_file = ref_path.with_name(ref_path.stem + ".prompt.txt")
                if prompt_file.exists():
                    prompt_text = prompt_file.read_text(encoding="utf-8").strip()

        wav = await synthesize(
            text=text,
            text_lang=language,
            ref_audio_path=str(ref_path),
            prompt_text=prompt_text,
            prompt_lang=language,
        )
        filename = f"tts-{uuid.uuid4()}.wav"
        object_url = await upload_audio(
            patient_id, wav, filename, content_type="audio/wav",
        )
        return await get_presigned_url(object_url, expires=3600)
    except TTSError as e:
        logger.error("TTS 合成失败: %s", e)
        return None
    except Exception as e:
        logger.error("TTS 流程异常: %s", e, exc_info=True)
        return None
```

- [ ] **Step 6: 运行测试通过**

```bash
cd backend && python -m pytest tests/test_tts_service.py -v
```

预期：6 PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/gpt_sovits.py backend/app/core/audio_utils.py backend/app/core/tts_service.py backend/tests/test_tts_service.py
git commit -m "feat: GPT-SoVITS 适配器 + tts_service 转真（wav上MinIO+presigned，失败静默降级）"
```

---

### Task 6: voice_clone 转真（参考音频即克隆）

**Files:**
- Modify: `backend/app/core/voice_clone.py`（整体重写）
- Test: `backend/tests/test_voice_clone.py`

**Interfaces:**
- Consumes: Task 3 的 `speech_to_text`/`ASRError`；Task 5 的 `audio_utils.convert_to_wav/download_object`。
- Produces: `trigger_voice_clone(persona_id: UUID, voice_sample_url: str) -> dict`：
  - 成功 `{"ok": True, "prompt_text", "prompt_language"("zh"|"en"), "ref_audio_path", "duration", "cloned_at"}`
  - 失败 `{"ok": False, "error": "<原因>"}`
  - Task 7 将 cfg 写入 `persona.voice_clone_cfg`，`cfg["ok"]` 决定 `voice_cloned`。

- [ ] **Step 1: 写失败测试 tests/test_voice_clone.py**

```python
import uuid

import app.core.voice_clone as vc


async def test_clone_ok(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "VOICE_RUNTIME_DIR", str(tmp_path))

    async def fake_download(url):
        return b"RAW"

    def fake_convert(data, sample_rate, channel_count=1):
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

    def fake_convert(data, sample_rate, channel_count=1):
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

    def fake_convert(data, sample_rate, channel_count=1):
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

    def fake_convert(data, sample_rate, channel_count=1):
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
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_voice_clone.py -v
```

预期：FAIL（现占位实现返回 False 而非 dict）。

- [ ] **Step 3: 重写 core/voice_clone.py**

```python
"""声音克隆（参考音频即克隆 MVP）

流程：下载样本 -> ffmpeg 转 24k wav -> ASR 转写得 prompt_text -> 校验时长
     -> 缓存到 voice-runtime/refs/{persona_id}.wav -> 返回 cfg dict
不产生新模型文件；GPT-SoVITS 推理时按参考音频 + prompt_text 使用该音色。
"""
import logging
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.core.asr_service import ASRError, speech_to_text
from app.core.audio_utils import (
    AudioConversionError,
    convert_to_wav,
    download_object,
)

logger = logging.getLogger(__name__)

MIN_SAMPLE_SECONDS = 1.0
MAX_SAMPLE_SECONDS = 30.0


def _detect_language(text: str) -> str:
    """简单启发式：ASCII 占比高判 en，否则 zh"""
    if not text:
        return "zh"
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return "en" if ascii_chars / len(text) > 0.6 else "zh"


async def trigger_voice_clone(persona_id: uuid.UUID, voice_sample_url: str) -> dict:
    """注册参考音色。返回 cfg dict（见模块 docstring / Task 接口）。"""
    try:
        data = await download_object(voice_sample_url)
    except Exception as e:
        logger.error("语音样本下载失败: %s", e)
        return {"ok": False, "error": f"语音样本下载失败: {e}"}

    try:
        wav, duration = await convert_to_wav(data, sample_rate=24000)
    except AudioConversionError as e:
        logger.error("样本转码失败: %s", e)
        return {"ok": False, "error": f"音频转换失败（ffmpeg）: {e}"}

    if duration < MIN_SAMPLE_SECONDS or duration > MAX_SAMPLE_SECONDS:
        msg = f"样本时长 {duration:.1f}s 不在 1~30s 范围"
        logger.warning(msg)
        return {"ok": False, "error": msg}

    refs_dir = settings.voice_runtime_dir / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    wav_path = refs_dir / f"{persona_id}.wav"
    wav_path.write_bytes(wav)

    try:
        prompt_text = await speech_to_text(wav, language="auto")
    except ASRError as e:
        logger.error("样本转写失败: %s", e)
        return {"ok": False, "error": f"样本转写失败: {e}"}

    if not prompt_text:
        return {"ok": False, "error": "样本转写结果为空，请上传含清晰人声的样本"}

    cfg = {
        "ok": True,
        "prompt_text": prompt_text,
        "prompt_language": _detect_language(prompt_text),
        "ref_audio_path": str(wav_path),
        "duration": round(duration, 3),
        "cloned_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("声音克隆注册成功: persona_id=%s, duration=%.1fs", persona_id, duration)
    return cfg
```

- [ ] **Step 4: 运行测试通过**

```bash
cd backend && python -m pytest tests/test_voice_clone.py -v
```

预期：4 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/voice_clone.py backend/tests/test_voice_clone.py
git commit -m "feat: voice_clone 转真（参考音频注册：转码+ASR转写+时长校验+cfg）"
```

---

### Task 7: personas 语音样本端点接线

**Files:**
- Modify: `backend/app/api/v1/personas.py:78-129`（upload_voice_sample）
- Test: `backend/tests/test_personas_voice.py`

**Interfaces:**
- Consumes: Task 4 的 `upload_audio(content_type=...)`；Task 6 的 `trigger_voice_clone -> cfg dict`。
- Produces: `PUT /personas/{id}/voice` 真实克隆：成功 `voice_cloned=True` + `voice_clone_cfg=cfg`；失败记录 cfg.error 且 `voice_cloned` 保持 False。

- [ ] **Step 1: 写失败测试 tests/test_personas_voice.py**

```python
import io
import uuid
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
    return Persona(
        patient_id=uuid.uuid4(),
        name="阿珍",
        relation="老伴",
        voice_cloned=False,
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
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_personas_voice.py -v
```

预期：FAIL（现实现调用占位 trigger_voice_clone 返回 False，不写 cfg）。

- [ ] **Step 3: 修改 personas.py 的 upload_voice_sample**

替换 Step 1~3（上传/更新/触发克隆）部分为：

```python
    # Step 1: 上传语音样本至 MinIO
    try:
        audio_bytes = await voice_sample.read()
        filename = f"{persona_id}_voice_{voice_sample.filename}"
        voice_sample_url = await upload_audio(
            persona.patient_id,
            audio_bytes,
            filename,
            content_type=voice_sample.content_type or "audio/webm",
        )

        # Step 2: 更新 voice_sample_url
        persona.voice_sample_url = voice_sample_url

        # Step 3: 触发声音克隆（参考音频注册：转码+转写+校验）
        clone_cfg = await trigger_voice_clone(persona_id, voice_sample_url)
        persona.voice_clone_cfg = clone_cfg
        if clone_cfg.get("ok"):
            persona.voice_cloned = True
        else:
            logger.warning(
                "声音克隆未完成: persona_id=%s, 原因=%s",
                persona_id, clone_cfg.get("error"),
            )

        await db.commit()
        await db.refresh(persona)

        logger.info("语音样本已上传: persona_id=%s, url=%s", persona_id, voice_sample_url)
    except Exception as e:
        logger.error("语音样本上传失败: %s", e)
        raise HTTPException(status_code=500, detail="语音样本上传失败")
```

（返回 `PersonaResponse` 部分保持不变。）

- [ ] **Step 4: 运行测试通过**

```bash
cd backend && python -m pytest tests/test_personas_voice.py -v
```

预期：2 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/personas.py backend/tests/test_personas_voice.py
git commit -m "feat: 语音样本上传端点接入真实克隆（cfg 落库+voice_cloned 状态）"
```

---

### Task 8: chat 照片亲人模式 + 克隆音色

**Files:**
- Modify: `backend/app/schemas/chat.py:16-19`（photo_id 字段）
- Modify: `backend/app/core/chat_engine.py`（persona 解析 + prompt + 返回扩展）
- Modify: `backend/app/api/v1/chat.py:52-98`（音色选择）
- Test: `backend/tests/test_chat_persona.py`

**Interfaces:**
- Consumes: Task 5 的 `synthesize_speech`；现成 `check_photo_persona_mode`。
- Produces:
  - `ChatMessageRequest` 增 `photo_id: UUID | None = None`
  - `chat_engine.generate_reply(patient_id, asr_text, photo_context=None, photo_id=None) -> {"reply_text", "persona", "persona_id", "voice_source"}`
  - 命中照片人物（有人物标注）→ 以该人物身份回话；该人物在人物库且 `voice_cloned` → `voice_source="cloned"` + `persona_id`

- [ ] **Step 1: 写失败测试 tests/test_chat_persona.py**

```python
import uuid
from types import SimpleNamespace

import app.api.v1.chat as chat_mod
from app.core.chat_engine import ChatEngine
from app.schemas.chat import ChatMessageRequest


class _FakeExec:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _SeqDB:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, stmt):
        return _FakeExec(self.results.pop(0))

    async def commit(self):
        pass


def _config():
    return SimpleNamespace(
        persona_name="强叔", era="1980s", language="zh-CN",
        region={"city": "广州"},
    )


def test_build_prompt_persona_mode():
    eng = ChatEngine()
    msgs = eng.build_prompt(
        _config(), [], "无照片", "你在吗",
        photo_persona={"persona_name": "阿珍", "persona_relation": "老伴"},
    )
    assert "阿珍" in msgs[0]["content"]
    assert "老伴" in msgs[0]["content"]


def test_build_prompt_default_mode():
    eng = ChatEngine()
    msgs = eng.build_prompt(_config(), [], "无照片", "你在吗")
    assert "强叔" in msgs[0]["content"]
    assert "阿珍" not in msgs[0]["content"]


def test_chat_message_request_accepts_photo_id():
    req = ChatMessageRequest(
        session_id=uuid.uuid4(), asr_text="hi",
        photo_id=uuid.uuid4(),
    )
    assert req.photo_id is not None


async def test_chat_message_cloned_voice(monkeypatch):
    session = SimpleNamespace(
        id=uuid.uuid4(), patient_id=uuid.uuid4(), message_count=0,
    )
    persona_row = SimpleNamespace(
        id=uuid.uuid4(), voice_cloned=True,
        voice_sample_url="/voice/x/audio/a.webm",
        voice_clone_cfg={"prompt_text": "你好，我是阿珍"},
    )
    db = _SeqDB([session, persona_row])

    reply = {
        "reply_text": "我是阿珍，我记得你",
        "persona": "阿珍",
        "persona_id": persona_row.id,
        "voice_source": "cloned",
    }

    async def fake_reply(**kwargs):
        assert kwargs.get("photo_id") is not None
        return reply

    captured = {}

    async def fake_tts(text, language, patient_id, voice="default",
                       persona_id=None, ref_audio_url=None, ref_text=None):
        captured.update(voice=voice, ref_text=ref_text)
        return "http://audio/1.wav" if voice == "persona" else "http://audio/0.wav"

    monkeypatch.setattr(chat_mod.chat_engine, "generate_reply", fake_reply)
    monkeypatch.setattr(chat_mod, "synthesize_speech", fake_tts)

    req = ChatMessageRequest(
        session_id=session.id, asr_text="阿珍你在吗",
        photo_id=uuid.uuid4(),
    )
    resp = await chat_mod.chat_message(req, db=db)

    assert resp.voice_source == "cloned"
    assert resp.persona == "阿珍"
    assert captured["voice"] == "persona"
    assert captured["ref_text"] == "你好，我是阿珍"
    assert resp.reply_audio_url == "http://audio/1.wav"


async def test_chat_message_default_voice(monkeypatch):
    session = SimpleNamespace(
        id=uuid.uuid4(), patient_id=uuid.uuid4(), message_count=0,
    )
    db = _SeqDB([session])

    async def fake_reply(**kwargs):
        return {
            "reply_text": "今天厂里排休呢",
            "persona": "强叔",
            "persona_id": None,
            "voice_source": "default",
        }

    captured = {}

    async def fake_tts(text, language, patient_id, voice="default",
                       persona_id=None, ref_audio_url=None, ref_text=None):
        captured.update(voice=voice)
        return None

    monkeypatch.setattr(chat_mod.chat_engine, "generate_reply", fake_reply)
    monkeypatch.setattr(chat_mod, "synthesize_speech", fake_tts)

    req = ChatMessageRequest(session_id=session.id, asr_text="我要去上班")
    resp = await chat_mod.chat_message(req, db=db)

    assert resp.voice_source == "default"
    assert captured["voice"] == "default"
    assert resp.reply_audio_url is None
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_chat_persona.py -v
```

预期：FAIL（photo_id 字段不存在 / build_prompt 无 photo_persona 参数）。

- [ ] **Step 3: schemas/chat.py 加字段**

```python
class ChatMessageRequest(BaseModel):
    session_id: UUID
    asr_text: str
    photo_context: str | None = None
    photo_id: UUID | None = None  # 当前轮播照片（有人物标注时触发照片亲人模式）
```

- [ ] **Step 4: chat_engine.py 改造**

文件头加导入：

```python
from app.models.persona import Persona
```

`build_prompt` 签名改为（加 `photo_persona=None`），并在函数体开头加分支：

```python
    def build_prompt(
        self,
        patient_config: PatientConfig,
        memories: list[Memory],
        photo_context: str,
        asr_text: str,
        photo_persona: dict | None = None,
    ) -> list[dict]:
        """构造 LLM prompt（photo_persona 命中时以照片亲人身份）"""
        memory_lines = [f"{i}. {m.raw_text}" for i, m in enumerate(memories, 1)]

        if photo_persona:
            p_name = photo_persona.get("persona_name", "亲人")
            p_relation = photo_persona.get("persona_relation") or "亲人"
            system_prompt = f"""你是{p_name}，患者的{p_relation}。你正通过数字相框和患者说话。
你和患者共同经历过下面这些事，像你亲自记得一样自然引用。

【核心对话规则】
1. 时空错位不纠错：顺着患者的话说，禁止出现"退休/你不是/你记错了"之类的否定和纠错。
2. 引用记忆：把下面的记忆自然穿插在对话中。
3. 语言一致：使用患者使用的语言（{patient_config.language or 'zh-CN'}）。
4. 简洁回复：回复严格控制在 40 字以内（中文）。

【记忆上下文】
{chr(10).join(memory_lines) if memory_lines else '暂无相关记忆'}

【照片上下文】
{photo_context}"""
        else:
            system_prompt = f"""你是{patient_config.persona_name or '强叔'}，一个{patient_config.era or '1980s'}年代的同龄街坊。你和患者是老相识、老街坊，一起在那个年代生活过。

【核心对话规则】
1. 时空错位不纠错：患者说"我要去上班"时回复"今天厂里排休呢"，禁止出现"退休/你不是/你记错了"之类的否定和纠错。
2. 引用记忆：将以下记忆自然穿插在对话中，仿佛你也记得这些事。
3. 语言一致：使用患者使用的语言（{patient_config.language or 'zh-CN'}）。
4. 简洁回复：回复严格控制在 40 字以内（中文）。

【患者画像】
- 年代：{patient_config.era or '未知'}
- 地区：{patient_config.region or '未知'}
- 语言：{patient_config.language or 'zh-CN'}

【记忆上下文】
{chr(10).join(memory_lines) if memory_lines else '暂无相关记忆'}

【照片上下文】
{photo_context}"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": asr_text},
        ]
```

新增 persona 解析方法：

```python
    async def _resolve_photo_persona(
        self,
        patient_id: uuid.UUID,
        photo_id: uuid.UUID,
    ) -> tuple[dict, Persona | None] | None:
        """照片有人物标注时返回 (照片人物信息, 人物库同名条目或None)"""
        info = await self.check_photo_persona_mode(patient_id, photo_id)
        if not info:
            return None
        async with async_session_factory() as db:
            stmt = select(Persona).where(
                Persona.patient_id == patient_id,
                Persona.name == info["persona_name"],
            )
            row = (await db.execute(stmt)).scalar_one_or_none()
        return info, row
```

`generate_reply` 整体替换为：

```python
    async def generate_reply(
        self,
        patient_id: uuid.UUID,
        asr_text: str,
        photo_context: str | None = None,
        photo_id: uuid.UUID | None = None,
    ) -> dict:
        """生成回复的完整流程

        Returns:
            {"reply_text": str, "persona": str,
             "persona_id": UUID | None, "voice_source": "cloned" | "default"}
        """
        async with async_session_factory() as db:
            cfg_stmt = select(PatientConfig).where(
                PatientConfig.patient_id == patient_id
            )
            cfg_result = await db.execute(cfg_stmt)
            patient_config = cfg_result.scalar_one_or_none()

        if patient_config is None:
            return {
                "reply_text": "你好呀，今天想聊点什么？",
                "persona": "老街坊",
                "persona_id": None,
                "voice_source": "default",
            }

        # 0. 照片亲人模式解析（photo_id 命中人物标注）
        photo_persona_info = None
        persona_row = None
        if photo_id is not None:
            resolved = await self._resolve_photo_persona(patient_id, photo_id)
            if resolved:
                photo_persona_info, persona_row = resolved

        # 1. 检索记忆
        memories = await self.retrieve_memories(patient_id, asr_text)

        # 2. 获取照片上下文
        if photo_context is None:
            photo_context = await self.get_photo_context(patient_id)

        # 3. 构建 prompt（照片亲人模式用人物身份）
        messages = self.build_prompt(
            patient_config, memories, photo_context, asr_text,
            photo_persona=photo_persona_info,
        )

        # 4. 调用 LLM
        reply_text = await self._call_llm_with_retry(messages)

        # 5. 确保不超过 40 字
        if len(reply_text) > 40:
            reply_text = reply_text[:40]

        # 6. 角色与音色来源
        if photo_persona_info:
            persona = photo_persona_info["persona_name"]
            if persona_row is not None and persona_row.voice_cloned:
                return {
                    "reply_text": reply_text,
                    "persona": persona,
                    "persona_id": persona_row.id,
                    "voice_source": "cloned",
                }
            return {
                "reply_text": reply_text,
                "persona": persona,
                "persona_id": None,
                "voice_source": "default",
            }

        return {
            "reply_text": reply_text,
            "persona": patient_config.persona_name or "老街坊",
            "persona_id": None,
            "voice_source": "default",
        }
```

- [ ] **Step 5: chat.py 改造**

文件头加导入：

```python
from uuid import UUID

from app.models.persona import Persona
```

新增辅助函数（router 定义之前）：

```python
async def _get_persona(db: AsyncSession, persona_id: UUID) -> Persona | None:
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    return result.scalar_one_or_none()
```

`chat_message` 整体替换为：

```python
@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(
    req: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """发送对话消息，返回数字人回复

    1. 检索相关记忆
    2. photo_id 命中照片亲人 -> 以该人物身份回话
    3. LLM 生成回复
    4. TTS 合成（克隆音/默认音，失败静默降级）
    5. 更新 session 消息计数
    """
    stmt = select(ChatSession).where(ChatSession.id == req.session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        return ChatMessageResponse(
            reply_text="你好呀，今天想聊点什么？",
            reply_audio_url=None,
            persona="老街坊",
            voice_source="default",
        )

    reply = await chat_engine.generate_reply(
        patient_id=session.patient_id,
        asr_text=req.asr_text,
        photo_context=req.photo_context,
        photo_id=req.photo_id,
    )

    # TTS 音色：照片亲人已克隆 -> 克隆音；否则默认音（失败 None 不阻断）
    audio_url = None
    if reply.get("voice_source") == "cloned" and reply.get("persona_id"):
        persona_row = await _get_persona(db, reply["persona_id"])
        if persona_row is not None and persona_row.voice_sample_url:
            cfg = persona_row.voice_clone_cfg or {}
            audio_url = await synthesize_speech(
                reply["reply_text"],
                language="zh-CN",
                patient_id=session.patient_id,
                voice="persona",
                persona_id=persona_row.id,
                ref_audio_url=persona_row.voice_sample_url,
                ref_text=cfg.get("prompt_text"),
            )
    if audio_url is None:
        audio_url = await synthesize_speech(
            reply["reply_text"],
            language="zh-CN",
            patient_id=session.patient_id,
        )

    session.message_count += 1
    await db.commit()

    return ChatMessageResponse(
        reply_text=reply["reply_text"],
        reply_audio_url=audio_url,
        persona=reply["persona"],
        voice_source=reply["voice_source"],
    )
```

- [ ] **Step 6: 运行测试（含全量回归）**

```bash
cd backend && python -m pytest tests -v
```

预期：全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/chat.py backend/app/core/chat_engine.py backend/app/api/v1/chat.py backend/tests/test_chat_persona.py
git commit -m "feat: 对话接入照片亲人模式（photo_id->人物身份+克隆音色，失败降级默认音）"
```

---

### Task 9: 家属端真实语音录记忆

**Files:**
- Modify: `caregiver-app/js/main.js`（startRecording/stopRecording 重写）
- Modify: `caregiver-app/js/api.js`（加 transcribeAudio）
- Modify: `caregiver-app/js/mock-api.js`（加 transcribeAudio mock）

**Interfaces:**
- Consumes: Task 3 的 `POST /api/v1/audio/transcribe`；photo-caption-composer 计划产出的 `submitMemoryEntry({text})`。
- Produces: `MockAPI.transcribeAudio(blob) -> Promise<{text, language}>`。

- [ ] **Step 1: mock-api.js 加 mock（`MockAPI` 对象内，`submitMemory` 附近）**

```js
  /**
   * 音频转文字（语音录记忆）
   * 对应 POST /api/v1/audio/transcribe
   * @param {Blob} blob - 录音 blob
   * @returns {Promise<Object>} { text, language }
   */
  transcribeAudio: (blob) => {
    console.log(`[MockAPI] transcribeAudio: size=${blob && blob.size}`);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({ text: '我爸以前在广州造船厂上班，每天下班都带我去江边看船', language: 'zh' });
      }, 800);
    });
  },
```

- [ ] **Step 2: api.js 加真实实现（`MockAPI.getDeviceStatus` 之后）**

```js
  MockAPI.transcribeAudio = async function (blob) {
    const fd = new FormData();
    fd.append('file', blob, 'voice.webm');
    fd.append('language', 'zh');
    const res = await fetch(BASE + '/audio/transcribe', { method: 'POST', body: fd });
    if (!res.ok) throw await res.json().catch(() => ({ detail: res.statusText }));
    return res.json();
  };
```

注意：**不要走 `_fetch`**（它强设 JSON Content-Type，multipart 由浏览器自动带 boundary）。

- [ ] **Step 3: main.js 重写录音**

在 `AppState` 附近（模块顶部变量区）加：

```js
  var mediaRecorder = null;
  var audioChunks = [];
  var submitPending = false;
```

替换 `startRecording` / `stopRecording` 为：

```js
  /** 开始录音（真实 MediaRecorder；不支持时由 stopRecording 回退模拟） */
  function startRecording() {
    if (AppState.isRecording) return;

    if (!navigator.mediaDevices || !window.MediaRecorder) {
      showToast('当前浏览器不支持录音');
      return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      AppState.isRecording = true;

      DOM.btnVoice.classList.add('recording');
      DOM.btnVoice.textContent = '⏺';

      showToast('录音中... 松开发送');

      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = function (e) {
        if (e.data && e.data.size) audioChunks.push(e.data);
      };
      mediaRecorder.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        if (!submitPending) return;

        var blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        if (blob.size < 2000) {
          showToast('录音太短，请按住说 1 秒以上');
          return;
        }
        showToast('语音识别中...');
        MockAPI.transcribeAudio(blob).then(function (res) {
          var text = ((res && res.text) || '').trim();
          if (!text) {
            showToast('没听清，再试一次');
            return;
          }
          submitMemoryEntry({ text: text });
        }).catch(function () {
          showToast('语音识别不可用');
        });
      };
      mediaRecorder.start();
    }).catch(function () {
      showToast('无法访问麦克风');
    });
  }

  /** 结束录音（submit=true 时提交转写） */
  function stopRecording(submit) {
    if (!AppState.isRecording) return;
    AppState.isRecording = false;

    DOM.btnVoice.classList.remove('recording');
    DOM.btnVoice.textContent = '🎤';

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      submitPending = submit;
      mediaRecorder.stop();
      return;
    }

    // 回退：无 mic 环境（演示）沿用罐头文本
    if (submit) {
      var mockAsrTexts = [
        '我爸以前在广州造船厂上班，每天下班都带我去江边看船',
        '小时候过年最喜欢去外婆家，她做的年糕特别好吃',
        '阿珍是我老伴，我们是在厂里认识的，她唱歌特别好听',
        '退休后喜欢去公园下象棋，老李头每次都输给我'
      ];
      submitMemoryEntry({ text: mockAsrTexts[Math.floor(Math.random() * mockAsrTexts.length)] });
    }
  }
```

- [ ] **Step 4: 手动验证**

1. Live Server 打开 caregiver-app（localhost，否则 mic 无权限）。
2. 按住 🎤 说一句中文（如"我妈最喜欢去越秀公园跳舞"）→ 松手。
3. 预期：toast「语音识别中...」（后端+ASR 服务都在时）→ 出现文字气泡（=识别文本）+ 记忆卡片。
4. 轻点一下 🎤（<0.5s）→ 预期：toast「录音太短」或回退提示，不发记忆。
5. 停掉 ASR 服务再录 → 预期：toast「语音识别不可用」。（api.js 无 catch 回退时会走这里；mock 模式下 transcribe 返回罐头句。）

- [ ] **Step 5: Commit**

```bash
git add caregiver-app/js/main.js caregiver-app/js/api.js caregiver-app/js/mock-api.js
git commit -m "feat: 家属端按住录音转真实 MediaRecorder+ASR 转写提交记忆"
```

---

### Task 10: 患者端语音对话闭环

**Files:**
- Create: `patient-app/js/voice.js`
- Modify: `patient-app/js/main.js`（CHAT 真闭环）
- Modify: `patient-app/js/photo-carousel.js`（getCurrentPhoto）
- Modify: `patient-app/index.html`（audio 元素 + script）
- Modify: `patient-app/js/api.js` / `patient-app/js/mock-api.js`（transcribeAudio、persona_name）

**Interfaces:**
- Consumes: Task 3 的 `/audio/transcribe`；Task 8 的 `photo_id`；状态机既有动作 `speech_detected`（STANDBY→CHAT）、`silence_timeout`（CHAT→STANDBY）。
- Produces: `VoiceManager`（全局，`init()/suspend()/resume()/available`，回调 `onSpeechStart`/`onUtterance(blob)`）；`photoCarousel.getCurrentPhoto()`。

- [ ] **Step 1: 创建 voice.js**

```js
/**
 * VoiceManager - 麦克风 VAD + 切句录音
 * ==============================
 * 常驻监听：音量 RMS 检测说话开始/结束，静音 0.7s 切句产出音频 blob。
 * 播放 TTS 期间 suspend() 暂停检测（防自听回声）。
 *
 * @module VoiceManager
 */
(function (global) {
  'use strict';

  var RMS_START = 0.045;      // 判定开始说话的音量阈值
  var RMS_STOP = 0.015;       // 判定停止说话的音量阈值
  var SILENCE_MS = 700;       // 静音多久判定一句话结束
  var MIN_UTTERANCE_MS = 400; // 过短视为噪声丢弃

  function VoiceManager() {
    this.available = false;
    this._ctx = null;
    this._stream = null;
    this._analyser = null;
    this._meterTimer = null;
    this._suspended = false;
    this._recorder = null;
    this._chunks = [];
    this._utteranceStart = 0;
    this._speechActive = false;
    this._silenceSince = 0;
    this.onSpeechStart = null; // 说话开始（用于 STANDBY->CHAT 触发）
    this.onUtterance = null;   // function(blob) 一句话结束
  }

  /** 初始化麦克风与分析器，resolve(true/false) */
  VoiceManager.prototype.init = function () {
    var self = this;
    if (!navigator.mediaDevices || !window.MediaRecorder ||
        !window.AudioContext) {
      return Promise.resolve(false);
    }
    return navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      self._stream = stream;
      var Ctx = window.AudioContext || window.webkitAudioContext;
      self._ctx = new Ctx();
      var source = self._ctx.createMediaStreamSource(stream);
      self._analyser = self._ctx.createAnalyser();
      self._analyser.fftSize = 1024;
      source.connect(self._analyser);
      self.available = true;
      self._startMeter();
      return true;
    }).catch(function (err) {
      console.warn('[Voice] 麦克风不可用:', err);
      return false;
    });
  };

  VoiceManager.prototype._startMeter = function () {
    var self = this;
    var buf = new Uint8Array(this._analyser.fftSize);
    this._meterTimer = setInterval(function () {
      if (!self._analyser || self._suspended) return;

      self._analyser.getByteTimeDomainData(buf);
      var sum = 0;
      for (var i = 0; i < buf.length; i++) {
        var v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      var rms = Math.sqrt(sum / buf.length);
      var now = Date.now();

      if (!self._speechActive) {
        if (rms >= RMS_START) {
          self._speechActive = true;
          self._utteranceStart = now;
          self._beginRecording();
          if (typeof self.onSpeechStart === 'function') self.onSpeechStart();
        }
      } else {
        if (rms < RMS_STOP) {
          if (!self._silenceSince) self._silenceSince = now;
          if (now - self._silenceSince >= SILENCE_MS) {
            self._speechActive = false;
            self._silenceSince = 0;
            self._finishRecording(now - self._utteranceStart);
          }
        } else {
          self._silenceSince = 0;
        }
      }
    }, 100);
  };

  VoiceManager.prototype._beginRecording = function () {
    var self = this;
    try {
      this._chunks = [];
      this._recorder = new MediaRecorder(this._stream);
      this._recorder.ondataavailable = function (e) {
        if (e.data && e.data.size) self._chunks.push(e.data);
      };
      this._recorder.start();
    } catch (e) {
      console.warn('[Voice] 录音启动失败:', e);
    }
  };

  VoiceManager.prototype._finishRecording = function (durationMs) {
    var self = this;
    var rec = this._recorder;
    if (!rec || rec.state === 'inactive') return;

    if (durationMs < MIN_UTTERANCE_MS) {
      try { rec.stop(); } catch (e) { /* ignore */ }
      this._chunks = [];
      return;
    }
    rec.onstop = function () {
      var blob = new Blob(self._chunks, { type: rec.mimeType || 'audio/webm' });
      if (blob.size > 0 && typeof self.onUtterance === 'function') {
        self.onUtterance(blob);
      }
    };
    try { rec.stop(); } catch (e) { /* ignore */ }
  };

  /** 播放 TTS 期间暂停检测 */
  VoiceManager.prototype.suspend = function () {
    this._suspended = true;
  };

  /** 播放完恢复（重置状态防误触发） */
  VoiceManager.prototype.resume = function () {
    this._suspended = false;
    this._silenceSince = 0;
    this._speechActive = false;
  };

  global.VoiceManager = VoiceManager;

})(window);
```

- [ ] **Step 2: index.html（CHAT 区加 audio；引入 voice.js）**

`state-CHAT` 区块内（`<div id="chat-wave"></div>` 之后）加：

```html
          <!-- TTS 播放（隐藏） -->
          <audio id="chat-audio" preload="auto"></audio>
```

脚本加载顺序（`js/hud.js` 之后、`js/main.js` 之前）插入：

```html
  <script src="js/voice.js"></script>
```

- [ ] **Step 3: photo-carousel.js 加 getCurrentPhoto（getCurrentIndex 之后）**

```js
  /**
   * 获取当前照片对象
   * @returns {Object|null} { id, url|object_url, persona_name, ... }
   */
  PhotoCarousel.prototype.getCurrentPhoto = function () {
    if (!this._photos || this._photos.length === 0) return null;
    return this._photos[this._currentIndex] || null;
  };
```

- [ ] **Step 4: mock-api.js（transcribeAudio mock + 照片 persona_name + 克隆音 mock 回复）**

`PHOTO_PLACEHOLDERS` 的 `photo-1` 与 `photo-3` 对象各加一行（caption 行后）：

```js
      persona_name: '阿珍',
```

`sendChatMessage` 的 resolve 改为（识别 photo_id 时模拟照片亲人回复）：

```js
    sendChatMessage: function (data) {
      return new Promise(function (resolve) {
        setTimeout(function () {
          if (data && data.photo_id) {
            resolve({
              reply_text: '是我呀，阿珍。我还记得那年咱们在厂门口拍的这张。',
              reply_audio_url: null,
              persona: '阿珍',
              voice_source: 'cloned'
            });
            return;
          }
          var replies = [
            '今天天气不错啊，要不要出去走走？',
            '我记得你最爱吃糖葫芦了。',
            '那年厂里分房子，咱们抽到了三楼。',
            '阿珍昨天还念叨你来着。',
            '咱老街坊啊，就爱听你讲故事。'
          ];
          var idx = Math.floor(Math.random() * replies.length);
          resolve({
            reply_text: replies[idx],
            reply_audio_url: null,
            persona: '老街坊',
            voice_source: 'default'
          });
        }, 500 + Math.random() * 500);
      });
    },
```

`endSession` 之前加：

```js
    /**
     * 音频转文字（患者端语音对话）
     * 对应 POST /api/v1/audio/transcribe
     * @param {Blob} blob
     * @returns {Promise<Object>} { text, language }
     */
    transcribeAudio: function (blob) {
      console.log('[MockAPI] transcribeAudio: size=', blob && blob.size);
      return new Promise(function (resolve) {
        setTimeout(function () {
          resolve({ text: '阿珍，你还记得我吗？', language: 'zh' });
        }, 600);
      });
    },
```

- [ ] **Step 5: api.js 加 transcribeAudio（heartbeat 之后）**

```js
  MockAPI.transcribeAudio = async function (blob) {
    const fd = new FormData();
    fd.append('file', blob, 'voice.webm');
    fd.append('language', 'zh');
    const res = await fetch(BASE + '/audio/transcribe', { method: 'POST', body: fd });
    if (!res.ok) throw await res.json().catch(() => ({ detail: res.statusText }));
    return res.json();
  };
```

（`sendChatMessage` 直接透传 data，`photo_id` 自动带上，无需改。）

- [ ] **Step 6: main.js 改造 CHAT 模块**

模块顶部变量区（`var currentSessionId = null;` 之后）加：

```js
  var voiceManager = null;
  var chatAudioEl = null;
  var waitingReply = false;
  var idleTimer = null;
  var IDLE_TIMEOUT_MS = 90000;
```

`init()` 中「4. 注册状态监听器」之前插入：

```js
    // 3.5 语音管理器（失败回退模拟对话）
    chatAudioEl = document.getElementById('chat-audio');
    voiceManager = new VoiceManager();
    voiceManager.init().then(function (ok) {
      console.log('[Voice] 初始化:', ok ? '可用' : '不可用（回退模拟对话）');
    });
    voiceManager.onSpeechStart = function () {
      if (stateMachine.getCurrentState() === STATES.STANDBY) {
        stateMachine.transition('speech_detected');
      }
    };
    voiceManager.onUtterance = function (blob) {
      if (stateMachine.getCurrentState() === STATES.CHAT) {
        handleUtterance(blob);
      }
    };
```

替换 `startChat` / `stopChat`，并在 `simulateChat` 之前插入新函数：

```js
  function startChat() {
    chatting = true;

    if (chatAvatarEl) {
      chatAvatarEl.style.backgroundImage =
        'radial-gradient(circle at 35% 35%, #f0d8b8, #d4a574 60%, #b8845a 100%)';
    }

    startWaveAnimation();

    if (voiceManager && voiceManager.available) {
      // 真实语音闭环
      MockAPI.startSession().then(function (result) {
        currentSessionId = result.session_id;
        if (chatSubtitleEl) {
          chatSubtitleEl.textContent = '... 倾听中';
          chatSubtitleEl.className = 'listening';
        }
        resetIdleTimer();
      });
    } else {
      simulateChat();
    }
  }

  function stopChat() {
    chatting = false;
    waitingReply = false;
    if (chatSimTimer) {
      clearTimeout(chatSimTimer);
      chatSimTimer = null;
    }
    if (idleTimer) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }
    if (voiceManager) voiceManager.resume();
    if (chatAudioEl) chatAudioEl.pause();
    stopWaveAnimation();

    if (currentSessionId) {
      MockAPI.endSession(currentSessionId);
      currentSessionId = null;
    }
  }

  /** 空闲超时回 STANDBY（每次交互重置） */
  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(function () {
      if (stateMachine.getCurrentState() === STATES.CHAT) {
        stateMachine.transition('silence_timeout');
      }
    }, IDLE_TIMEOUT_MS);
  }

  /** 处理一句话录音：转写 -> 对话 -> 播报 */
  function handleUtterance(blob) {
    if (waitingReply || !currentSessionId) return;
    waitingReply = true;
    resetIdleTimer();

    if (chatSubtitleEl) {
      chatSubtitleEl.textContent = '... 倾听中';
      chatSubtitleEl.className = 'listening';
    }

    MockAPI.transcribeAudio(blob).then(function (res) {
      var text = ((res && res.text) || '').trim();
      if (!text) {
        waitingReply = false;
        return;
      }

      var photo = photoCarousel ? photoCarousel.getCurrentPhoto() : null;
      var payload = {
        session_id: currentSessionId,
        asr_text: text,
        photo_id: (photo && photo.persona_name && photo.id) ? photo.id : null
      };

      MockAPI.sendChatMessage(payload).then(function (result) {
        showReply(result);
      }).catch(function () {
        waitingReply = false;
      });
    }).catch(function () {
      waitingReply = false;
    });
  }

  /** 展示回复：字幕+角色名+HUD+音频播报（播放期间暂停 VAD） */
  function showReply(result) {
    if (chatSubtitleEl) {
      chatSubtitleEl.textContent = '「' + result.reply_text + '」';
      chatSubtitleEl.className = 'speaking';
    }

    var personaNameEl = document.getElementById('chat-persona-name');
    if (personaNameEl && result.persona) {
      personaNameEl.textContent = result.persona;
    }

    if (hudPanel && hudPanel.isVisible()) {
      hudPanel.updatePromptInfo('回复: ' + result.reply_text);
      hudPanel.updateVoiceSource(result.persona + ' / ' + result.voice_source);
    }

    simulateTTSPulse();

    var finish = function () {
      if (voiceManager) voiceManager.resume();
      waitingReply = false;
      resetIdleTimer();
    };

    if (result.reply_audio_url && chatAudioEl) {
      if (voiceManager) voiceManager.suspend();
      chatAudioEl.src = result.reply_audio_url;
      chatAudioEl.onended = finish;
      chatAudioEl.onerror = finish;
      chatAudioEl.play().catch(finish);
    } else {
      // 无音频（TTS 未配置）：按 3s 模拟播报后恢复
      setTimeout(finish, 3000);
    }
  }
```

（`simulateChat` / `chatLoop` / `simulateTTSPulse` / `triggerChat` 保留不动，作为无 mic 回退。）

- [ ] **Step 7: 手动验证**

1. Live Server 打开 patient-app/index.html（localhost + 授权麦克风）。
2. 控制台 `window.__debug.stateMachine.transition('config_ready')` 进 STANDBY。
3. 对麦克风说一句话 → 预期：自动进入 CHAT（无需 triggerChat），字幕「... 倾听中」→ 回复字幕+角色名（mock 下带 persona_name 的照片会回「阿珍 / cloned」）。
4. 继续说话 → 多轮对话循环；每次回复后恢复倾听。
5. 静默 90s → 预期：回 STANDBY（开发时可临时把 IDLE_TIMEOUT_MS 改小验证）。
6. 拒绝麦克风授权刷新 → 预期：走原模拟循环（simulateChat），不报错。

- [ ] **Step 8: Commit**

```bash
git add patient-app/js/voice.js patient-app/js/main.js patient-app/js/photo-carousel.js patient-app/index.html patient-app/js/api.js patient-app/js/mock-api.js
git commit -m "feat: 患者端语音对话闭环（VAD监听+切句转写+photo_id照片亲人+TTS播报）"
```

---

### Task 11: 文档与收尾

**Files:**
- Create: `voice-services/README.md`
- Modify: `README.md`（技术栈行 + 后端启动段）
- Modify: `.gitignore`

- [ ] **Step 1: voice-services/README.md**

````markdown
# voice-services 语音服务

AIx-health 的旁路语音模型服务。后端（:8000）通过 HTTP 调用，二者可独立启停。

| 服务 | 端口 | 说明 |
| :--- | :--- | :--- |
| ASR（SenseVoice） | 8200 | 本目录 `asr_server.py` |
| TTS（GPT-SoVITS） | 8300 | 官方仓库 `api_v2.py`，独立安装 |

## 0. 前置依赖

- Python 3.10+（建议 3.11）
- **ffmpeg**（必须，音频归一化）：Windows `winget install Gyan.FFmpeg`，装后在终端 `ffmpeg -version` 验证
- NVIDIA GPU（可选，ASR 用 `ASR_DEVICE=cuda` 加速）

## 1. ASR 服务（SenseVoice）

```bash
cd voice-services
python -m venv .venv
.venv\Scripts\pip install -r requirements-asr.txt
# GPU 加速：set ASR_DEVICE=cuda
.venv\Scripts\python asr_server.py          # 默认 127.0.0.1:8200
```

- 首次请求会从 ModelScope 自动下载 SenseVoiceSmall（约 1GB），请耐心等待。
- 验证：`curl http://127.0.0.1:8200/health`

## 2. GPT-SoVITS 服务（:8300）

在**本目录之外**（如 `../GPT-SoVITS`）克隆官方仓库并安装：

```bash
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS
# 按官方 README 安装依赖并下载预训练模型到 GPT_SoVITS/pretrained_models/
python api_v2.py -a 127.0.0.1 -p 8300 -c GPT_SoVITS/configs/tts_infer.yaml
```

验证：服务起来后，后端 `/chat/message` 的 TTS 会在有请求时自动调用。

## 3. 默认音色（必配一次）

GPT-SoVITS 是参考音频合成，**任何语音都需要参考音**。默认老街坊/强叔音：

1. 准备一段 3~10s 干净中文人声 wav（音色越接近目标越好）；
2. 放到仓库根 `voice-runtime/refs/default.wav`；
3. 把这段话的**文字内容**写入 `voice-runtime/refs/default.prompt.txt`（一行即可），
   或在 `backend/.env` 配 `DEFAULT_VOICE_REF` / `DEFAULT_VOICE_REF_TEXT`。

> 未配置时对话仍可用（纯文字回复，`reply_audio_url=null`）。

## 4. 人物库克隆音（参考音频即克隆）

`PUT /personas/{id}/voice` 上传 3~10s 样本即可，后端自动：转码 -> ASR 转写 ->
校验 -> 缓存到 `voice-runtime/refs/{persona_id}.wav` -> `voice_cloned=true`。
患者端轮播到该人物照片并对话时，自动用其克隆音色回复。

## 5. 启动顺序

postgres/minio（docker-compose.dev.yml）→ ASR(:8200) → GPT-SoVITS(:8300) → backend(:8000) → 前端
````

- [ ] **Step 2: 根 README.md 更新**

技术栈表中 `| ASR/TTS | 预留接口（FunASR / Coqui TTS） |` 替换为：

```markdown
| ASR | SenseVoice（funasr，voice-services/ 独立服务 :8200） |
| TTS/克隆 | GPT-SoVITS（参考音频即克隆，独立服务 :8300，见 voice-services/README.md） |
```

「后端启动」小节的依赖表后追加：

```markdown
**语音服务（可选，不启动则对话无语音、记忆文字录入仍可用）**：

```bash
# ASR :8200
cd voice-services && .venv\Scripts\python asr_server.py
# TTS :8300（官方 GPT-SoVITS 仓库）
python api_v2.py -a 127.0.0.1 -p 8300 -c GPT_SoVITS/configs/tts_infer.yaml
```

详见 [voice-services/README.md](voice-services/README.md)（含默认音色 default.wav 配置）。
```

- [ ] **Step 3: .gitignore 追加**

```
voice-runtime/
voice-services/.venv/
```

- [ ] **Step 4: 全量回归**

```bash
cd backend && python -m pytest tests -v
```

预期：全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add voice-services/README.md README.md .gitignore
git commit -m "docs: 语音服务启动文档（ASR/GPT-SoVITS/默认音色/克隆流程）"
```

---

## 验收清单（对照 spec 第 6 节）

1. `voice-services` ASR `/health` ok、`/asr` 能转写中文。
2. GPT-SoVITS :8300 起后，`POST /api/v1/chat/message` 返回 `reply_audio_url`（presigned），播放为克隆/默认音。
3. caregiver-app：选图→描述→发送；按住说话→转写→记忆。
4. `PUT /personas/{id}/voice` 上传样本 → `voice_cloned=true`，`voice_clone_cfg.prompt_text` 非空。
5. patient-app：说话自动进 CHAT，多轮语音对话，照片亲人克隆音播报，90s 空闲回 STANDBY。
6. ASR/TTS 任一服务关闭：前端提示降级，不崩溃。

