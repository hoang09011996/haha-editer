import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import write_wav
from vidflow.cli import app
from vidflow.errors import VidflowError
from vidflow.quick import clips, ops
from vidflow.quick import render as rq
from vidflow.quick.model import load_beats, save_beats
from vidflow.quick.preset import load_preset, save_preset

runner = CliRunner()


def edit(root, fn):
    """Sửa beats.json trong test (fixture qroot cũng làm vậy) — code thật luôn đi qua ops/clips."""
    b = load_beats(root)
    fn(b.beats)
    save_beats(root, b)


def with_images(root, img, ns=(1, 2, 3, 4)):
    for n in ns:
        ops.set_image(root, n, img(f"{n}.png"))


def with_clip(root, img, n):
    clips.set_clip_enabled(root, [n], True)
    clips.set_clip(root, n, img(f"c{n}.mp4", b"mp4"))


def test_canvas_sizes():
    assert rq.canvas("1080p", "16:9") == (1920, 1080)
    assert rq.canvas("720p", "16:9") == (1280, 720)
    assert rq.canvas("1080p", "9:16") == (1080, 1920)
    assert rq.canvas("720p", "9:16") == (720, 1280)
    with pytest.raises(VidflowError, match="1080p"):
        rq.canvas("4k", "16:9")


def test_props_images_only(qroot, img):
    with_images(qroot, img)
    plan = rq.build_render_props(qroot)
    p = plan.props
    assert (p["fps"], p["width"], p["height"]) == (30, 1280, 720)  # flow.resolution mặc định 720p
    assert p["duration"] == 16.0 and p["audio"] is None
    assert [b["kind"] for b in p["beats"]] == ["image"] * 4
    assert p["beats"][1] == {"n": 2, "src": "images/002_00-04.png", "kind": "image", "start": 4.0, "end": 8.0,
                             "cont": False, "fade": 0.3, "rate": 1.0, "clipLen": None}
    assert p["beats"][0]["fade"] == 0.0
    assert [s["text"] for s in p["subtitles"]] == ["A.", "B.", "C.", "D."]
    assert p["zoom"] is True and p["clipVolume"] == 0.5
    assert p["logo"] is None and p["music"] is None and p["musicVolume"] == 0.12
    assert plan.assets["images/002_00-04.png"] == qroot / "images" / "002_00-04.png"
    assert any("voice.wav" in w for w in plan.warnings)


def test_resolution_option_overrides_flow(qroot, img):
    with_images(qroot, img)
    p = rq.build_render_props(qroot, rq.RenderOptions(resolution="1080p")).props
    assert (p["width"], p["height"]) == (1920, 1080)


def test_blank_beats_voice_length_and_gaps(qroot, img):
    with_images(qroot, img, ns=(1, 3))

    def gaps(bs):
        for i, b in enumerate(bs):
            b.start, b.end = i * 4.0, i * 4.0 + 3.85  # khoảng lặng 0.15 s giữa câu như voice.py

    edit(qroot, gaps)
    write_wav(qroot / "audio" / "voice.wav", 20.0)
    plan = rq.build_render_props(qroot)
    p = plan.props
    assert p["duration"] == 20.0 and p["audio"] == "audio/voice.wav"
    assert plan.assets["audio/voice.wav"] == qroot / "audio" / "voice.wav"
    assert [(b["start"], b["end"]) for b in p["beats"]] == [(0.0, 4.0), (4.0, 8.0), (8.0, 12.0), (12.0, 20.0)]
    assert [b["kind"] for b in p["beats"]] == ["image", "blank", "image", "blank"]
    assert p["beats"][1]["src"] is None
    assert p["subtitles"][0] == {"start": 0.0, "end": 3.85, "text": "A."}
    assert any("2 mốc chưa có ảnh" in w and "2, 4" in w for w in plan.warnings)
    assert not any("voice.wav" in w for w in plan.warnings)


def test_duration_is_max_of_voice_and_last_beat(qroot, img):
    with_images(qroot, img)
    write_wav(qroot / "audio" / "voice.wav", 10.0)
    assert rq.build_render_props(qroot).props["duration"] == 16.0


