import subprocess
import wave
from pathlib import Path

import pytest

from vidflow.config import Config
from vidflow.project import create_project

SAMPLE = """\
title: "Buổi sáng của An"
aspect: "9:16"
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
