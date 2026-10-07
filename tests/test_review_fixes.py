import shutil
import subprocess

import pytest

from conftest import write_wav
from vidflow.frames import import_frame, set_review
from vidflow.project import create_project
from vidflow.render import planned_durations, run_render
from vidflow.state import TtsResult
from vidflow.status import scene_rows
from vidflow.timeline import plan_timeline

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")


def png(path, color="red"):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s=200x300",
                    "-frames:v", "1", str(path)], check=True)
    return path


def setup(project, cfg, tmp_path, mode="slideshow", n=2, secs=1.0, assemble="ffmpeg"):
    frames = "\n".join(f"      - {{id: f{i:02d}, prompt: \"p{i}\", status: approved, seconds: {secs}}}" for i in range(1, n + 1))
    project.script_path.write_text(f"title: T\nprompt_language: vi\nscenes:\n  - id: s01\n    mode: {mode}\n    assemble: {assemble}\n"
                                   f"    status: approved\n    frames:\n{frames}\n", encoding="utf-8")
    for i in range(1, n + 1):
        import_frame(project, cfg, "s01", f"f{i:02d}", png(tmp_path / f"i{i}.png"), now=lambda: "T")


def test_deleted_frame_image_does_not_crash_status(project, cfg, tmp_path):
    setup(project, cfg, tmp_path)
    run_render(project, cfg, now=lambda: "T")
    (project.root / "frames/s01/f01_1.png").unlink()
    row = scene_rows(project, project.load_script(), project.load_state(), cfg)[0]
    assert row["clip"] in ("thiếu ảnh", "cũ")
    assert "f01" in run_render(project, cfg, now=lambda: "T")["skipped"]["s01"]


def test_legacy_script_without_language_is_english(tmp_path):
    p = create_project(tmp_path / "old", title="Old", aspect="9:16")
    assert p.load_script().prompt_language == "vi"  # project mới: tiếng Việt
    p.script_path.write_text("title: Cũ\nscenes: []\n", encoding="utf-8")
    assert p.load_script().prompt_language == "en"  # script cũ không có khóa: giữ tiếng Anh


def test_stopmotion_without_voice_uses_frame_seconds(project, cfg, tmp_path):
    setup(project, cfg, tmp_path, mode="stopmotion", n=3, secs=1.0)
    script, state = project.load_script(), project.load_state()
    assert sum(planned_durations(script, state, script.scenes[0])) == pytest.approx(3.0)
    setup(project, cfg, tmp_path, mode="stopmotion", n=3, secs=1.0, assemble="capcut")
    script, state = project.load_script(), project.load_state()
    tl = plan_timeline(script, state, {})
    assert tl.scenes[0].end - tl.scenes[0].start == pytest.approx(3.0, abs=1e-3)


def test_status_flags_frame_older_than_prompt(project, cfg, tmp_path):
    setup(project, cfg, tmp_path)
    run_render(project, cfg, now=lambda: "T")
    script = project.load_script()
    script.scenes[0].frames[0].prompt = "prompt mới"
    project.save_script(script)
    row = scene_rows(project, project.load_script(), project.load_state(), cfg)[0]
    assert row["clip"] == "khung cũ"
