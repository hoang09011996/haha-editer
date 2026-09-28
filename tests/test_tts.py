import pytest

from conftest import write_wav
from vidflow.tts import run_tts


class FakeSpeech:
    def __init__(self, tmp_path, seconds=2.0):
        self.calls = []
        self.data = write_wav(tmp_path / "fake.wav", seconds).read_bytes()

    def synthesize(self, *, text, voice, style, model):
        self.calls.append({"text": text, "voice": voice, "style": style, "model": model})
        return self.data


def test_generates_for_scenes_with_narration(project, cfg, tmp_path):
    fake = FakeSpeech(tmp_path)
    done = run_tts(project, cfg, fake)
    assert done == ["s01", "s03"]
    assert fake.calls[0] == {"text": "Mỗi sáng, An bắt đầu ngày mới.", "voice": "Kore", "style": "ấm áp",
                             "model": "gemini-3.8-flash-tts"}
    st = project.load_state()
    assert st.scenes["s01"].tts.file == "audio/s01.wav"
    assert st.scenes["s01"].tts.duration_s == pytest.approx(2.0)
    assert (project.root / "audio/s01.wav").is_file()
    assert "s02" not in st.scenes or st.scenes["s02"].tts is None


def test_skips_unchanged_and_redoes_changed(project, cfg, tmp_path):
    fake = FakeSpeech(tmp_path)
    run_tts(project, cfg, fake)
    assert run_tts(project, cfg, fake) == []
    text = project.script_path.read_text(encoding="utf-8").replace("bắt đầu ngày mới", "thức dậy")
    project.script_path.write_text(text, encoding="utf-8")
    assert run_tts(project, cfg, fake) == ["s01"]
    assert run_tts(project, cfg, fake, scene_ids=["s03"], force=True) == ["s03"]


def test_missing_audio_file_regenerates(project, cfg, tmp_path):
    fake = FakeSpeech(tmp_path)
    run_tts(project, cfg, fake)
    (project.root / "audio/s01.wav").unlink()
    assert run_tts(project, cfg, fake) == ["s01"]
