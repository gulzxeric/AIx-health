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
