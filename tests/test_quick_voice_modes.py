"""Cách đọc giọng: per_beat | chunk | full — chia đoạn, căn mốc trong audio đoạn, cache + chạy tiếp."""
import io
import math
import random
import wave
from array import array

import pytest
import yaml

from vidflow.config import Config
from vidflow.errors import VidflowError
from vidflow.media import wav_duration
from vidflow.quick import ops
from vidflow.quick.model import Beat, Beats, create_quick, load_beats, load_quick, save_beats
from vidflow.quick.preset import load_preset
from vidflow.quick.voice import CHUNK_BEATS, GAP_S, align_chunk, chunk_groups, run_voice

RATE = 24000
PRESET = "doodle-giai-ma"


# ---------- PCM tổng hợp ----------

def tone(seconds: float, amp: int = 8000) -> list[int]:
    n = int(round(seconds * RATE))
    return [int(amp * math.sin(2 * math.pi * 220 * i / RATE)) for i in range(n)]


def silence(seconds: float) -> list[int]:
    return [0] * int(round(seconds * RATE))


def build(parts) -> list[int]:
    out: list[int] = []
    for kind, secs in parts:
        out += tone(secs) if kind == "t" else silence(secs)
    return out


def close(got, want, tol=0.012):
    assert len(got) == len(want), (got, want)
    for (gs, ge), (ws, we) in zip(got, want):
        assert abs(gs - ws) <= tol and abs(ge - we) <= tol, (got, want)


# ---------- align_chunk ----------

def test_align_recovers_exact_cuts_ignoring_short_pause():
    pcm = build([("s", 0.2), ("t", 1.0), ("s", 0.3), ("t", 0.9), ("s", 0.15), ("t", 1.0), ("s", 0.3),
                 ("t", 0.8), ("s", 0.25)])
    texts = ["a" * 10, "b b " * 5 + "b" * 10, "c" * 8]  # 10, 20, 8 ký tự (không tính dấu cách)
    got = align_chunk(pcm, RATE, texts)
    close(got, [(0.2, 1.35), (1.35, 3.7), (3.7, 4.65)])


def test_align_missing_silence_falls_back_to_proportional():
    pcm = build([("t", 2.0), ("s", 0.3), ("t", 1.0)])
    got = align_chunk(pcm, RATE, ["a" * 10, "b" * 10, "c" * 10])
    close(got, [(0.0, 1.1), (1.1, 2.15), (2.15, 3.3)])


def test_align_single_beat_trims_edges():
    pcm = build([("s", 0.3), ("t", 1.0), ("s", 0.4)])
    close(align_chunk(pcm, RATE, ["Một câu."]), [(0.3, 1.3)])


def test_align_all_silent_is_proportional():
    got = align_chunk(silence(2.0), RATE, ["aa", "bb"])
    close(got, [(0.0, 1.0), (1.0, 2.0)])


def test_align_always_monotonic():
    rnd = random.Random(7)
    for _ in range(30):
        parts = [("s", rnd.uniform(0, 0.3))]
        for _ in range(rnd.randint(1, 12)):
            parts += [("t", rnd.uniform(0.05, 1.5)), ("s", rnd.choice([0.0, 0.05, 0.13, 0.4]))]
        pcm = build(parts)
        texts = ["x" * rnd.randint(1, 60) for _ in range(rnd.randint(1, 25))]
        got = align_chunk(pcm, RATE, texts)
        assert len(got) == len(texts)
        for s, e in got:
            assert s < e
        for (_, e), (s, _) in zip(got, got[1:]):
            assert s == e
        assert got[0][0] >= 0 and got[-1][1] <= round(len(pcm) / RATE, 3) + 0.001


# ---------- chia đoạn ----------

def test_chunk_groups_caps_beats_and_chars():
    assert [len(g) for g in chunk_groups(["Câu."] * 45, "chunk")] == [20, 20, 5]
    assert [len(g) for g in chunk_groups(["a" * 400] * 7, "chunk")] == [3, 3, 1]
    assert [len(g) for g in chunk_groups(["a" * 400] * 45, "full")] == [45]
    assert [len(g) for g in chunk_groups(["Câu."] * 3, "per_beat")] == [1, 1, 1]
    # nhóm là chỉ số mốc liên tiếp, phủ đủ
    groups = chunk_groups([f"Câu {i}." for i in range(45)], "chunk")
    assert [i for g in groups for i in g] == list(range(45))
    assert CHUNK_BEATS == 20


def test_chunk_groups_edit_stays_inside_block():
    texts = ["a" * 100] * 45
    before = chunk_groups(texts, "chunk")
    texts[3] = "a" * 700  # khối 20 câu đầu tách lại, các khối sau giữ nguyên
    after = chunk_groups(texts, "chunk")
    assert [g for g in after if g[0] >= 20] == [g for g in before if g[0] >= 20]


