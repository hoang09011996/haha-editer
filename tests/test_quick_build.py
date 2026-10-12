import sys
import types

import pytest

from vidflow.config import Config
from vidflow.errors import VidflowError
from vidflow.quick.build import build_quick
from vidflow.quick.model import Beat, Beats, create_quick, load_quick, save_beats


@pytest.fixture
def fake_assemble(monkeypatch):
    calls = []

    def assemble(images_dir, **kw):
        calls.append((images_dir, kw))
        return {"draft": "x"}

    mod = types.ModuleType("vidflow.assemble")
    mod.assemble = assemble
    monkeypatch.setitem(sys.modules, "vidflow.assemble", mod)
    return calls


def test_build_passes_args(tmp_path, fake_assemble):
    root = tmp_path / "myvid"
    create_quick(root, preset="doodle-giai-ma", title="T")
    save_beats(root, Beats(aspect="16:9", beats=[Beat(n=1, start=0.0, end=1.0, text="A.",
                                                      image="images/001_00-00.jpg", status="ok")]))
    (root / "images" / "001_00-00.jpg").write_bytes(b"x")
    (root / "audio" / "voice.wav").write_bytes(b"RIFF")
    cfg = Config()
    res = build_quick(root, cfg)
    assert res == {"draft": "x"}
    images_dir, kw = fake_assemble[0]
    assert images_dir == root / "images"
    assert kw["audio"] == root / "audio" / "voice.wav"
    assert kw["beats"] == root / "beats.json"
    assert kw["name"] == "myvid"
    assert kw["aspect"] == "16:9"
    assert kw["cfg"] is cfg
    assert kw["clips"] == {}
    assert load_quick(root).stage == "built"


def test_build_without_audio_or_timings(tmp_path, fake_assemble):
    root = tmp_path / "v"
    create_quick(root, preset="doodle-giai-ma", title="T")
    (root / "images" / "001_00-00.jpg").write_bytes(b"x")
    build_quick(root, Config(), name="khac")
    _, kw = fake_assemble[0]
    assert kw["audio"] is None and kw["beats"] is None and kw["name"] == "khac"


def test_build_no_images(tmp_path, fake_assemble):
    root = tmp_path / "v"
    create_quick(root, preset="doodle-giai-ma", title="T")
    with pytest.raises(VidflowError, match="ảnh"):
        build_quick(root, Config())
    assert fake_assemble == []


def test_build_cli(tmp_path, fake_assemble):
    from typer.testing import CliRunner
    from vidflow.cli import app
    root = tmp_path / "v"
    create_quick(root, preset="doodle-giai-ma", title="T")
    (root / "images" / "001_00-00.jpg").write_bytes(b"x")
    r = CliRunner().invoke(app, ["quick", "build", "-p", str(root)])
    assert r.exit_code == 0, r.output
    assert len(fake_assemble) == 1


def test_build_passes_ready_clips(tmp_path, fake_assemble):
    from vidflow.quick.model import Clip

    root = tmp_path / "v"
    create_quick(root, preset="doodle-giai-ma", title="T")
    save_beats(root, Beats(aspect="16:9", beats=[
        Beat(n=1, start=0.0, end=1.0, text="A.", image="images/001_00-00.jpg", status="ok",
             clip=Clip(enabled=True, status="ok", file="clips/001_00-00.mp4")),
        Beat(n=2, start=1.0, end=2.0, text="B.", image="images/002_00-01.jpg", status="ok",
             clip=Clip(enabled=True, status="redo", file="clips/002_00-01.mp4"))]))
    for rel in ("images/001_00-00.jpg", "images/002_00-01.jpg", "clips/001_00-00.mp4", "clips/002_00-01.mp4"):
        (root / rel).write_bytes(b"x")
    build_quick(root, Config())
    _, kw = fake_assemble[0]
    assert kw["clips"] == {1: root / "clips" / "001_00-00.mp4"}
