import pytest
from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.errors import VidflowError
from vidflow.quick import chars, ops
from vidflow.quick.model import load_beats

runner = CliRunner()


def test_set_prompts_extracts_refs_and_rejects_unknown(qroot, P):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("@MODERNYOU wakes up"), "verdict": "pass", "score": 8}])
    assert load_beats(qroot).beats[0].refs == ["MODERNYOU"]
    with pytest.raises(VidflowError, match="@GHOST"):
        ops.set_prompts(qroot, [{"n": 2, "prompt": P("@GHOST"), "verdict": "pass", "score": 8}])


def test_set_prompts_batch_is_atomic(qroot, P):
    with pytest.raises(VidflowError):
        ops.set_prompts(qroot, [{"n": 1, "prompt": P("ok"), "verdict": "pass", "score": 8},
                                {"n": 2, "prompt": P("@GHOST"), "verdict": "pass", "score": 8}])
    assert load_beats(qroot).beats[0].prompt == ""


def test_cont_rules(qroot, P):
    ops.set_prompts(qroot, [{"n": 2, "prompt": P("x"), "verdict": "pass", "score": 8, "cont": True}])
    assert load_beats(qroot).beats[1].cont is True
    ops.set_prompts(qroot, [{"n": 2, "prompt": P("y"), "verdict": "pass", "score": 8}])
    assert load_beats(qroot).beats[1].cont is True  # không gửi cont → giữ nguyên
    with pytest.raises(VidflowError, match="Mốc 1"):
        ops.set_prompts(qroot, [{"n": 1, "prompt": P("x"), "verdict": "pass", "score": 8, "cont": True}])
    ops.update_settings(qroot, allow_cont=False)
    with pytest.raises(VidflowError, match="nối cảnh"):
        ops.set_prompts(qroot, [{"n": 3, "prompt": P("x"), "verdict": "pass", "score": 8, "cont": True}])


def test_edit_prompt_clears_review_then_set_review(qroot, P):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("a"), "verdict": "pass", "score": 8}])
    b = ops.edit_prompt(qroot, 1, P("@MODERNYOU b"))
    assert b.review is None and b.refs == ["MODERNYOU"]
    with pytest.raises(VidflowError, match="câu neo"):
        ops.edit_prompt(qroot, 1, "no anchors")
    b = ops.set_review(qroot, 1, "fail", score=5, issues=["mơ hồ"])
    assert b.review.verdict == "fail" and b.review.issues == ["mơ hồ"]
    b = ops.set_review(qroot, 1, "override")
    assert b.review.verdict == "override"
    with pytest.raises(VidflowError):
        ops.set_review(qroot, 1, "maybe")
    with pytest.raises(VidflowError, match="chưa có prompt"):
        ops.set_review(qroot, 2, "pass")


def test_edit_and_review_clip_prompt(qroot):
    b = ops.edit_prompt(qroot, 1, "doodle motion of @MODERNYOU stretching. Sound: a yawn.", clip=True)
    assert b.clip.prompt.startswith("doodle motion") and b.clip.review is None
    b = ops.set_review(qroot, 1, "pass", score=8, clip=True)
    assert b.clip.review.verdict == "pass" and b.review is None


def test_fail_retry_and_set_image_clears_error(qroot, img):
    ops.record_fail(qroot, 2, "Flow: vi phạm chính sách")
    assert load_beats(qroot).beats[1].error == "Flow: vi phạm chính sách"
    with pytest.raises(VidflowError):
        ops.record_fail(qroot, 2, "  ")
    assert ops.clear_errors(qroot) == 1
    assert load_beats(qroot).beats[1].error == ""
    ops.record_fail(qroot, 3, "lỗi")
    ops.set_image(qroot, 3, img())
    assert load_beats(qroot).beats[2].error == ""


def test_clip_fail_and_retry(qroot):
    ops.record_fail(qroot, 1, "Veo lỗi", clip=True)
    c = load_beats(qroot).beats[0].clip
    assert c.status == "error" and c.error == "Veo lỗi"
    assert ops.clear_errors(qroot, [1], clip=True) == 1
    c = load_beats(qroot).beats[0].clip
    assert c.status == "redo" and c.error == ""


def test_cli_review_fail_retry(qroot, P):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("a"), "verdict": "fail", "score": 4}])
    r = runner.invoke(app, ["quick", "set-review", "-p", str(qroot), "1", "--verdict", "pass", "--score", "8"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quick", "fail", "-p", str(qroot), "2", "--reason", "từ chối"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quick", "retry", "-p", str(qroot)])
    assert r.exit_code == 0 and "1" in r.output
    r = runner.invoke(app, ["quick", "set-prompt", "-p", str(qroot), "2", "--prompt", P("b"), "--cont"])
    assert r.exit_code == 0, r.output
    assert load_beats(qroot).beats[1].cont is True