# ---------- run_voice theo đoạn ----------

def secs_of(text: str) -> float:
    return 0.05 * len(text.replace(" ", ""))


def chunk_wav(texts: list[str]) -> bytes:
    parts = [("s", 0.1)]
    for i, t in enumerate(texts):
        if i:
            parts.append(("s", 0.3))
        parts.append(("t", secs_of(t)))
    parts.append(("s", 0.2))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(array("h", build(parts)).tobytes())
    return buf.getvalue()


class Quota(Exception):
    code = 429


class ChunkSpeech:
    """Mỗi dòng = một tông 0.05 s/ký tự, các dòng cách nhau 0.3 s im lặng; đoạn chứa 'HỎNG' lỗi quota."""

    def __init__(self, fail_on: str | None = None):
        self.calls: list[str] = []
        self.fail_on = fail_on

    def synthesize(self, *, text, voice, style, model):
        self.calls.append(text)
        if self.fail_on and self.fail_on in text:
            raise Quota("quota")
        return chunk_wav(text.split("\n"))


def texts_n(n: int) -> list[str]:
    return [f"Câu số {i} dài {'x' * (i % 7 + 3)}." for i in range(1, n + 1)]


@pytest.fixture
def root45(tmp_path):
    root = tmp_path / "v"
    create_quick(root, preset=PRESET, title="T")
    save_beats(root, Beats(beats=[Beat(n=i, text=t) for i, t in enumerate(texts_n(45), 1)]))
    return root


def run(root, client, mode=None):
    return run_voice(root, Config(), client, preset=load_preset(PRESET), sleep=lambda s: None, mode=mode)


def expected_times(texts: list[str]) -> list[tuple[float, float]]:
    """Mốc tuyệt đối theo cấu trúc ChunkSpeech + GAP_S giữa các đoạn."""
    out, offset = [], 0.0
    for g in chunk_groups(texts, "chunk"):
        t = 0.1
        for k, i in enumerate(g):
            d = secs_of(texts[i])
            start = t if k == 0 else t - 0.15
            end = t + d + (0.15 if k < len(g) - 1 else 0)
            out.append((offset + start, offset + end))
            t += d + 0.3
        offset += t - 0.3 + 0.2 + GAP_S
    return out


def test_chunk_mode_default_one_call_per_chunk(root45):
    c = ChunkSpeech()
    total = run(root45, c)
    texts = texts_n(45)
    assert c.calls == ["\n".join(texts[:20]), "\n".join(texts[20:40]), "\n".join(texts[40:])]
    out = root45 / "audio" / "voice.wav"
    assert abs(wav_duration(out) - total) < 0.002
    b = load_beats(root45).beats
    assert b[0].start == 0.0
    want = expected_times(texts)
    for x, (ws, we) in zip(b[1:], want[1:]):
        assert abs(x.start - ws) < 0.015 and abs(x.end - we) < 0.015, (x.n, x.start, x.end, ws, we)
    for prev, cur in zip(b, b[1:]):
        assert prev.start < prev.end <= cur.start
    s = ops.status_summary(root45)
    assert s["stage"] == "voiced" and s["beats"]["voiced"] == 45 and s["voice_mode"] == "chunk"


def test_chunk_resume_edit_and_mode_switch(root45):
    b = load_beats(root45)
    b.beats[25].text = "HỎNG giữa chừng."
    save_beats(root45, b)
    with pytest.raises(VidflowError, match="đã đọc 1/3 đoạn"):
        run(root45, ChunkSpeech(fail_on="HỎNG"))
    assert not (root45 / "audio" / "voice.wav").exists()
    assert ops.status_summary(root45)["beats"]["voiced"] == 20

    texts = texts_n(45)
    b = load_beats(root45)
    b.beats[25].text = texts[25]
    save_beats(root45, b)
    good = ChunkSpeech()
    run(root45, good)
    assert good.calls == ["\n".join(texts[20:40]), "\n".join(texts[40:])]  # đoạn 1 lấy từ cache

    again = ChunkSpeech()
    run(root45, again)
    assert again.calls == []

    b = load_beats(root45)
    b.beats[41].text = "Câu sửa lại."
    save_beats(root45, b)
    edit = ChunkSpeech()
    run(root45, edit)
    assert len(edit.calls) == 1 and "Câu sửa lại." in edit.calls[0]

    full = ChunkSpeech()
    run(root45, full, mode="full")
    assert len(full.calls) == 1 and full.calls[0].count("\n") == 44
    back = ChunkSpeech()
    run(root45, back, mode="chunk")
    assert back.calls == []  # cache của chế độ khác vẫn còn


