import shutil

import pytest

from conftest import make_mp4
from vidflow.errors import ScriptError, VidflowError
from vidflow.inputs import video_hash
from vidflow.frames import set_review
from vidflow.manual import import_clip, import_inbox, pending_prompts, write_prompts_md
from vidflow.state import Take

def reviewed(project):
    """Đánh dấu prompt các cảnh veo đã qua kiểm duyệt (prompt chỉ được gen khi kiểm duyệt đạt)."""
    for sid in ("s01", "s02"):
        set_review(project, sid, None, verdict="pass", score=8, issues=[], suggestion="")
    return project


pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")


def test_pending_prompts_only_approved_without_current_clip(project, cfg):
    (project.refs_dir / "an.png").write_bytes(b"img")
    reviewed(project)
    items = pending_prompts(project, cfg)
    assert [i["id"] for i in items] == ["s01", "s02"]
    s01 = items[0]
    assert s01["aspect"] == "9:16" and s01["duration"] == 8
    assert s01["prompt"].startswith("Phong cách: cinematic, warm tone.")
    assert s01["ref_images"] == [str(project.refs_dir / "an.png")]
    script = project.load_script()
    state = project.load_state()
    state.scene("s01").takes.append(Take(file="clips/x.mp4", input_hash=video_hash(project, script, script.scene("s01"), cfg),
                                         cost_usd=0, created_at="t"))
    project.save_state(state)
    assert [i["id"] for i in pending_prompts(project, cfg)] == ["s02"]


def test_write_prompts_md(project, cfg):
    reviewed(project)
    out = write_prompts_md(project, pending_prompts(project, cfg))
    text = out.read_text(encoding="utf-8")
    assert out == project.root / "prompts.md"
    assert "## s01 · 9:16 · 8s" in text and "Close-up of a young woman" in text


def test_import_clip_registers_take_and_picks(project, cfg, tmp_path):
    src = make_mp4(tmp_path / "dl" / "flow_video.mp4", 2)
    rel = import_clip(project, cfg, "s01", src, now=lambda: "T")
    assert rel == "clips/s01_t1.mp4"
    assert (project.root / rel).is_file() and src.is_file()
    st = project.load_state().scenes["s01"]
    assert st.picked == 0
    take = st.takes[0]
    assert take.source == "flow" and take.cost_usd == 0
    script = project.load_script()
    assert take.input_hash == video_hash(project, script, script.scene("s01"), cfg)
    assert import_clip(project, cfg, "s01", src, now=lambda: "T") == "clips/s01_t2.mp4"
    assert project.load_state().scenes["s01"].picked == 1
    assert project.load_state().spent_usd == 0


def test_import_rejects_unknown_scene_missing_and_non_video(project, cfg, tmp_path):
    with pytest.raises(ScriptError, match="s99"):
        import_clip(project, cfg, "s99", make_mp4(tmp_path / "a.mp4", 1))
    with pytest.raises(VidflowError, match="Không thấy"):
        import_clip(project, cfg, "s01", tmp_path / "none.mp4")
    bad = tmp_path / "bad.mp4"
    bad.write_text("not a video")
    with pytest.raises(VidflowError, match="Không đọc được"):
        import_clip(project, cfg, "s01", bad)
    assert project.load_state().scenes.get("s01") is None or not project.load_state().scenes["s01"].takes


def test_import_inbox_matches_prefix_and_moves_done(project, cfg):
    inbox = project.root / "inbox"
    make_mp4(inbox / "s01.mp4", 1)
    make_mp4(inbox / "s02_take_b.mp4", 1)
    make_mp4(inbox / "random.mp4", 1)
    imported, unmatched = import_inbox(project, cfg, now=lambda: "T")
    assert imported == {"s01.mp4": "clips/s01_t1.mp4", "s02_take_b.mp4": "clips/s02_t1.mp4"}
    assert unmatched == ["random.mp4"]
    assert (inbox / "imported" / "s01.mp4").is_file() and not (inbox / "s01.mp4").exists()
    assert (inbox / "random.mp4").is_file()


def test_import_inbox_prefers_longest_scene_id(project, cfg):
    text = project.script_path.read_text(encoding="utf-8").replace("  - id: s03", "  - id: s01b")
    project.script_path.write_text(text, encoding="utf-8")
    make_mp4(project.root / "inbox" / "s01b_x.mp4", 1)
    imported, _ = import_inbox(project, cfg, now=lambda: "T")
    assert imported == {"s01b_x.mp4": "clips/s01b_t1.mp4"}


def test_prompts_md_shows_vietnamese_translation(project, cfg):
    text = project.script_path.read_text(encoding="utf-8").replace(
        '    veo_prompt: "Close-up of a young woman sipping coffee."',
        '    veo_prompt: "Close-up of a young woman sipping coffee."\n    veo_prompt_vi: "Cận cảnh cô gái nhấp cà phê."')
    project.script_path.write_text(text, encoding="utf-8")
    items = pending_prompts(reviewed(project), cfg)
    assert items[0]["prompt_vi"] == "Cận cảnh cô gái nhấp cà phê."
    assert "Cận cảnh cô gái" not in items[0]["prompt"]
    md = write_prompts_md(project, items).read_text(encoding="utf-8")
    assert "- Bản dịch (chỉ để đọc, không dán vào Flow): Cận cảnh cô gái nhấp cà phê." in md


def test_prompts_include_flow_settings(project, cfg):
    items = pending_prompts(reviewed(project), cfg)
    assert items[0]["flow_resolution"] == "720p" and items[0]["flow_video_model"] == ""
    script = project.load_script()
    script.flow.video_model, script.flow.resolution = "Veo 3.1 Fast", "1080p"
    project.save_script(script)
    items = pending_prompts(reviewed(project), cfg)
    assert items[0]["flow_video_model"] == "Veo 3.1 Fast" and items[0]["flow_resolution"] == "1080p"
