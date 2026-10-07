import shutil
import subprocess

import pytest

from vidflow.errors import ScriptError, VidflowError
from vidflow.frames import import_frame, pending_frames, pick_frame, set_review
from vidflow.manual import pending_prompts

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")

SCRIPT = """\
title: "Thử ảnh"
aspect: "9:16"
style: "hoạt hình 3D"
characters:
  - {id: tuan, description: "nam 30 tuổi"}
scenes:
  - id: s01
    mode: slideshow
    status: approved
    characters: [tuan]
    frames:
      - {id: f01, prompt: "Tuấn ngáp", status: approved}
      - {id: f02, prompt: "Tuấn dụi mắt", status: approved}
      - {id: f03, prompt: "chưa duyệt"}
  - id: s02
    status: approved
    veo_prompt: "Tuấn uống cà phê"
"""


def png(path, color="red", size="400x300"):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s={size}",
                    "-frames:v", "1", str(path)], check=True)
    return path


@pytest.fixture
def proj(project):
    project.script_path.write_text(SCRIPT, encoding="utf-8")
    return project


def test_unreviewed_frames_are_blocked(proj, cfg):
    items, blocked = pending_frames(proj, cfg)
    assert items == []
    assert {(b["scene"], b["frame"]) for b in blocked} == {("s01", "f01"), ("s01", "f02")}
    assert all("chưa kiểm duyệt" in b["reason"] for b in blocked)


def test_reviewed_frames_listed(proj, cfg):
    set_review(proj, "s01", "f01", verdict="pass", score=8, issues=[], suggestion="")
    set_review(proj, "s01", "f02", verdict="fail", score=4, issues=["thiếu ánh sáng"], suggestion="thêm nắng sớm")
    items, blocked = pending_frames(proj, cfg)
    assert [(i["scene"], i["frame"]) for i in items] == [("s01", "f01")]
    assert "Tuấn ngáp" in items[0]["prompt"] and items[0]["aspect"] == "9:16"
    assert any(b["frame"] == "f02" and "trượt" in b["reason"] for b in blocked)


def test_review_stale_after_prompt_edit(proj, cfg):
    set_review(proj, "s01", "f01", verdict="pass", score=9, issues=[], suggestion="")
    text = proj.script_path.read_text(encoding="utf-8").replace("Tuấn ngáp", "Tuấn ngáp to")
    proj.script_path.write_text(text, encoding="utf-8")
    items, blocked = pending_frames(proj, cfg)
    assert items == [] or all(i["frame"] != "f01" for i in items)
    assert any(b["frame"] == "f01" and "cũ" in b["reason"] for b in blocked)


def test_import_and_pick(proj, cfg, tmp_path):
    set_review(proj, "s01", "f01", verdict="pass", score=8, issues=[], suggestion="")
    a, b = png(tmp_path / "a.png"), png(tmp_path / "b.jpg", "blue")
    assert import_frame(proj, cfg, "s01", "f01", a, now=lambda: "T") == "frames/s01/f01_1.png"
    assert import_frame(proj, cfg, "s01", "f01", b, now=lambda: "T") == "frames/s01/f01_2.jpg"
    st = proj.load_state().scenes["s01"].frames["f01"]
    assert st.picked == 1 and len(st.images) == 2
    assert pick_frame(proj, "s01", "f01", 1) == "frames/s01/f01_1.png"
    items, _ = pending_frames(proj, cfg)
    assert all(i["frame"] != "f01" for i in items)  # đã có ảnh khớp prompt


def test_import_rejects(proj, cfg, tmp_path):
    with pytest.raises(ScriptError):
        import_frame(proj, cfg, "s01", "f99", png(tmp_path / "a.png"))
    bad = tmp_path / "x.png"; bad.write_text("không phải ảnh")
    with pytest.raises(VidflowError, match="ảnh"):
        import_frame(proj, cfg, "s01", "f01", bad)
    with pytest.raises(ScriptError, match="1..0"):
        pick_frame(proj, "s01", "f01", 1)


def test_veo_prompts_need_review(proj, cfg):
    items = pending_prompts(proj, cfg)
    assert items == []
    set_review(proj, "s02", None, verdict="pass", score=8, issues=[], suggestion="")
    assert [i["id"] for i in pending_prompts(proj, cfg)] == ["s02"]


def test_override(proj, cfg):
    set_review(proj, "s01", "f02", verdict="override", score=0, issues=[], suggestion="")
    items, _ = pending_frames(proj, cfg)
    assert [i["frame"] for i in items] == ["f02"]
