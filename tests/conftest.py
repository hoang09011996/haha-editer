import subprocess
import wave
from pathlib import Path

import pytest

from vidflow.config import Config
from vidflow.project import create_project

SAMPLE = """\
title: "Buổi sáng của An"
aspect: "9:16"
prompt_language: vi
style: "cinematic, warm tone"
characters:
  - id: an
    description: "cô gái 25 tuổi, tóc ngắn đen, áo sơ mi trắng"
voice: { name: "Kore", style: "ấm áp", speed: 1.0 }
music: null
subtitles: { enabled: true, max_chars_per_line: 20 }
budget_usd: 10
scenes:
  - id: s01
    narration: "Mỗi sáng, An bắt đầu ngày mới."
    veo_prompt: "Close-up of a young woman sipping coffee."
    characters: [an]
    duration: 8
    status: approved
  - id: s02
    narration: ""
    veo_prompt: "Wide shot of a sunny street."
    duration: 4
    status: approved
  - id: s03
    narration: "Cảnh chưa duyệt."
    veo_prompt: "A park."
    duration: 6
    status: draft
"""


@pytest.fixture
def project(tmp_path: Path):
    p = create_project(tmp_path / "demo", title="Demo", aspect="9:16")
    p.script_path.write_text(SAMPLE, encoding="utf-8")
    return p


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    return Config(veo_price_per_second=0.5, image_model="test-image-model", draft_folder=drafts,
                  media_folder=tmp_path / "movies_media")


def write_wav(path: Path, seconds: float, rate: int = 24000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return path


def make_mp4(path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=216x384:rate=30",
                    "-t", str(seconds), "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


# ---- quy trình nhanh (spec 2026-10-12) ----

@pytest.fixture
def quick_presets(tmp_path, monkeypatch):
    """Bản sao bộ kênh doodle-giai-ma có @MODERNYOU, trong tmp — không ghi vào presets/ thật."""
    import vidflow.quick.preset as pm
    from vidflow.quick.model import Character

    d = tmp_path / "presets"
    p = pm.load_preset("doodle-giai-ma")
    p.characters = [Character(id="MODERNYOU", name="Người hiện đại",
                              desc="round-headed modern person in a cobalt t-shirt", color="#3557D6")]
    pm.save_preset(p, presets_dir=d)
    monkeypatch.setattr(pm, "PRESETS_DIR", d)
    return d


@pytest.fixture
def qroot(tmp_path, quick_presets):
    """Project nhanh 4 mốc A–D, mỗi mốc 4 giây (0, 4, 8, 12)."""
    from vidflow.quick import ops
    from vidflow.quick.model import create_quick, load_beats, save_beats

    root = tmp_path / "vid"
    create_quick(root, preset="doodle-giai-ma", title="T")
    ops.set_beat_texts(root, ["A.", "B.", "C.", "D."])
    b = load_beats(root)
    for i, beat in enumerate(b.beats):
        beat.start, beat.end = i * 4.0, i * 4.0 + 4.0
    save_beats(root, b)
    return root


@pytest.fixture
def P(quick_presets):
    """P("mô tả") → prompt ảnh có đủ câu neo của bộ kênh."""
    import vidflow.quick.preset as pm

    pr = pm.load_preset("doodle-giai-ma")
    return lambda s: f"{pr.style_anchor_start} {s}, {pr.style_anchor_end}"


@pytest.fixture
def img(tmp_path):
    def make(name="a.png", data=b"\x89PNGx"):
        f = tmp_path / "dl" / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        return f
    return make
