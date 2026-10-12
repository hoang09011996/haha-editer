"""Giọng đọc quy trình nhanh, 3 cách (quick.yaml `voice_mode`):
- per_beat: mỗi mốc một lượt TTS → audio/beats/NNN.wav (cache theo hash lời + giọng);
- chunk: ~20 mốc/lượt (tối đa ~1500 ký tự) → audio/chunks/<hash>.wav, căn mốc trong đoạn bằng khoảng lặng;
- full: cả bài một lượt (một đoạn).
Sau cùng ghép audio/voice.wav và điền start/end (dưới khóa project)."""
from __future__ import annotations

import hashlib
import json
import math
import time
import wave
from array import array
from pathlib import Path
from typing import Callable, Sequence

from vidflow.config import Config
from vidflow.errors import VidflowError
from vidflow.media import ensure_wav
from vidflow.quick.model import Beat, Beats, load_quick, project_lock, require_beats, save_beats
from vidflow.quick.ops import VOICE_FILE, _advance, check_voice_mode
from vidflow.quick.preset import Preset, load_preset
from vidflow.retry import with_retry
from vidflow.state import atomic_write_text
from vidflow.tts import SpeechClient

RATE = 24000
GAP_S = 0.15
BEATS_AUDIO = "audio/beats"
CHUNKS_AUDIO = "audio/chunks"
INDEX = "index.json"
CHUNK_BEATS = 20      # số mốc tối đa mỗi đoạn (chunk)
CHUNK_CHARS = 1500    # số ký tự tối đa mỗi đoạn — vượt thì mở đoạn mới
FULL_MAX_CHARS = 3000  # "cả bài một lượt" chỉ cho bài ngắn — bài dài Gemini dễ cắt/bỏ câu, lỗi thì mất cả lượt
FRAME_S = 0.01        # khung phân tích âm lượng
SILENCE_REL = 0.05    # khung có RMS < 5% RMS đỉnh của đoạn = im lặng
MIN_SILENCE_S = 0.12


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


def voiced_count(root: Path, beats: list[Beat], mode: str = "per_beat") -> int:
    """Số mốc có audio trong cache (của cách đọc `mode`) khớp đúng lời hiện tại."""
    if mode != "per_beat":
        cidx = _load_chunk_index(root)
        have = {(e.get("mode"), tuple(e.get("texts", []))) for h, e in cidx.items() if _chunk_wav(root, h).is_file()}
        texts = [b.text.strip() for b in beats]
        return sum(len(g) for g in chunk_groups(texts, mode) if (mode, tuple(texts[i] for i in g)) in have)
    idx = _load_index(root)
    return sum(1 for b in beats if (e := idx.get(str(b.n))) and e.get("text") == b.text.strip()
               and _beat_wav(root, b.n).is_file())


def _read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, RATE):
            raise VidflowError(f"{path}: cần WAV mono 16-bit {RATE} Hz")
        return w.readframes(w.getnframes())


# ---------- đọc theo đoạn (chunk/full) ----------

def chunk_groups(texts: list[str], mode: str) -> list[list[int]]:
    """Chia mốc (theo chỉ số) thành các đoạn đọc một lượt. Tất định: chunk chia theo khối CHUNK_BEATS mốc cố định
    rồi tách tiếp khi vượt CHUNK_CHARS — sửa một câu chỉ làm đổi đoạn trong khối của nó."""
    n = len(texts)
    if mode == "per_beat":
        return [[i] for i in range(n)]
    if mode == "full":
        return [list(range(n))] if n else []
    groups: list[list[int]] = []
    for block in range(0, n, CHUNK_BEATS):
        cur: list[int] = []
        chars = 0
        for i in range(block, min(block + CHUNK_BEATS, n)):
            size = len(texts[i].strip()) + (1 if cur else 0)
            if cur and chars + size > CHUNK_CHARS:
                groups.append(cur)
                cur, chars, size = [], 0, len(texts[i].strip())
            cur.append(i)
            chars += size
        groups.append(cur)
    return groups


def chunk_hash(mode: str, texts: list[str], preset: Preset, model: str) -> str:
    key = json.dumps([mode, "\n".join(texts), preset.voice.name, preset.voice.style, model], ensure_ascii=False)
    return hashlib.sha256(key.encode()).hexdigest()[:20]


