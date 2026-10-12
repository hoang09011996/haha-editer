import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from conftest import write_wav
from vidflow.assemble import Placement, assemble, plan_images
from vidflow.config import Config
from vidflow.errors import CapCutRunningError, VidflowError

SAMPLE_112 = Path("/Users/anhnh/orca/projects/haha-editer/samples/doodle-112")
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")


def touch(d: Path, *names: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        (d / n).write_bytes(b"x")
    return d


def make_png(path: Path, color="red", size="400x300") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s={size}",
                    "-frames:v", "1", str(path)], check=True)
    return path


def write_beats(path: Path, beats: list[dict], aspect="16:9") -> Path:
    path.write_text(json.dumps({"aspect": aspect, "beats": beats}, ensure_ascii=False), encoding="utf-8")
    return path


# ---------- plan_images (thuần, không cần pyCapCut) ----------

def test_plan_from_names_last_plus_4s(tmp_path):
    d = touch(tmp_path / "imgs", "002_00-03.jpg", "001_00-00.jpg", "003_01-05.PNG")
    plan = plan_images(d)
    assert [p.file.name for p in plan] == ["001_00-00.jpg", "002_00-03.jpg", "003_01-05.PNG"]
    assert [(p.start, p.end) for p in plan] == [(0.0, 3.0), (3.0, 65.0), (65.0, 69.0)]
    assert all(isinstance(p, Placement) for p in plan)


def test_plan_last_extends_to_audio(tmp_path):
    d = touch(tmp_path / "imgs", "001_00-00.jpg", "002_00-03.webp")
    plan = plan_images(d, audio_len=10.5)
    assert plan[-1].end == 10.5


def test_plan_beats_override_ms_and_warn(tmp_path):
    d = touch(tmp_path / "imgs", "001_00-00.jpg", "002_00-02.jpg", "003_00-05.jpg")
    beats = write_beats(tmp_path / "beats.json", [
        {"n": 1, "start": 0.0, "end": 2.312, "text": "Một."},
        {"n": 2, "start": 2.312, "end": 5.1, "text": "Hai."},
        {"n": 9, "start": 9.0, "end": 10.0, "text": "Lạc."},
    ])
    warnings: list[str] = []
    plan = plan_images(d, beats=beats, warnings=warnings)
    assert [(p.start, p.end) for p in plan] == [(0.0, 2.312), (2.312, 5.0), (5.0, 9.0)]
    assert any("003_00-05.jpg" in w for w in warnings)  # ảnh không có beat
    assert any("9" in w for w in warnings)  # beat không có ảnh


def test_plan_skips_bad_names(tmp_path):
    d = touch(tmp_path / "imgs", "001_00-00.jpg", "cover.jpg", "2_00-01.jpg", "002_00-01.gif", "003_00-04.jpeg")
    skipped: list[str] = []
    plan = plan_images(d, skipped=skipped)
    assert [p.file.name for p in plan] == ["001_00-00.jpg", "003_00-04.jpeg"]
    assert sorted(skipped) == ["002_00-01.gif", "2_00-01.jpg", "cover.jpg"]


def test_plan_duplicate_nnn_errors(tmp_path):
    d = touch(tmp_path / "imgs", "001_00-00.jpg", "002_00-03.jpg", "002_00-04.png")
    with pytest.raises(VidflowError, match=r"002_00-03\.jpg.*002_00-04\.png|002_00-04\.png.*002_00-03\.jpg"):
        plan_images(d)


def test_plan_decreasing_time_errors(tmp_path):
    d = touch(tmp_path / "imgs", "001_00-00.jpg", "002_00-09.jpg", "003_00-09.jpg")
    with pytest.raises(VidflowError, match=r"002_00-09\.jpg.*003_00-09\.jpg"):
        plan_images(d)


def test_plan_no_images_errors(tmp_path):
    d = touch(tmp_path / "imgs", "readme.txt")
    with pytest.raises(VidflowError, match="readme.txt"):
        plan_images(d)


def test_plan_keeps_beat_number(tmp_path):
    d = touch(tmp_path / "imgs", "001_00-00.jpg", "007_00-03.jpg")
    assert [p.n for p in plan_images(d)] == [1, 7]


# ---------- assemble (pyCapCut, ảnh thật nhỏ) ----------

@pytest.fixture
def acfg(tmp_path):
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    return Config(draft_folder=drafts, media_folder=tmp_path / "media")


@pytest.fixture
def small_images(tmp_path):
    d = tmp_path / "proj" / "images"
    make_png(d / "001_00-00.png", "red")
    make_png(d / "002_00-02.png", "green")
    make_png(d / "003_00-03.png", "blue", size="300x400")
    make_png(d / "004_00-05.png", "yellow")
    return d