def test_requires_some_image_and_timing(qroot):
    with pytest.raises(VidflowError, match="Chưa có ảnh"):
        rq.build_render_props(qroot)
    edit(qroot, lambda bs: setattr(bs[2], "start", None))
    with pytest.raises(VidflowError, match="quick voice"):
        rq.build_render_props(qroot)


def test_clip_trim_and_speed(qroot, img):
    with_images(qroot, img)
    with_clip(qroot, img, 2)
    with_clip(qroot, img, 3)
    lengths = {"002_00-04.mp4": 2.5, "003_00-08.mp4": 6.0}
    probe = lambda path: lengths[path.name]  # noqa: E731
    plan = rq.build_render_props(qroot, probe=probe)
    b2, b3 = plan.props["beats"][1], plan.props["beats"][2]
    assert (b2["kind"], b2["src"], b2["rate"], b2["clipLen"]) == ("video", "clips/002_00-04.mp4", 1.0, 2.5)
    assert (b3["kind"], b3["rate"], b3["clipLen"]) == ("video", 1.0, 6.0)
    assert plan.assets["clips/002_00-04.mp4"] == qroot / "clips" / "002_00-04.mp4"
    p = rq.build_render_props(qroot, rq.RenderOptions(clip_fit="speed"), probe=probe).props
    assert p["beats"][1]["rate"] == 0.625 and p["beats"][2]["rate"] == 1.5


def test_speed_is_clamped_with_warning(qroot, img):
    with_images(qroot, img)
    with_clip(qroot, img, 1)
    plan = rq.build_render_props(qroot, rq.RenderOptions(clip_fit="speed"), probe=lambda _: 1.0)
    assert plan.props["beats"][0]["rate"] == 0.5
    assert any("Mốc 1" in w and "x0.25" in w for w in plan.warnings)


def test_clip_fallbacks_to_image(qroot, img):
    with_images(qroot, img)
    with_clip(qroot, img, 1)
    with_clip(qroot, img, 2)
    clips.set_clip_enabled(qroot, [1], False)

    def broken(path):
        raise VidflowError("ffprobe không đọc được")

    plan = rq.build_render_props(qroot, probe=broken)
    assert [b["kind"] for b in plan.props["beats"][:2]] == ["image", "image"]
    assert any("Mốc 2" in w and "dùng ảnh" in w for w in plan.warnings)


def test_transitions(qroot, img):
    with_images(qroot, img)
    edit(qroot, lambda bs: setattr(bs[2], "cont", True))

    def fades(t):
        return [b["fade"] for b in rq.build_render_props(qroot, rq.RenderOptions(transition=t)).props["beats"]]

    assert rq.build_render_props(qroot).props["beats"][2]["cont"] is True
    assert fades("scene") == [0.0, 0.3, 0.0, 0.3]
    assert fades("cut") == [0.0, 0.0, 0.0, 0.0]
    assert fades("fade") == [0.0, 0.3, 0.3, 0.3]
    edit(qroot, lambda bs: setattr(bs[1], "start", 7.6))  # mốc 2 chỉ còn 0.4 s → mờ tối đa nửa mốc
    assert fades("fade")[1] == 0.2
    with pytest.raises(VidflowError, match="scene, cut hoặc fade"):
        rq.build_render_props(qroot, rq.RenderOptions(transition="wipe"))
    with pytest.raises(VidflowError, match="trim hoặc speed"):
        rq.build_render_props(qroot, rq.RenderOptions(clip_fit="stretch"))