def _chunk_index_path(root: Path) -> Path:
    return Path(root) / CHUNKS_AUDIO / INDEX


def _load_chunk_index(root: Path) -> dict:
    p = _chunk_index_path(root)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _chunk_wav(root: Path, h: str) -> Path:
    return Path(root) / CHUNKS_AUDIO / f"{h}.wav"


def _tts_chunks(root: Path, cfg: Config, client: SpeechClient, preset: Preset, beats: Beats, mode: str,
                sleep: Callable[[float], None], on_progress: Callable[[int, int], None] | None) -> list[tuple[list[int], str]]:
    """Mỗi đoạn một lượt TTS (lời các mốc nối bằng xuống dòng) → audio/chunks/<hash>.wav. Trả [(chỉ số mốc, hash)]."""
    (root / CHUNKS_AUDIO).mkdir(parents=True, exist_ok=True)
    idx = _load_chunk_index(root)
    texts = [b.text.strip() for b in beats.beats]
    n_chars = sum(len(t) for t in texts)
    if mode == "full" and n_chars > FULL_MAX_CHARS:
        raise VidflowError(f"Bài dài {n_chars} ký tự — 'Cả bài một lượt' chỉ dùng cho bài ≤ {FULL_MAX_CHARS} ký tự. "
                           "Chọn cách đọc 'Theo đoạn' (chunk) trong Cài đặt.")
    groups = chunk_groups(texts, mode)
    out: list[tuple[list[int], str]] = []
    total, done = len(groups), 0
    for g in groups:
        part = [texts[i] for i in g]
        h = chunk_hash(mode, part, preset, cfg.tts_model)
        wav = _chunk_wav(root, h)
        out.append((g, h))
        if h in idx and wav.is_file():
            done += 1
            continue
        joined = "\n".join(part)
        try:
            # treo (TimeoutError) gần như luôn do hết lượt miễn phí: thử lại chỉ thêm vài phút chờ vô ích
            data = with_retry(lambda: client.synthesize(text=joined, voice=preset.voice.name,
                                                        style=preset.voice.style, model=cfg.tts_model), sleep=sleep,
                              retry_timeouts=False)
        except Exception as e:
            hint = " — Gemini không trả lời, thường do hết lượt TTS miễn phí; thử lại sau" if isinstance(e, TimeoutError) else ""
            first, last = beats.beats[g[0]].n, beats.beats[g[-1]].n
            raise VidflowError(f"TTS dừng ở đoạn {done + 1} (mốc {first}–{last}): đã đọc {done}/{total} đoạn "
                               f"({e}{hint}). Chạy lại `vidflow quick voice` để tiếp tục (các đoạn đã đọc được giữ lại).") from e
        tmp = wav.with_suffix(".tmp.wav")
        tmp.write_bytes(ensure_wav(data, RATE))
        _read_pcm(tmp)  # kiểm tra định dạng sớm
        tmp.replace(wav)
        idx[h] = {"mode": mode, "texts": part, "voice": preset.voice.name, "model": cfg.tts_model}
        atomic_write_text(_chunk_index_path(root), json.dumps(idx, ensure_ascii=False, indent=1))
        done += 1
        if on_progress:
            on_progress(done, total)
    return out


def _weight(text: str) -> int:
    return max(1, sum(1 for c in text if not c.isspace()))


