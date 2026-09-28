from __future__ import annotations

import io
import math
import subprocess
import wave
from pathlib import Path

from vidflow.errors import VidflowError


def ensure_wav(data: bytes, rate: int = 24000) -> bytes:
    """Gemini TTS trả WAV; nếu nhận PCM 16-bit mono thô thì bọc header WAV."""
    if data[:4] == b"RIFF":
        return data
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data)
    return buf.getvalue()


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def floor_ms(x: float) -> float:
    return math.floor(round(x * 1000, 6)) / 1000


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not r.stdout.strip():
        raise VidflowError(f"ffprobe không đọc được {path}: {r.stderr.strip()}")
    return float(r.stdout.strip())