def load(draft_dir: Path) -> dict:
    return json.loads((draft_dir / "draft_info.json").read_text(encoding="utf-8"))


def track_segs(content, kind):
    segs = [s for t in content["tracks"] if t["type"] == kind for s in t["segments"]]
    return sorted(segs, key=lambda s: s["target_timerange"]["start"])


def scales(seg):
    return {k["property_type"]: [kf["values"][0] for kf in k["keyframe_list"]] for k in seg["common_keyframes"]}


def run(images, cfg, **kw):
    kw.setdefault("is_running", lambda: False)
    kw.setdefault("stamp", lambda: "S1")
    return assemble(images, cfg=cfg, **kw)


@needs_ffmpeg
def test_assemble_small(small_images, acfg):
    rep = run(small_images, acfg)
    assert rep.draft_dir == acfg.draft_folder / "vidflow_proj"
    assert rep.count == 4 and rep.total_s == pytest.approx(9.0)
    content = load(rep.draft_dir)
    assert (content["canvas_config"]["width"], content["canvas_config"]["height"]) == (1920, 1080)
    segs = track_segs(content, "video")
    assert len(segs) == 4
    t = 0
    for s in segs:  # liền mạch µs: không hở, không chồng
        assert s["target_timerange"]["start"] == t
        t += s["target_timerange"]["duration"]
    assert t == 9_000_000
    # media đã copy sang media_folder/<draft>
    vids = {m["id"]: m for m in content["materials"]["videos"]}
    assert all(str(acfg.media_folder / "vidflow_proj") in m["path"] for m in vids.values())
    # phủ kín: 400x300 → 4/3, 300x400 → 6.4/2.7; zoom xen kẽ vào/ra 1.0↔1.08
    base = [4 / 3, 4 / 3, 6.4 / 2.7, 4 / 3]
    for i, (s, b) in enumerate(zip(segs, base)):
        assert s["clip"]["scale"]["x"] == pytest.approx(b, rel=1e-4)
        kf = scales(s)["KFTypeScaleX"]
        expect = [b, b * 1.08] if i % 2 == 0 else [b * 1.08, b]
        assert kf == pytest.approx(expect, rel=1e-4)


@needs_ffmpeg
def test_assemble_no_zoom_and_aspect(small_images, acfg):
    rep = run(small_images, acfg, zoom=False, aspect="9:16", name="mine")
    content = load(rep.draft_dir)
    assert rep.draft_dir.name == "mine"
    assert (content["canvas_config"]["width"], content["canvas_config"]["height"]) == (1080, 1920)
    assert all(not s["common_keyframes"] for s in track_segs(content, "video"))


@needs_ffmpeg
def test_assemble_auto_portrait_majority(tmp_path, acfg):
    d = tmp_path / "p"
    make_png(d / "001_00-00.png", size="300x400")
    make_png(d / "002_00-01.png", size="300x400")
    make_png(d / "003_00-02.png", size="400x300")
    content = load(run(d, acfg).draft_dir)
    assert (content["canvas_config"]["width"], content["canvas_config"]["height"]) == (1080, 1920)


@needs_ffmpeg
def test_assemble_audio_and_subtitles(small_images, acfg, tmp_path):
    audio = write_wav(tmp_path / "voice.wav", 12.0)
    beats = write_beats(tmp_path / "beats.json", [
        {"n": 1, "start": 0.0, "end": 1.9, "text": "Một."},
        {"n": 2, "start": 2.0, "end": 2.95, "text": "Hai."},
        {"n": 3, "start": 3.0, "end": 4.9, "text": "Ba."},
        {"n": 4, "start": 5.0, "end": 11.0, "text": "Bốn."},
    ])
    rep = run(small_images, acfg, audio=audio, beats=beats)
    content = load(rep.draft_dir)
    assert rep.total_s == pytest.approx(12.0, abs=0.01)
    aud = track_segs(content, "audio")
    assert len(aud) == 1 and aud[0]["target_timerange"]["start"] == 0
    assert str(acfg.media_folder / "vidflow_proj") in content["materials"]["audios"][0]["path"]
    subs = track_segs(content, "text")
    assert len(subs) == 4
    assert subs[1]["target_timerange"] == {"start": 2_000_000, "duration": 950_000}
    texts = [json.loads(m["content"])["text"] for m in content["materials"]["texts"]]
    assert texts == ["Một.", "Hai.", "Ba.", "Bốn."]

    rep2 = run(small_images, acfg, audio=audio, beats=beats, subtitles=False, stamp=lambda: "S2")
    assert not track_segs(load(rep2.draft_dir), "text")
    # draft cũ được backup
    assert (acfg.media_folder / "backups" / "S2" / "vidflow_proj" / "draft_info.json").is_file()


