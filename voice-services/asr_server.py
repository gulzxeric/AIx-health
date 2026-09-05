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