def test_timeout_hint_and_chunk_count(root45):
    class Slow(ChunkSpeech):
        def synthesize(self, **kw):
            raise TimeoutError("hết giờ")

    with pytest.raises(VidflowError, match="đã đọc 0/3 đoạn.*hết lượt TTS miễn phí"):
        run(root45, Slow())


def test_chunk_rejects_text_changed_mid_run(root45):
    class Edit(ChunkSpeech):
        def synthesize(self, **kw):
            if not self.calls:
                ops.set_beat_texts(root45, ["Khác hẳn."], aspect="16:9")
            return super().synthesize(**kw)

    with pytest.raises(VidflowError, match="đổi"):
        run(root45, Edit())
    assert load_beats(root45).beats[0].start is None


def test_per_beat_mode_from_settings(root45):
    ops.update_settings(root45, voice_mode="per_beat")
    c = ChunkSpeech()
    run(root45, c)
    assert len(c.calls) == 45 and "\n" not in "".join(c.calls)
    assert ops.status_summary(root45)["beats"]["voiced"] == 45


def test_bad_mode_override(root45):
    with pytest.raises(VidflowError, match="Cách đọc"):
        run(root45, ChunkSpeech(), mode="xyz")


# ---------- model / settings ----------

def test_voice_mode_default_and_old_yaml(tmp_path):
    root = tmp_path / "v"
    create_quick(root, preset=PRESET)
    assert load_quick(root).voice_mode == "chunk"
    data = yaml.safe_load((root / "quick.yaml").read_text(encoding="utf-8"))
    data.pop("voice_mode")
    (root / "quick.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert load_quick(root).voice_mode == "chunk"
    ops.update_settings(root, voice_mode="full")
    assert load_quick(root).voice_mode == "full"
    with pytest.raises(VidflowError, match="Cách đọc"):
        ops.update_settings(root, voice_mode="nhanh")
    assert ops.status_summary(root)["voice_mode"] == "full"


# ---------- CLI ----------

def test_cli_settings_and_voice_mode(root45, monkeypatch):
    from typer.testing import CliRunner

    import vidflow.gemini
    from vidflow.cli import app

    made: list[ChunkSpeech] = []

    def fake_client():
        made.append(ChunkSpeech())
        return made[-1]

    monkeypatch.setattr(vidflow.gemini, "GeminiSpeechClient", fake_client)
    r = CliRunner().invoke(app, ["quick", "settings", "-p", str(root45), "--voice-mode", "full"])
    assert r.exit_code == 0, r.output
    assert load_quick(root45).voice_mode == "full" and "full" in r.output
    r = CliRunner().invoke(app, ["quick", "settings", "-p", str(root45), "--voice-mode", "x"])
    assert r.exit_code == 1 and "Cách đọc" in r.output
    r = CliRunner().invoke(app, ["quick", "voice", "-p", str(root45), "--mode", "chunk"])
    assert r.exit_code == 0, r.output
    assert len(made[-1].calls) == 3 and "3/3" in r.output
    r = CliRunner().invoke(app, ["quick", "voice", "-p", str(root45)])  # theo cài đặt: full
    assert r.exit_code == 0, r.output
    assert len(made[-1].calls) == 1
    r = CliRunner().invoke(app, ["quick", "voice", "-p", str(root45), "--mode", "bad"])
    assert r.exit_code == 1 and "Cách đọc" in r.output


def test_tts_deadline_grows_with_text():
    from vidflow.gemini import tts_deadline

    assert tts_deadline("Một câu.") == 90
    assert tts_deadline("a" * 1500) == pytest.approx(225)


def test_tts_deadline_is_capped():
    from vidflow.gemini import TTS_MAX_S, tts_deadline

    assert tts_deadline("a" * 20000) == TTS_MAX_S == 300


def test_chunk_timeout_not_retried(root45):
    calls = []

    class Hang:
        def synthesize(self, **kw):
            calls.append(1)
            raise TimeoutError("Không phản hồi sau 225 giây")

    with pytest.raises(VidflowError, match="hết lượt"):
        run(root45, Hang(), mode="chunk")
    assert len(calls) == 1  # treo vì hết lượt → không thử lại 3 lần


def test_full_mode_refuses_long_script(tmp_path):
    root = tmp_path / "long"
    create_quick(root, preset=PRESET, title="T")
    save_beats(root, Beats(beats=[Beat(n=i, text="x" * 200) for i in range(1, 21)]))  # 4000 ký tự
    with pytest.raises(VidflowError, match="Theo đoạn"):
        run(root, None, mode="full")