def align_chunk(samples: Sequence[int], rate: int, texts: list[str]) -> list[tuple[float, float]]:
    """Căn mốc trong audio một đoạn: [(start, end)] (giây, tính từ đầu đoạn, làm tròn ms), liền nhau và tăng dần.
    Ranh giới = giữa khoảng lặng (≥ MIN_SILENCE_S) gần điểm cắt kỳ vọng (tỉ lệ số ký tự không tính dấu cách);
    không có khoảng lặng hợp lệ trong cửa sổ → dùng điểm cắt kỳ vọng."""
    n = len(texts)
    if n == 0:
        return []
    total_s = len(samples) / rate
    frame = max(1, int(round(FRAME_S * rate)))
    rms = []
    for i in range(0, len(samples), frame):
        chunk = samples[i:i + frame]
        rms.append(math.sqrt(sum(x * x for x in chunk) / len(chunk)))
    peak = max(rms, default=0.0)
    if peak <= 0:
        s0, e0 = 0.0, total_s
        silences: list[tuple[float, float]] = []
    else:
        thr = peak * SILENCE_REL
        loud = [i for i, r in enumerate(rms) if r >= thr]
        first, last = loud[0], loud[-1]
        amp = thr  # biên: mẫu đầu/cuối vượt ngưỡng trong khung biên
        lo = next((k for k in range(first * frame, min(len(samples), (first + 1) * frame)) if abs(samples[k]) >= amp),
                  first * frame)
        hi_end = min(len(samples), (last + 1) * frame)
        hi = next((k + 1 for k in range(hi_end - 1, last * frame - 1, -1) if abs(samples[k]) >= amp), hi_end)
        s0, e0 = lo / rate, hi / rate
        silences = []
        run = None
        min_frames = int(math.ceil(MIN_SILENCE_S / FRAME_S - 1e-9))
        for i in range(first, last + 1):
            if rms[i] < thr:
                run = i if run is None else run
            elif run is not None:
                if i - run >= min_frames:
                    silences.append((run * frame / rate, i * frame / rate))
                run = None
    dur = max(e0 - s0, 0.0)
    w = [_weight(t) for t in texts]
    tot = sum(w)
    cum, acc = [], 0
    for x in w[:-1]:
        acc += x
        cum.append(acc)
    expected = [s0 + dur * c / tot for c in cum]
    lens = [dur * x / tot for x in w]
    windows = [max(0.6, 0.35 * max(lens[i], lens[i + 1])) for i in range(n - 1)]
    mids = [(a + b) / 2 for a, b in silences]
    cuts = _match_cuts(expected, windows, mids, [b - a for a, b in silences])
    bounds = [s0, *cuts, e0]
    out = [round(x, 3) for x in bounds]
    for i in range(1, len(out)):  # tăng ngặt ở độ phân giải ms
        if out[i] <= out[i - 1]:
            out[i] = round(out[i - 1] + 0.001, 3)
    return [(out[i], out[i + 1]) for i in range(n)]


def _match_cuts(expected: list[float], windows: list[float], mids: list[float], lengths: list[float]) -> list[float]:
    """Gán mỗi ranh giới tối đa một khoảng lặng (không dùng lại, giữ thứ tự) — quy hoạch động, chi phí = độ lệch /
    cửa sổ (+ phạt nhẹ khoảng lặng ngắn); không gán được → điểm cắt kỳ vọng, kẹp giữa hai ranh giới đã gán."""
    nb, ns = len(expected), len(mids)
    if nb == 0:
        return []
    miss = 1.5
    inf = float("inf")
    dp = [[inf] * (ns + 1) for _ in range(nb + 1)]
    back: list[list[tuple[int, int, bool] | None]] = [[None] * (ns + 1) for _ in range(nb + 1)]
    dp[0] = [0.0] * (ns + 1)
    for i in range(nb + 1):
        for j in range(ns + 1):
            cur = dp[i][j]
            if cur == inf:
                continue
            if j < ns and cur < dp[i][j + 1]:  # bỏ qua khoảng lặng j (ngắt nghỉ trong câu)
                dp[i][j + 1], back[i][j + 1] = cur, (i, j, False)
            if i < nb:
                if cur + miss < dp[i + 1][j]:  # ranh giới i không có khoảng lặng
                    dp[i + 1][j], back[i + 1][j] = cur + miss, (i, j, False)
                if j < ns and abs(mids[j] - expected[i]) <= windows[i]:
                    c = cur + abs(mids[j] - expected[i]) / windows[i] + 0.3 * (1 - min(lengths[j] / 0.4, 1))
                    if c < dp[i + 1][j + 1]:
                        dp[i + 1][j + 1], back[i + 1][j + 1] = c, (i, j, True)
    j = min(range(ns + 1), key=lambda k: dp[nb][k])
    i = nb
    chosen: list[float | None] = [None] * nb
    while i > 0:
        pi, pj, used = back[i][j]
        if used:
            chosen[pi] = mids[pj]
        i, j = pi, pj
    cuts: list[float] = []
    for k in range(nb):
        if chosen[k] is not None:
            cuts.append(chosen[k])
            continue
        lo = cuts[-1] if cuts else -inf
        hi = next((c for c in chosen[k + 1:] if c is not None), inf)
        x = expected[k]
        if not lo < x < hi:
            x = (lo + hi) / 2 if lo > -inf and hi < inf else (lo + 0.001 if lo > -inf else hi - 0.001)
        cuts.append(x)
    return cuts


