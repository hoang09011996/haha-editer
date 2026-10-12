import json

import pytest
from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.errors import VidflowError
from vidflow.quick import clips, ops
from vidflow.quick.model import FlowSettings, load_beats, load_quick

runner = CliRunner()
CP = "doodle motion of @MODERNYOU stretching. Sound: a yawn."


def test_defaults_and_old_files_load(tmp_path):
    (tmp_path / "quick.yaml").write_text("preset: x\nflow: {image_model: A, video_model: '', resolution: 720p}\n",
                                         encoding="utf-8")
    q = load_quick(tmp_path)
    assert q.flow.image_provider == "flow" and q.flow.video_provider == "flow"
    assert q.limits == []
    assert FlowSettings().image_provider == "flow"


def test_settings_providers(qroot):
    q = ops.update_settings(qroot, image_provider="gemini", video_provider="aistudio")
    assert q.flow.image_provider == "gemini" and q.flow.video_provider == "aistudio"
    with pytest.raises(VidflowError, match="gemeni"):
        ops.update_settings(qroot, image_provider="gemeni")
    s = ops.status_summary(qroot)
    assert s["providers"] == {"image": "gemini", "video": "aistudio"}


def test_set_image_and_clip_record_provider(qroot, P, img):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("a"), "verdict": "pass", "score": 8}])
    b = ops.set_image(qroot, 1, img(), provider="gemini")
    assert b.provider == "gemini"
    b = ops.set_image(qroot, 2, img("b.png"))
    assert b.provider == ""  # không khai → để trống
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP, "verdict": "pass", "score": 8}])
    b = clips.set_clip(qroot, 1, img("v.mp4", b"x"), provider="aistudio")
    assert b.clip.provider == "aistudio"
    with pytest.raises(VidflowError):
        ops.set_image(qroot, 3, img("c.png"), provider="midjourney")


def test_record_and_clear_limits(qroot):
    ops.record_limit(qroot, "flow", "image", reason="hết tín dụng")
    ops.record_limit(qroot, "gemini", "video")
    s = ops.status_summary(qroot)
    assert [(x["provider"], x["kind"]) for x in s["limits"]] == [("flow", "image"), ("gemini", "video")]
    assert s["limits"][0]["reason"] == "hết tín dụng" and s["limits"][0]["at"]
    assert "Hết lượt" in ops.format_status(s)
    assert ops.clear_limits(qroot, "gemini") == 1
    assert [x.provider for x in load_quick(qroot).limits] == ["flow"]
    with pytest.raises(VidflowError):
        ops.record_limit(qroot, "flow", "audio")


def test_cli_provider_commands(qroot, P, img):
    r = runner.invoke(app, ["quick", "settings", "-p", str(qroot), "--image-provider", "aistudio"])
    assert r.exit_code == 0 and "aistudio" in r.output
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("a"), "verdict": "pass", "score": 8}])
    r = runner.invoke(app, ["quick", "set-image", "-p", str(qroot), "1", str(img()), "--provider", "aistudio"])
    assert r.exit_code == 0, r.output
    assert load_beats(qroot).beats[0].provider == "aistudio"
    r = runner.invoke(app, ["quick", "limit", "-p", str(qroot), "--provider", "aistudio", "--kind", "image",
                            "--reason", "cần trả phí"])
    assert r.exit_code == 0, r.output
    s = json.loads(runner.invoke(app, ["quick", "status", "-p", str(qroot), "--json"]).output)
    assert s["limits"][0]["reason"] == "cần trả phí"
    r = runner.invoke(app, ["quick", "limit", "-p", str(qroot), "--provider", "x", "--kind", "image"])
    assert r.exit_code == 1 and "Traceback" not in r.output


import vidflow.quick.jobs as jobs_mod


def _ready_for_flow(qroot, P):
    ops.set_prompts(qroot, [{"n": i, "prompt": P("x"), "verdict": "pass", "score": 8} for i in range(1, 5)])


