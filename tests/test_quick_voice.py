import io
import wave

import pytest

from vidflow.config import Config
from vidflow.errors import VidflowError
from vidflow.media import wav_duration
from vidflow.quick.model import Beat, Beats, create_quick, load_beats, save_beats
from vidflow.quick.ops import status_summary
from vidflow.quick.preset import load_preset
from vidflow.quick.voice import GAP_S, run_voice

RATE = 24000


def pcm(seconds: float) -> bytes:
    return b"\x01\x00" * int(round(seconds * RATE))


def wav(seconds: float) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm(seconds))
    return buf.getvalue()


class Transient(Exception):
    code = 429


class FakeSpeech:
    """Độ dài = 0.5s + 0.1s mỗi ký tự; câu chứa 'HỎNG' luôn lỗi quota."""

    def __init__(self, fail_on: str | None = None):
        self.calls: list[str] = []
        self.fail_on = fail_on

    def synthesize(self, *, text, voice, style, model):
        self.calls.append(text)
        if self.fail_on and self.fail_on in text:
            raise Transient("quota")
        secs = 0.5 + 0.1 * len(text)
        # xen kẽ WAV có header và PCM thô như Gemini có thể trả
        return wav(secs) if len(self.calls) % 2 else pcm(secs)


TEXTS = ["Một.", "Câu hai dài hơn.", "Ba.", "Câu bốn khá là dài đấy nhé.", "Năm!"]


def dur(t):
    return 0.5 + 0.1 * len(t)


@pytest.fixture
def qroot(tmp_path):
    root = tmp_path / "v"
    create_quick(root, preset="doodle-giai-ma", title="T")
    save_beats(root, Beats(aspect="16:9", beats=[Beat(n=i + 1, text=t) for i, t in enumerate(TEXTS)]))
    return root


def run(root, client):
    return run_voice(root, Config(), client, preset=load_preset("doodle-giai-ma"), sleep=lambda s: None)


def test_voice_concat_and_timings(qroot):
    c = FakeSpeech()
    run(qroot, c)
    assert c.calls == TEXTS
    total = sum(dur(t) for t in TEXTS) + GAP_S * (len(TEXTS) - 1)
    out = qroot / "audio" / "voice.wav"
    assert abs(wav_duration(out) - total) < 0.002
    with wave.open(str(out)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, RATE)
    b = load_beats(qroot).beats
    assert b[0].start == 0.0
    for prev, cur in zip(b, b[1:]):
        assert prev.end > prev.start
        assert abs(cur.start - (prev.end + GAP_S)) < 0.002
    for x, t in zip(b, TEXTS):
        assert abs((x.end - x.start) - dur(t)) < 0.002
    assert abs(b[-1].end - total) < 0.002
    s = status_summary(qroot)
    assert s["beats"]["voiced"] == 5
    assert abs(s["voice_s"] - total) < 0.01
    assert s["stage"] == "voiced"


def test_voice_resume_after_failure_and_cache(qroot):
    b = load_beats(qroot)
    b.beats[2].text = "HỎNG ba."
    save_beats(qroot, b)
    bad = FakeSpeech(fail_on="HỎNG")
    with pytest.raises(VidflowError, match="2/5"):
        run(qroot, bad)
    assert not (qroot / "audio" / "voice.wav").exists()
    assert status_summary(qroot)["beats"]["voiced"] == 2
    b = load_beats(qroot)
    b.beats[2].text = "Ba."
    save_beats(qroot, b)
    good = FakeSpeech()
    run(qroot, good)
    assert good.calls == TEXTS[2:]  # 2 câu đầu lấy từ cache
    again = FakeSpeech()
    run(qroot, again)
    assert again.calls == []  # cache trúng hết
    b = load_beats(qroot)
    b.beats[0].text = "Một sửa."
    save_beats(qroot, b)
    edit = FakeSpeech()
    run(qroot, edit)
    assert edit.calls == ["Một sửa."]
    assert load_beats(qroot).beats[1].start > 0.5 + 0.1 * len("Một sửa.")


def test_voice_without_beats(tmp_path):
    root = tmp_path / "v"
    create_quick(root, preset="doodle-giai-ma", title="T")
    with pytest.raises(VidflowError, match="script"):
        run(root, FakeSpeech())