def run_voice(root: Path, cfg: Config, client: SpeechClient, *, preset: Preset | None = None,
              sleep: Callable[[float], None] = time.sleep, on_progress: Callable[[int, int], None] | None = None,
              mode: str | None = None) -> float:
    """Đọc phần chưa có trong cache, ghép voice.wav, điền start/end. Trả độ dài voice.wav (giây).
    `mode` None = theo cài đặt video. Lỗi giữa chừng → giữ phần đã đọc, báo VidflowError; chạy lại sẽ tiếp tục."""
    root = Path(root)
    q = load_quick(root)
    mode = check_voice_mode(mode or q.voice_mode)
    preset = preset or load_preset(q.preset)
    beats = require_beats(root)
    if mode == "per_beat":
        _tts_per_beat(root, cfg, client, preset, beats, sleep, on_progress)
        return _merge(root, beats, lambda bs: [(_read_pcm(_beat_wav(root, b.n)), None) for b in bs])
    chunks = _tts_chunks(root, cfg, client, preset, beats, mode, sleep, on_progress)

    def pieces(bs: list[Beat]):
        out = []
        for g, h in chunks:
            pcm = _read_pcm(_chunk_wav(root, h))
            out.append((pcm, align_chunk(array("h", pcm), RATE, [bs[i].text.strip() for i in g])))
        return out

    return _merge(root, beats, pieces)


def _tts_per_beat(root: Path, cfg: Config, client: SpeechClient, preset: Preset, beats: Beats,
                  sleep: Callable[[float], None], on_progress: Callable[[int, int], None] | None) -> None:
    """Mỗi mốc một lượt TTS → audio/beats/NNN.wav (bỏ qua mốc đã có trong cache)."""
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


def _merge(root: Path, beats: Beats, pieces: Callable[[list[Beat]], list[tuple[bytes, list | None]]]) -> float:
    """Ghép các mảnh PCM (cách nhau GAP_S) thành voice.wav và điền start/end tuyệt đối.
    `pieces(beats)` trả [(pcm, mốc trong mảnh | None)] theo thứ tự; None = mảnh là đúng một mốc (cả mảnh).
    TTS chạy lâu nên không giữ khóa; phần này chạy dưới khóa, trên beats.json đọc lại (giữ thay đổi của tiến
    trình khác trong lúc đọc), và từ chối nếu lời thoại đã đổi giữa chừng."""
    spoken = [(b.n, b.text.strip()) for b in beats.beats]
    with project_lock(root):
        beats = require_beats(root)
        if [(b.n, b.text.strip()) for b in beats.beats] != spoken:
            raise VidflowError("Lời thoại đã đổi trong lúc đọc — chạy lại `vidflow quick voice`.")
        gap = b"\x00\x00" * int(round(GAP_S * RATE))
        frames = 0
        voice = root / VOICE_FILE
        tmp = voice.with_suffix(".tmp.wav")
        it = iter(beats.beats)
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            for i, (pcm, times) in enumerate(pieces(beats.beats)):
                if i:
                    w.writeframes(gap)
                    frames += len(gap) // 2
                base = frames / RATE
                n = len(pcm) // 2
                for s, e in (times or [(0.0, n / RATE)]):
                    b = next(it)
                    b.start, b.end = round(base + s, 3), round(base + e, 3)
                frames += n
                w.writeframes(pcm)
        beats.beats[0].start = 0.0  # video bắt đầu từ mốc 1 (giống cách đọc từng câu)
        tmp.replace(voice)
        save_beats(root, beats)
        _advance(root, "voiced")
    return frames / RATE


def gemini_voice(root: Path, cfg: Config, **kw) -> float:
    """Bản thật: Gemini TTS (free tier) — dùng cho CLI/UI."""
    from vidflow.gemini import GeminiSpeechClient

    return run_voice(root, cfg, GeminiSpeechClient(), **kw)
