import shutil
import subprocess

import pytest

from conftest import write_wav
from vidflow.frames import import_frame
from vidflow.media import probe_duration
from vidflow.render import planned_durations, render_hash, run_render
from vidflow.state import TtsResult
from vidflow.status import scene_rows

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")


def png(path, color="red", size="400x300"):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s={size}",
                    "-frames:v", "1", str(path)], check=True)
    return path


def make(project, cfg, tmp_path, mode, n=3, extra="", voice=None, frame_extra=""):
    frames = "\n".join(f"      - {{id: f{i:02d}, prompt: \"p{i}\", status: approved, seconds: 1.0{frame_extra}}}" for i in range(1, n + 1))
    project.script_path.write_text(f"""title: T
aspect: "9:16"
scenes:
  - id: s01
    mode: {mode}
    status: approved
    narration: "{'có lời' if voice else ''}"
{extra}    frames:
{frames}
""", encoding="utf-8")
    colors = ["red", "green", "blue", "yellow", "white", "gray"]
    for i in range(1, n + 1):
        import_frame(project, cfg, "s01", f"f{i:02d}", png(tmp_path / f"i{i}.png", colors[i % len(colors)]), now=lambda: "T")
    if voice:
        write_wav(project.audio_dir / "s01.wav", voice)
        st = project.load_state()
        st.scene("s01").tts = TtsResult(file="audio/s01.wav", duration_s=voice, input_hash="h")
        project.save_state(st)


def size(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return r.stdout.strip()


def pixel(path, t, x, y):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                        "-vf", f"format=rgb24,crop=1:1:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    return tuple(r.stdout[:3])


def test_slideshow_length_size_and_take(project, cfg, tmp_path):
    make(project, cfg, tmp_path, "slideshow", n=3)
    rep = run_render(project, cfg, now=lambda: "T")
    assert rep["created"] == ["clips/s01_r1.mp4"] and rep["skipped"] == {}
    clip = project.root / "clips/s01_r1.mp4"
    assert probe_duration(clip) == pytest.approx(3.0, abs=0.08)
    assert size(clip) == "1080,1920"
    st = project.load_state().scenes["s01"]
    assert st.takes[0].source == "render" and st.picked == 0


def test_slideshow_stretches_to_voice(project, cfg, tmp_path):
    make(project, cfg, tmp_path, "slideshow", n=2, voice=3.0, extra="    transition: cut\n")
    run_render(project, cfg, now=lambda: "T")
    assert probe_duration(project.root / "clips/s01_r1.mp4") == pytest.approx(3.3, abs=0.08)


def test_stopmotion_loops(project, cfg, tmp_path):
    make(project, cfg, tmp_path, "stopmotion", n=4, voice=2.0, extra="    fps: 8\n")
    script, state = project.load_script(), project.load_state()
    durs = planned_durations(script, state, script.scenes[0])
    assert sum(durs) == pytest.approx(2.3, abs=1e-6) and len(durs) >= 18 and durs[0] == pytest.approx(0.125)
    run_render(project, cfg, now=lambda: "T")
    assert probe_duration(project.root / "clips/s01_r1.mp4") == pytest.approx(2.3, abs=0.08)


def test_comic_has_white_bubble(project, cfg, tmp_path):
    make(project, cfg, tmp_path, "comic", n=1, frame_extra=', caption: "Ủa, sao chua thế này trời ơi, ai bày trend vậy!", motion: static')
    run_render(project, cfg, now=lambda: "T")
    clip = project.root / "clips/s01_r1.mp4"
    top = pixel(clip, 0.5, 60, 130)      # trong bong bóng (nền trắng)
    bottom = pixel(clip, 0.5, 540, 1700)  # ảnh gốc (xanh lá)
    assert min(top) > 200, top
    assert bottom[1] > 100 and bottom[0] < 100, bottom


def test_render_skips_missing_frames(project, cfg, tmp_path):
    make(project, cfg, tmp_path, "slideshow", n=2)
    st = project.load_state(); st.scenes["s01"].frames["f02"].picked = None; project.save_state(st)
    rep = run_render(project, cfg, now=lambda: "T")
    assert rep["created"] == [] and "f02" in rep["skipped"]["s01"]


def test_status_render_take_and_rerender_noop(project, cfg, tmp_path):
    make(project, cfg, tmp_path, "slideshow", n=2)
    run_render(project, cfg, now=lambda: "T")
    row = scene_rows(project, project.load_script(), project.load_state(), cfg)[0]
    assert row["clip"] == "ok"
    assert run_render(project, cfg, now=lambda: "T")["created"] == []  # không đổi gì → không render lại
    import_frame(project, cfg, "s01", "f01", png(tmp_path / "new.png", "purple"), now=lambda: "T")
    row = scene_rows(project, project.load_script(), project.load_state(), cfg)[0]
    assert row["clip"] == "cũ"


def test_capcut_assembled_scenes_not_rendered(project, cfg, tmp_path):
    make(project, cfg, tmp_path, "slideshow", n=1, extra="    assemble: capcut\n")
    rep = run_render(project, cfg, now=lambda: "T")
    assert rep["created"] == [] and "CapCut" in rep["skipped"]["s01"]
    assert render_hash(project, project.load_script(), project.load_state(), project.load_script().scenes[0]) is not None