def test_logo_music_and_switches(qroot, img, quick_presets, tmp_path):
    with_images(qroot, img)
    logo = tmp_path / "brand" / "Logo.PNG"
    logo.parent.mkdir()
    logo.write_bytes(b"png")
    pr = load_preset("doodle-giai-ma")
    pr.logo = str(logo)
    save_preset(pr, presets_dir=quick_presets)
    write_wav(qroot / "audio" / "music.wav", 2.0)
    plan = rq.build_render_props(qroot)
    assert plan.props["logo"] == "logo/logo.png" and plan.assets["logo/logo.png"] == logo
    assert plan.props["music"] == "audio/music.wav"
    assert plan.assets["audio/music.wav"] == qroot / "audio" / "music.wav"
    off = rq.build_render_props(qroot, rq.RenderOptions(zoom=False, subtitles=False, clip_audio=False,
                                                        logo=False, music=False)).props
    assert off["zoom"] is False and off["subtitles"] == [] and off["clipVolume"] == 0.0
    assert off["logo"] is None and off["music"] is None
    logo.unlink()
    plan = rq.build_render_props(qroot)
    assert plan.props["logo"] is None and any("logo" in w for w in plan.warnings)


@pytest.fixture
def remotion(tmp_path):
    """Thư mục remotion/ giả đã 'npm ci' (chỉ cần node_modules/@remotion/cli)."""
    d = tmp_path / "remotion"
    (d / "node_modules" / "@remotion" / "cli").mkdir(parents=True)
    return d


def fake_run(calls, rc=0):
    def run(cmd, **kw):
        calls.append((cmd, kw))
        if rc == 0:
            Path(cmd[5]).write_bytes(b"mp4")
        return subprocess.CompletedProcess(cmd, rc)
    return run


def test_write_props_and_public_dir(qroot, img):
    with_images(qroot, img, ns=(1,))
    (qroot / "out" / "vid-v1.mp4").write_bytes(b"old")
    path, plan = rq.write_render_props(qroot)
    assert path == (qroot / "tmp" / "render-props.json").resolve()
    assert json.loads(path.read_text(encoding="utf-8")) == plan.props
    public = qroot / "tmp" / "render" / "public"
    link = public / "images" / "001_00-00.png"
    # file thường (hard link) — server của Remotion trả 404 cho symlink
    assert not link.is_symlink() and link.samefile(qroot / "images" / "001_00-00.png")
    assert not (public / "out").exists() and not (public / "images" / "002_00-04.png").exists()
    (public / "stray.txt").write_text("x")
    rq.write_render_props(qroot)
    assert not (public / "stray.txt").exists()                     # dựng lại sạch
    assert (qroot / "images" / "001_00-00.png").read_bytes()       # file thật còn nguyên


def test_public_dir_copies_when_hard_link_fails(qroot, img, monkeypatch):
    with_images(qroot, img, ns=(1,))

    def no_link(src, dst):
        raise OSError(18, "Cross-device link")

    monkeypatch.setattr(rq.os, "link", no_link)
    rq.write_render_props(qroot)
    f = qroot / "tmp" / "render" / "public" / "images" / "001_00-00.png"
    assert not f.is_symlink() and f.read_bytes() == (qroot / "images" / "001_00-00.png").read_bytes()


def test_next_output_versions(qroot):
    out = (qroot / "out").resolve()
    assert rq.next_output(qroot) == out / "vid-v1.mp4"
    for name in ("vid-v1.mp4", "vid-v3.mp4", "other-v9.mp4", "vid-v2-test.mp4"):
        (out / name).write_bytes(b"x")
    assert rq.next_output(qroot) == out / "vid-v4.mp4"


def test_render_runs_remotion_with_absolute_paths(qroot, img, remotion, monkeypatch):
    with_images(qroot, img)
    monkeypatch.chdir(qroot.parent)
    calls = []
    res = rq.render_quick(Path("vid"), run=fake_run(calls), remotion_dir=remotion, npx="npx")
    cmd, kw = calls[0]
    root = qroot.resolve()
    assert cmd[:5] == ["npx", "remotion", "render", "src/index.ts", "DoodleVideo"]
    assert cmd[5] == str(root / "out" / "vid-v1.mp4")
    assert cmd[6] == f"--props={root / 'tmp' / 'render-props.json'}"
    assert cmd[7] == f"--public-dir={root / 'tmp' / 'render' / 'public'}"
    assert kw["cwd"] == remotion
    assert res.output == root / "out" / "vid-v1.mp4" and res.output.is_file()
    assert res.props_path == root / "tmp" / "render-props.json" and res.duration == 16.0
    rq.render_quick(qroot, run=fake_run(calls), remotion_dir=remotion, npx="npx")
    assert calls[1][0][5] == str(root / "out" / "vid-v2.mp4")


