import json

import pytest
from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.errors import VidflowError
from vidflow.quick import clips, ops
from vidflow.quick.model import load_beats, load_quick

runner = CliRunner()
CP = "doodle motion of @MODERNYOU stretching. Sound: a yawn."


def _ready(qroot, P, img, n=1):
    ops.set_prompts(qroot, [{"n": n, "prompt": P("a"), "verdict": "pass", "score": 8}])
    ops.set_image(qroot, n, img())


def test_settings(qroot):
    q = ops.update_settings(qroot, video_model="Veo 3.1 Lite", resolution="1080p", max_clips=3, allow_cont=False)
    assert q.flow.video_model == "Veo 3.1 Lite" and q.flow.resolution == "1080p"
    assert q.max_clips == 3 and q.allow_cont is False
    with pytest.raises(VidflowError):
        ops.update_settings(qroot, resolution="4k")
    with pytest.raises(VidflowError, match="@NOBODY"):
        ops.update_settings(qroot, channel_chars=["NOBODY"])


def test_max_clips_enforced_and_cannot_drop_below_enabled(qroot):
    ops.update_settings(qroot, max_clips=2)
    clips.set_clip_enabled(qroot, [1, 2], True)
    with pytest.raises(VidflowError, match="Tối đa 2"):
        clips.set_clip_enabled(qroot, [3], True)
    clips.set_clip_enabled(qroot, [1], True)  # đã bật thì không tính thêm
    with pytest.raises(VidflowError, match="Đang bật 2"):
        ops.update_settings(qroot, max_clips=1)
    clips.set_clip_enabled(qroot, [2], False)
    assert [b.clip.enabled for b in load_beats(qroot).beats] == [True, False, False, False]


def test_set_clip_prompts_enables_and_validates(qroot):
    ops.update_settings(qroot, max_clips=1)
    clips.set_clip_prompts(qroot, [{"n": 2, "prompt": CP, "verdict": "pass", "score": 8}])
    c = load_beats(qroot).beats[1].clip
    assert c.enabled and c.prompt == CP and c.review.verdict == "pass"
    with pytest.raises(VidflowError, match="Tối đa 1"):
        clips.set_clip_prompts(qroot, [{"n": 3, "prompt": CP, "verdict": "pass", "score": 8}])
    with pytest.raises(VidflowError, match="@GHOST"):
        clips.set_clip_prompts(qroot, [{"n": 2, "prompt": "@GHOST moves", "verdict": "pass", "score": 8}])


def test_clip_todo_requires_image_review_and_model(qroot, P, img):
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP, "verdict": "pass", "score": 8},
                                   {"n": 2, "prompt": CP, "verdict": "fail", "score": 4}])
    assert clips.clip_todo(qroot)["clips"] == []  # mốc 1 chưa có ảnh, mốc 2 trượt
    _ready(qroot, P, img, 1)
    with pytest.raises(VidflowError, match="model clip"):
        clips.clip_todo(qroot)
    ops.update_settings(qroot, video_model="Veo 3.1 Lite")
    data = clips.clip_todo(qroot)
    assert data["video_model"] == "Veo 3.1 Lite" and data["resolution"] == "720p"
    row = data["clips"][0]
    assert row["n"] == 1 and row["duration"] == 4.0 and row["file"] == "clips/001_00-00.mp4"
    assert row["image"] == str((qroot / "images" / "001_00-00.png").resolve())


def test_set_clip_and_image_regen_marks_clip_redo(qroot, P, img):
    _ready(qroot, P, img, 1)
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP, "verdict": "pass", "score": 8}])
    b = clips.set_clip(qroot, 1, img("v.MP4", b"mp4"))
    assert b.clip.file == "clips/001_00-00.mp4" and b.clip.status == "ok"
    assert (qroot / "clips" / "001_00-00.mp4").read_bytes() == b"mp4"
    ops.set_image(qroot, 1, img("new.png"))
    assert load_beats(qroot).beats[0].clip.status == "redo"
    with pytest.raises(VidflowError, match="chưa bật clip"):
        clips.set_clip(qroot, 2, img("v.mp4", b"x"))
    with pytest.raises(VidflowError, match="không hỗ trợ"):
        clips.set_clip(qroot, 1, img("v.avi", b"x"))


def test_errored_clip_leaves_todo_until_retry(qroot, P, img):
    ops.update_settings(qroot, video_model="Veo 3.1 Lite")
    _ready(qroot, P, img, 1)
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP, "verdict": "pass", "score": 8}])
    ops.record_fail(qroot, 1, "Veo từ chối", clip=True)
    assert clips.clip_todo(qroot)["clips"] == []
    ops.clear_errors(qroot, [1], clip=True)
    assert [c["n"] for c in clips.clip_todo(qroot)["clips"]] == [1]


def test_cli_clip_commands(qroot, P, img, tmp_path):
    r = runner.invoke(app, ["quick", "settings", "-p", str(qroot), "--video-model", "Veo 3.1 Lite", "--max-clips", "5"])
    assert r.exit_code == 0, r.output
    assert load_quick(qroot).max_clips == 5
    r = runner.invoke(app, ["quick", "clip", "-p", str(qroot), "on", "2", "3"])
    assert r.exit_code == 0, r.output
    f = tmp_path / "cp.json"
    f.write_text(json.dumps([{"n": 1, "prompt": CP, "verdict": "pass", "score": 8}]), encoding="utf-8")
    assert runner.invoke(app, ["quick", "set-clip-prompts", "-p", str(qroot), "--json", str(f)]).exit_code == 0
    _ready(qroot, P, img, 1)
    r = runner.invoke(app, ["quick", "beats", "-p", str(qroot), "--json", "--todo-clips"])
    assert json.loads(r.output)["clips"][0]["n"] == 1
    r = runner.invoke(app, ["quick", "set-clip", "-p", str(qroot), "1", str(img("v.mp4", b"x"))])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quick", "clip", "-p", str(qroot), "maybe", "1"])
    assert r.exit_code == 1 and "Traceback" not in r.output


def test_status_exposes_allow_cont(qroot):
    assert ops.status_summary(qroot)["allow_cont"] is True
    ops.update_settings(qroot, allow_cont=False)
    assert ops.status_summary(qroot)["allow_cont"] is False


def test_set_prompts_clears_error_when_prompt_changes(qroot, P):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("a"), "verdict": "pass", "score": 8}])
    ops.record_fail(qroot, 1, "blocked")
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("a"), "verdict": "pass", "score": 8}])
    assert load_beats(qroot).get(1).error == "blocked"
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("b"), "verdict": "pass", "score": 8}])
    assert load_beats(qroot).get(1).error == ""


def test_set_clip_prompts_error_to_redo_when_prompt_changes(qroot):
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP, "verdict": "pass", "score": 8}])
    ops.record_fail(qroot, 1, "blocked", clip=True)
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP, "verdict": "pass", "score": 8}])
    c = load_beats(qroot).get(1).clip
    assert c.status == "error" and c.error == "blocked"
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP + " Slower.", "verdict": "pass", "score": 8}])
    c = load_beats(qroot).get(1).clip
    assert c.status == "redo" and c.error == ""
