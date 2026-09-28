import shutil

import pytest

from conftest import make_mp4, write_wav
from vidflow.errors import VidflowError
from vidflow.media import ensure_wav, floor_ms, probe_duration, wav_duration


def test_wav_passthrough(tmp_path):
    p = write_wav(tmp_path / "a.wav", 1.5)
    data = p.read_bytes()
    assert ensure_wav(data) is data
    assert wav_duration(p) == pytest.approx(1.5)


def test_raw_pcm_is_wrapped(tmp_path):
    pcm = b"\x00\x00" * 24000 * 2  # 2s PCM 16-bit mono 24kHz
    out = tmp_path / "b.wav"
    out.write_bytes(ensure_wav(pcm))
    assert out.read_bytes()[:4] == b"RIFF"
    assert wav_duration(out) == pytest.approx(2.0)


def test_floor_ms():
    assert floor_ms(1.23499) == 1.234


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="cần ffprobe")
def test_probe_duration(tmp_path):
    p = make_mp4(tmp_path / "c.mp4", 2)
    assert probe_duration(p) == pytest.approx(2.0, abs=0.05)


def test_probe_missing_file(tmp_path):
    with pytest.raises(VidflowError, match="ffprobe"):
        probe_duration(tmp_path / "none.mp4")


def test_floor_ms_keeps_exact_milliseconds():
    assert all(floor_ms(x / 1000) == x / 1000 for x in range(0, 20000))