def test_render_failure_leaves_no_output(qroot, img, remotion):
    with_images(qroot, img)

    def run(cmd, **kw):
        Path(cmd[5]).write_bytes(b"half")  # Remotion chết giữa chừng
        return subprocess.CompletedProcess(cmd, 1)

    with pytest.raises(VidflowError, match="mã 1"):
        rq.render_quick(qroot, run=run, remotion_dir=remotion, npx="npx")
    assert list((qroot / "out").glob("*.mp4")) == []
    assert rq.next_output(qroot).name == "vid-v1.mp4"


def test_render_oserror_is_vidflow_error_and_leaves_no_output(qroot, img, remotion):
    with_images(qroot, img)

    def run(cmd, **kw):
        Path(cmd[5]).write_bytes(b"half")
        raise OSError("exec format error")

    with pytest.raises(VidflowError, match="Không chạy được Remotion"):
        rq.render_quick(qroot, run=run, remotion_dir=remotion, npx="npx")
    assert list((qroot / "out").glob("*.mp4")) == []


def test_render_interrupt_reraises_and_leaves_no_output(qroot, img, remotion):
    with_images(qroot, img)

    def run(cmd, **kw):
        Path(cmd[5]).write_bytes(b"half")
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        rq.render_quick(qroot, run=run, remotion_dir=remotion, npx="npx")
    assert list((qroot / "out").glob("*.mp4")) == []


def test_render_requires_remotion_install_and_npx(qroot, img, remotion, tmp_path, monkeypatch):
    with_images(qroot, img)
    with pytest.raises(VidflowError, match="npm ci"):
        rq.render_quick(qroot, run=fake_run([]), remotion_dir=tmp_path / "nope", npx="npx")
    monkeypatch.setattr(rq.shutil, "which", lambda name: None)
    with pytest.raises(VidflowError, match="npx"):
        rq.render_quick(qroot, run=fake_run([]), remotion_dir=remotion)


def test_cli_render(qroot, img, remotion, monkeypatch):
    with_images(qroot, img)
    calls = []
    monkeypatch.setattr(rq, "REMOTION_DIR", remotion)
    monkeypatch.setattr(rq.subprocess, "run", fake_run(calls))
    monkeypatch.setattr(rq.shutil, "which", lambda name: "/usr/local/bin/npx")
    r = runner.invoke(app, ["quick", "render", "-p", str(qroot), "--resolution", "1080p", "--transition", "cut",
                            "--clip-fit", "speed", "--no-zoom", "--no-subtitles", "--no-clip-audio", "--no-logo",
                            "--no-music"])
    assert r.exit_code == 0, r.output
    assert "vid-v1.mp4" in r.output and calls[0][0][0] == "/usr/local/bin/npx"
    props = json.loads((qroot / "tmp" / "render-props.json").read_text(encoding="utf-8"))
    assert (props["width"], props["zoom"], props["subtitles"], props["clipVolume"]) == (1920, False, [], 0.0)
    assert all(b["fade"] == 0.0 for b in props["beats"])
    r = runner.invoke(app, ["quick", "render", "-p", str(qroot), "--props-only"])
    assert r.exit_code == 0, r.output
    assert "render-props.json" in r.output and len(calls) == 1
    r = runner.invoke(app, ["quick", "render", "-p", str(qroot), "--transition", "wipe"])
    assert r.exit_code == 1 and "Traceback" not in r.output


def test_garbage_voice_wav_is_vidflow_error(qroot, img):
    with_images(qroot, img)
    (qroot / "audio").mkdir(exist_ok=True)
    (qroot / "audio" / "voice.wav").write_bytes(b"not a wav at all")
    with pytest.raises(VidflowError, match="voice.wav hỏng"):
        rq.build_render_props(qroot)
