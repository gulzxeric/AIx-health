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
