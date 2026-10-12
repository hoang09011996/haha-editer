"""TTS từng mốc → audio/beats/NNN.wav (cache theo hash lời + giọng), ghép audio/voice.wav, điền start/end."""
from __future__ import annotations

import hashlib
import json
import time
import wave
from pathlib import Path
from typing import Callable

from vidflow.config import Config
from vidflow.errors import VidflowError
from vidflow.media import ensure_wav
from vidflow.quick.model import Beat, load_quick, project_lock, require_beats, save_beats
from vidflow.quick.ops import VOICE_FILE, _advance
from vidflow.quick.preset import Preset, load_preset
from vidflow.retry import with_retry
from vidflow.state import atomic_write_text
from vidflow.tts import SpeechClient

RATE = 24000
GAP_S = 0.15
BEATS_AUDIO = "audio/beats"
INDEX = "index.json"


def beat_hash(text: str, preset: Preset, model: str) -> str:
    key = json.dumps([text.strip(), preset.voice.name, preset.voice.style, model], ensure_ascii=False)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _index_path(root: Path) -> Path:
    return Path(root) / BEATS_AUDIO / INDEX


def _load_index(root: Path) -> dict:
    p = _index_path(root)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _beat_wav(root: Path, n: int) -> Path:
    return Path(root) / BEATS_AUDIO / f"{n:03d}.wav"


def voiced_count(root: Path, beats: list[Beat]) -> int:
    """Số mốc có wav trong cache khớp đúng lời hiện tại."""
    idx = _load_index(root)
    return sum(1 for b in beats if (e := idx.get(str(b.n))) and e.get("text") == b.text.strip()
               and _beat_wav(root, b.n).is_file())


def _read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, RATE):
            raise VidflowError(f"{path}: cần WAV mono 16-bit {RATE} Hz")
        return w.readframes(w.getnframes())


def run_voice(root: Path, cfg: Config, client: SpeechClient, *, preset: Preset | None = None,
              sleep: Callable[[float], None] = time.sleep, on_progress: Callable[[int, int], None] | None = None) -> float:
    """Đọc mọi mốc chưa có trong cache, ghép voice.wav, điền start/end. Trả độ dài voice.wav (giây).
    Lỗi giữa chừng → giữ các câu đã đọc, báo VidflowError; chạy lại sẽ tiếp tục."""
    root = Path(root)
    preset = preset or load_preset(load_quick(root).preset)
    beats = require_beats(root)
    (root / BEATS_AUDIO).mkdir(parents=True, exist_ok=True)
    idx = _load_index(root)
    total = len(beats.beats)
    done = 0
    for b in beats.beats:
        h = beat_hash(b.text, preset, cfg.tts_model)
        out = _beat_wav(root, b.n)
        if idx.get(str(b.n), {}).get("hash") == h and out.is_file():
            done += 1
            continue
        try:
            data = with_retry(lambda: client.synthesize(text=b.text, voice=preset.voice.name,
                                                        style=preset.voice.style, model=cfg.tts_model), sleep=sleep)
        except Exception as e:
            hint = " — Gemini không trả lời, thường do hết lượt TTS miễn phí; thử lại sau" if isinstance(e, TimeoutError) else ""
            raise VidflowError(f"TTS dừng ở mốc {b.n}: đã đọc {done}/{total} câu ({e}{hint}). "
                               "Chạy lại `vidflow quick voice` để tiếp tục (các câu đã đọc được giữ lại).") from e
        out.write_bytes(ensure_wav(data, RATE))
        _read_pcm(out)  # kiểm tra định dạng sớm
        idx[str(b.n)] = {"hash": h, "text": b.text.strip()}
        atomic_write_text(_index_path(root), json.dumps(idx, ensure_ascii=False, indent=1))
        done += 1
        if on_progress:
            on_progress(done, total)

    # TTS ở trên chạy lâu nên không giữ khóa; phần ghép + ghi mốc thời gian chạy dưới khóa, trên beats.json đọc lại
    # (giữ thay đổi của tiến trình khác trong lúc đọc), và từ chối nếu lời thoại đã đổi giữa chừng.
    spoken = [(b.n, b.text.strip()) for b in beats.beats]
    with project_lock(root):
        beats = require_beats(root)
        if [(b.n, b.text.strip()) for b in beats.beats] != spoken:
            raise VidflowError("Lời thoại đã đổi trong lúc đọc — chạy lại `vidflow quick voice`.")
        gap = b"\x00\x00" * int(round(GAP_S * RATE))
        frames = 0
        voice = root / VOICE_FILE
        tmp = voice.with_suffix(".tmp.wav")
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            for i, b in enumerate(beats.beats):
                if i:
                    w.writeframes(gap)
                    frames += len(gap) // 2
                pcm = _read_pcm(_beat_wav(root, b.n))
                b.start = round(frames / RATE, 3)
                frames += len(pcm) // 2
                b.end = round(frames / RATE, 3)
                w.writeframes(pcm)
        tmp.replace(voice)
        save_beats(root, beats)
        _advance(root, "voiced")
    return frames / RATE


def gemini_voice(root: Path, cfg: Config, **kw) -> float:
    """Bản thật: Gemini TTS (free tier) — dùng cho CLI/UI."""
    from vidflow.gemini import GeminiSpeechClient

    return run_voice(root, cfg, GeminiSpeechClient(), **kw)