@needs_ffmpeg
def test_assemble_with_clips(small_images, acfg, tmp_path):
    from conftest import make_mp4
    from vidflow.capcut_draft import cover_scale

    long_clip = make_mp4(tmp_path / "dl" / "002_00-02.mp4", 3.0)   # mốc 2 dài 1 s → cắt
    short_clip = make_mp4(tmp_path / "dl" / "004_00-05.mp4", 1.0)  # mốc 4 dài 4 s → làm chậm
    rep = run(small_images, acfg, clips={2: long_clip, 4: short_clip})
    assert rep.count == 4 and rep.clips == 2
    content = load(rep.draft_dir)
    segs = track_segs(content, "video")
    assert len(segs) == 4
    t = 0
    for s in segs:  # vẫn liền mạch
        assert s["target_timerange"]["start"] == t
        t += s["target_timerange"]["duration"]
    assert t == 9_000_000
    vids = {m["id"]: m for m in content["materials"]["videos"]}
    s1, s2, s4 = segs[0], segs[1], segs[3]
    assert str(acfg.media_folder / "vidflow_proj" / "clips") in vids[s2["material_id"]]["path"]
    assert s2["source_timerange"] == {"start": 0, "duration": 1_000_000} and s2["speed"] == 1.0
    assert s2["volume"] == 0.5 and not s2["common_keyframes"]
    assert s2["clip"]["scale"]["x"] == pytest.approx(cover_scale(216, 384, 1920, 1080), rel=1e-4)
    assert s4["target_timerange"]["duration"] == 4_000_000
    assert s4["speed"] == pytest.approx(0.25, rel=0.05)
    assert s1["volume"] == 0.0 and "images" in vids[s1["material_id"]]["path"]


@needs_ffmpeg
def test_assemble_refuses_when_capcut_running(small_images, acfg):
    with pytest.raises(CapCutRunningError):
        run(small_images, acfg, is_running=lambda: True)
    assert not (acfg.draft_folder / "vidflow_proj").exists()


@needs_ffmpeg
def test_cli_assemble(small_images, acfg, tmp_path):
    from typer.testing import CliRunner

    from vidflow.cli import app

    toml = tmp_path / "v.toml"
    toml.write_text(f'draft_folder = "{acfg.draft_folder}"\nmedia_folder = "{acfg.media_folder}"\n')
    (small_images / "notes.txt").write_text("x")
    import vidflow.assemble as mod

    orig = mod.capcut_running
    mod.capcut_running = lambda: False
    try:
        r = CliRunner().invoke(app, ["assemble", "--images", str(small_images), "--no-zoom", "--config", str(toml)])
    finally:
        mod.capcut_running = orig
    assert r.exit_code == 0, r.output
    assert "4 ảnh" in r.output and "notes.txt" in r.output


# ---------- tích hợp: mẫu thật 112 ảnh ----------

@pytest.mark.skipif(not SAMPLE_112.is_dir(), reason="không có samples/doodle-112")
def test_integration_doodle_112(acfg):
    t0 = time.perf_counter()
    rep = run(SAMPLE_112, acfg)
    elapsed = time.perf_counter() - t0
    assert elapsed < 30, elapsed
    assert rep.count == 112 and not rep.skipped_files
    content = load(rep.draft_dir)
    assert (content["canvas_config"]["width"], content["canvas_config"]["height"]) == (1920, 1080)
    segs = track_segs(content, "video")
    assert len(segs) == 112
    assert segs[0]["target_timerange"]["start"] == 0
    assert segs[28]["target_timerange"]["start"] == 125_000_000
    for a, b in zip(segs, segs[1:]):
        assert a["target_timerange"]["start"] + a["target_timerange"]["duration"] == b["target_timerange"]["start"]
    last = segs[-1]["target_timerange"]
    assert last["start"] + last["duration"] == (487 + 4) * 1_000_000


@needs_ffmpeg
def test_assemble_clamps_clip_speed(small_images, acfg, tmp_path):
    from conftest import make_mp4

    tiny = make_mp4(tmp_path / "dl" / "004_00-05.mp4", 0.2)  # mốc 4 dài 4 s → cần x0.05 < 0.1
    rep = run(small_images, acfg, clips={4: tiny})
    s4 = track_segs(load(rep.draft_dir), "video")[3]
    assert s4["speed"] == pytest.approx(0.1, rel=0.01)
    src = s4["source_timerange"]["duration"]
    assert s4["target_timerange"]["duration"] == pytest.approx(src * 10, abs=10)
    assert s4["target_timerange"]["duration"] < 4_000_000
    assert any("4" in w and "0.1" in w for w in rep.warnings)