def test_job_uses_settings_provider_and_override(qroot, P, monkeypatch):
    _ready_for_flow(qroot, P)
    calls = []
    monkeypatch.setattr(jobs_mod, "run_claude", lambda kind, root, preset, **kw: calls.append((kind, kw.get("provider"))) or 0)
    ops.update_settings(qroot, image_provider="gemini")
    assert runner.invoke(app, ["quick", "flow", "-p", str(qroot)]).exit_code == 0
    assert runner.invoke(app, ["quick", "sheets", "-p", str(qroot), "--provider", "aistudio"]).exit_code == 0
    assert calls == [("flow", "gemini"), ("sheets", "aistudio")]
    r = runner.invoke(app, ["quick", "flow", "-p", str(qroot), "--provider", "gemeni"])
    assert r.exit_code == 1 and len(calls) == 2


def test_job_exits_3_when_agent_records_limit(qroot, P, monkeypatch):
    _ready_for_flow(qroot, P)
    ops.record_limit(qroot, "flow", "image")  # cũ, cùng nguồn + loại — bị xóa khi bắt đầu job
    ops.record_limit(qroot, "flow", "video")  # cùng nguồn, khác loại — giữ nguyên
    ops.record_limit(qroot, "gemini", "image")  # nguồn khác — giữ nguyên

    def fake_run(kind, root, preset, **kw):
        ops.record_limit(root, kw["provider"], "image", reason="đã dùng hết")
        return 0

    monkeypatch.setattr(jobs_mod, "run_claude", fake_run)
    r = runner.invoke(app, ["quick", "flow", "-p", str(qroot)])
    assert r.exit_code == 3
    assert "Hết lượt" in r.output and "ở flow" in r.output
    hits = [(x.provider, x.kind) for x in load_quick(qroot).limits]
    assert hits == [("flow", "video"), ("gemini", "image"), ("flow", "image")]


def test_print_does_not_clear_limits_or_run(qroot, P, monkeypatch):
    _ready_for_flow(qroot, P)
    ops.record_limit(qroot, "flow", "image")
    monkeypatch.setattr(jobs_mod, "run_claude", lambda *a, **kw: pytest.fail("không được chạy"))
    r = runner.invoke(app, ["quick", "flow", "-p", str(qroot), "--print", "--provider", "gemini"])
    assert r.exit_code == 0 and "Gemini" in r.output
    assert len(load_quick(qroot).limits) == 1


def test_image_job_ignores_video_limit_of_same_provider(qroot, P, monkeypatch):
    _ready_for_flow(qroot, P)

    def fake_run(kind, root, preset, **kw):
        ops.record_limit(root, kw["provider"], "video", reason="hết lượt clip")
        return 0

    monkeypatch.setattr(jobs_mod, "run_claude", fake_run)
    r = runner.invoke(app, ["quick", "flow", "-p", str(qroot)])
    assert r.exit_code == 0, r.output


def test_clear_limits_kind_filter(qroot):
    ops.record_limit(qroot, "flow", "image")
    ops.record_limit(qroot, "flow", "video")
    assert ops.clear_limits(qroot, "flow", kind="video") == 1
    assert [(x.provider, x.kind) for x in load_quick(qroot).limits] == [("flow", "image")]
    with pytest.raises(VidflowError):
        ops.clear_limits(qroot, "gemeni")


def test_begin_gen_clears_only_same_provider_and_kind(qroot):
    ops.update_settings(qroot, video_provider="gemini")
    for prov, kind in (("gemini", "video"), ("gemini", "image"), ("flow", "video")):
        ops.record_limit(qroot, prov, kind)
    assert jobs_mod.begin_gen(qroot, "clips") == "gemini"
    assert [(x.provider, x.kind) for x in load_quick(qroot).limits] == [("gemini", "image"), ("flow", "video")]
    assert jobs_mod.limit_hit(qroot, "gemini", "clips") is None
    assert jobs_mod.limit_hit(qroot, "gemini", "flow").kind == "image"
    assert jobs_mod.begin_gen(qroot, "sheets", "flow") == "flow"
    with pytest.raises(VidflowError):
        jobs_mod.begin_gen(qroot, "flow", "gemeni")


def test_claude_cmd_provider_none_uses_settings(qroot, quick_presets):
    from vidflow.quick.preset import load_preset
    ops.update_settings(qroot, image_provider="aistudio")
    pr = load_preset("doodle-giai-ma")
    assert "AI Studio" in jobs_mod.claude_cmd("flow", qroot, pr)[-1]
    assert "Google Flow" in jobs_mod.claude_cmd("clips", qroot, pr)[-1]
    assert "Google Flow" in jobs_mod.claude_cmd("flow", qroot / "missing", pr)[-1]
