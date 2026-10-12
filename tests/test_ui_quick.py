"""API quy trình nhanh trên UI (spec 2026-10-12, Giai đoạn 3)."""
import sys
import time
import wave
from array import array
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vidflow.quick import chars, ops
from vidflow.errors import VidflowError
from vidflow.quick.model import create_quick, load_beats, load_quick
from vidflow.quick.preset import load_preset
from vidflow.ui.jobs import JobLaunchError, JobRunner, ReviewRunner
from vidflow.ui.quick_api import beat_state, media_url
from vidflow.ui.server import create_app

FARMER = {"id": "FARMER", "name": "Nông dân", "desc": "hunched neolithic farmer", "color": "#8B5E3C"}


class QuickFakeRunner(JobRunner):
    """Thay lệnh thật (claude / vidflow quick) bằng lệnh python ngắn; ghi lại việc được gọi."""

    def __init__(self):
        super().__init__()
        self.cmd = [sys.executable, "-c", "print('ok')"]
        self.calls = []

    def quick_command_for(self, kind, project_root, instruction="", options=None, provider=None):
        self.calls.append((kind, instruction, dict(options or {}), provider))
        return self.cmd


def wait_idle(c):
    for _ in range(80):
        j = c.get("/api/jobs/current").json()
        if j.get("state") != "running":
            return j
        time.sleep(0.1)
    raise AssertionError("việc nền chưa xong")


class FakeReview(ReviewRunner):
    """Giả lập `claude -p` vai prompt-reviewer: chạy `action` (ghi kết quả qua ops) rồi trả (rc, out)."""

    def __init__(self):
        super().__init__()
        self.cmds, self.action, self.rc, self.out = [], None, 0, "Mốc 1: trượt 4/10"

    def run(self, cmd):
        self.cmds.append(cmd)
        if self.action:
            self.action()
        return self.rc, self.out


@pytest.fixture
def env(tmp_path, qroot, quick_presets):
    runner, reviews = QuickFakeRunner(), FakeReview()
    c = TestClient(create_app(projects_root=tmp_path, runner=runner, review_runner=reviews))
    yield SimpleNamespace(c=c, root=qroot, tmp=tmp_path, presets=quick_presets, runner=runner, reviews=reviews)
    runner.stop()


def test_list_presets_and_quick(env):
    assert env.c.get("/api/quick").json() == [
        {"name": "vid", "title": "T", "preset": "doodle-giai-ma", "stage": "script", "beats": 4}]
    p = env.c.get("/api/presets").json()
    assert [x["id"] for x in p] == ["doodle-giai-ma"] and p[0]["characters"][0]["id"] == "MODERNYOU"


def test_get_quick_payload(env):
    d = env.c.get("/api/quick/vid").json()
    assert d["name"] == "vid" and d["aspect"] == "16:9" and d["preset"]["id"] == "doodle-giai-ma"
    assert [b["n"] for b in d["beats"]] == [1, 2, 3, 4]
    assert {b["state"] for b in d["beats"]} == {"pending"}
    assert d["beats"][0]["image_url"] is None and d["beats"][0]["attach"] == []
    assert d["characters"] == [{"id": "MODERNYOU", "name": "Người hiện đại",
                                "desc": "round-headed modern person in a cobalt t-shirt", "color": "#3557D6",
                                "scope": "channel", "uses": 0, "blocked": 0, "image_url": None}]
    assert d["status"]["beats"]["total"] == 4 and d["renders"] == [] and d["voice_url"] is None
    assert d["job"] is None and d["quick"]["flow"]["resolution"] == "720p"


def test_get_quick_new_project_without_beats(env):
    create_quick(env.tmp / "moi", preset="doodle-giai-ma")
    r = env.c.get("/api/quick/moi")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["beats"] == [] and d["status"]["stage"] == "new" and d["aspect"] == "16:9"


def test_unknown_quick_404(env):
    assert env.c.get("/api/quick/nope").status_code == 404
    assert env.c.get("/api/quick/Bad!").status_code == 404


def test_beat_states_attach_and_media(env, P, img):
    c, root = env.c, env.root
    chars.set_chars(root, [FARMER])
    ops.set_prompts(root, [{"n": 1, "prompt": P("a cave"), "verdict": "pass", "score": 8},
                           {"n": 2, "prompt": P("@FARMER digging"), "verdict": "pass", "score": 8},
                           {"n": 3, "prompt": P("the same cave"), "verdict": "pass", "score": 8, "cont": True}])
    ops.set_image(root, 1, img())
    ops.record_fail(root, 4, "Flow từ chối")
    d = c.get("/api/quick/vid").json()
    assert {b["n"]: b["state"] for b in d["beats"]} == {1: "ok", 2: "blocked", 3: "pending", 4: "error"}
    b1, b2, b3 = d["beats"][:3]
    assert b1["image_url"].startswith("/media/vid/images/001_00-00.png?v=")
    assert c.get(b1["image_url"].split("?")[0]).status_code == 200
    assert b2["attach"] == [{"kind": "char", "id": "FARMER", "url": None}] and b2["blocked"] == "thiếu ảnh @FARMER"
    assert b3["attach"] == [{"kind": "prev", "n": 2, "url": None}]
    far = next(x for x in d["characters"] if x["id"] == "FARMER")
    assert far["scope"] == "video" and far["uses"] == 1 and far["blocked"] == 1 and far["image_url"] is None


def test_flow_running_marks_gen(env, P):
    ops.set_prompts(env.root, [{"n": 1, "prompt": P("a cave"), "verdict": "pass", "score": 8}])
    env.runner.cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    env.runner.start("flow", "vid", env.root, quick=True)
    d = env.c.get("/api/quick/vid").json()
    assert [b["state"] for b in d["beats"]] == ["gen", "pending", "pending", "pending"]
    assert d["job"]["label"] == "Gen ảnh mốc" and d["job"]["state"] == "running"


def test_media_quick_and_preset_refs(env):
    (env.root / "out" / "vid-v1.mp4").write_bytes(b"mp4")
    assert env.c.get("/media/vid/out/vid-v1.mp4").status_code == 200
    d = env.c.get("/api/quick/vid").json()
    assert d["renders"][0]["file"] == "out/vid-v1.mp4"
    assert d["renders"][0]["url"].startswith("/media/vid/out/vid-v1.mp4?v=")
    for bad in ("/media/vid/quick.yaml", "/media/vid/beats.json", "/media/vid/images/..%2Fquick.yaml",
                "/media/_presets/doodle-giai-ma/..%2F..%2Fdoodle-giai-ma.yaml", "/media/_presets/NOPE/X.png",
                "/media/_presets/doodle-giai-ma/MODERNYOU.png"):
        assert env.c.get(bad).status_code == 404, bad
    refs = env.presets / "refs" / "doodle-giai-ma"
    refs.mkdir(parents=True)
    (refs / "MODERNYOU.png").write_bytes(b"\x89PNGx")
    assert env.c.get("/media/_presets/doodle-giai-ma/MODERNYOU.png").status_code == 200
    me = next(x for x in env.c.get("/api/quick/vid").json()["characters"] if x["id"] == "MODERNYOU")
    assert me["image_url"].startswith("/media/_presets/doodle-giai-ma/MODERNYOU.png?v=")


def _row(**kw):
    base = dict(error="", status="pending", image=None, blocked=None, prompt="p", review={"verdict": "pass"}, start=0.0)
    return {**base, **kw}


@pytest.mark.parametrize("row,flow,want", [
    (_row(error="x", status="ok", image="i"), False, "error"),
    (_row(status="ok", image="i"), True, "ok"),
    (_row(blocked="thiếu ảnh @A"), True, "blocked"),
    (_row(blocked="chờ ảnh mốc 1"), True, "pending"),
    (_row(status="redo", image="i", review={"verdict": "override"}), True, "gen"),
    (_row(status="redo", image="i"), False, "redo"),
    (_row(review={"verdict": "fail"}), True, "pending"),
    (_row(start=None), True, "pending"),
])
def test_beat_state(row, flow, want):
    assert beat_state(row, flow) == want


def test_create_quick_project_and_ideas_job(env):
    r = env.c.post("/api/quick", json={"preset": "doodle-giai-ma", "topic": "tổ tiên 50.000 năm trước",
                                       "video_model": "Veo 3.1 Lite", "max_clips": 5, "allow_cont": False})
    assert r.status_code == 201, r.text
    name = r.json()["name"]
    assert name.startswith("doodle-giai-ma-")
    q = load_quick(env.tmp / name)
    assert q.title == "tổ tiên 50.000 năm trước" and q.flow.video_model == "Veo 3.1 Lite"
    assert q.max_clips == 5 and q.allow_cont is False and q.flow.resolution == "720p"
    kind, instruction, _, _ = env.runner.calls[0]
    assert kind == "ideas" and "tổ tiên 50.000 năm trước" in instruction
    assert r.json()["job"]["label"] == "Claude đề xuất 5 ý tưởng" and r.json()["warning"] is None
    assert name in [x["name"] for x in env.c.get("/api/quick").json()]
    wait_idle(env.c)


def test_create_while_busy_keeps_project_and_warns(env):
    env.runner.cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    assert env.c.post("/api/quick/vid/jobs", json={"kind": "voice"}).status_code == 202
    r = env.c.post("/api/quick", json={"preset": "doodle-giai-ma", "name": "busy1", "max_clips": 0})
    assert r.status_code == 201 and r.json()["job"] is None and "Đang chạy" in r.json()["warning"]
    assert load_quick(env.tmp / "busy1").preset == "doodle-giai-ma"
    assert env.c.post("/api/quick/vid/jobs/stop").status_code == 200  # dọn việc nền còn chạy


def test_create_existing_dir_is_conflict_and_untouched(env):
    (env.tmp / "keep1").mkdir()
    (env.tmp / "keep1" / "mine.txt").write_text("x")
    r = env.c.post("/api/quick", json={"preset": "doodle-giai-ma", "name": "keep1", "max_clips": 0, "start": False})
    assert r.status_code == 409
    assert (env.tmp / "keep1" / "mine.txt").read_text() == "x"


def test_create_concurrent_dir_is_conflict_and_untouched(env, monkeypatch):
    """Thư mục xuất hiện giữa bước kiểm tra và bước tạo (request khác) → 409, không xóa thư mục của request kia."""
    import vidflow.ui.quick_api as qa
    real = qa.default_name

    def racing(preset):
        name = real(preset)
        (env.tmp / name).mkdir()
        (env.tmp / name / "other.txt").write_text("y")
        return name
    monkeypatch.setattr(qa, "default_name", racing)
    r = env.c.post("/api/quick", json={"preset": "doodle-giai-ma", "max_clips": 0, "start": False})
    assert r.status_code == 409
    assert [d for d in env.tmp.iterdir() if (d / "other.txt").is_file()]


def test_create_cleans_up_on_os_error(env, monkeypatch):
    def boom(*a, **k):
        raise OSError("đĩa đầy")
    monkeypatch.setattr(ops, "update_settings", boom)
    c = TestClient(env.c.app, raise_server_exceptions=False)
    r = c.post("/api/quick", json={"preset": "doodle-giai-ma", "name": "os1", "max_clips": 0, "start": False})
    assert r.status_code == 500 and "đĩa đầy" in r.json()["detail"]
    assert not (env.tmp / "os1").exists()


def test_create_validation_leaves_nothing_behind(env):
    base = {"preset": "doodle-giai-ma", "start": False}
    r = env.c.post("/api/quick", json={**base, "max_clips": 3})
    assert r.status_code == 422 and "model clip" in r.json()["detail"]
    assert env.c.post("/api/quick", json={**base, "name": "x1", "max_clips": 0}).status_code == 201
    assert env.c.post("/api/quick", json={**base, "name": "x1", "max_clips": 0}).status_code == 409
    assert env.c.post("/api/quick", json={**base, "name": "Bad Name", "max_clips": 0}).status_code == 422
    assert env.c.post("/api/quick", json={**base, "preset": "nope", "name": "x2", "max_clips": 0}).status_code == 422
    assert env.c.post("/api/quick", json={**base, "preset": "../x", "name": "x4", "max_clips": 0}).status_code == 422
    r = env.c.post("/api/quick", json={**base, "name": "x3", "max_clips": 0, "channel_chars": ["GHOST"]})
    assert r.status_code == 422 and "GHOST" in r.json()["detail"]
    for gone in ("x2", "x3", "x4"):
        assert not (env.tmp / gone).exists()
    assert env.runner.calls == []


def test_settings_pick_clip_redo_retry(env, img):
    c, root = env.c, env.root
    assert c.post("/api/quick/vid/settings", json={"video_model": "Veo 3.1 Lite", "max_clips": 1}).status_code == 200
    q = load_quick(root)
    assert q.flow.video_model == "Veo 3.1 Lite" and q.max_clips == 1
    assert c.post("/api/quick/vid/settings", json={"resolution": "4k"}).status_code == 422
    ops.set_ideas(root, [{"title": "Ý A"}, {"title": "Ý B"}])
    r = c.post("/api/quick/vid/pick", json={"n": 2})
    assert r.status_code == 200 and r.json() == {"title": "Ý B"}
    assert c.post("/api/quick/vid/pick", json={"n": 9}).status_code == 422
    assert c.post("/api/quick/vid/clip", json={"ns": [1], "on": True}).status_code == 200
    r = c.post("/api/quick/vid/clip", json={"ns": [2], "on": True})
    assert r.status_code == 422 and "Tối đa 1 clip" in r.json()["detail"]
    ops.set_image(root, 1, img())
    assert c.post("/api/quick/vid/redo", json={"ns": [1]}).status_code == 200
    assert load_beats(root).get(1).status == "redo"
    assert c.post("/api/quick/vid/redo", json={"ns": [99]}).status_code == 422
    assert c.post("/api/quick/vid/redo", json={"ns": []}).status_code == 422
    ops.record_fail(root, 2, "bị chặn nội dung")
    r = c.post("/api/quick/vid/retry", json={})
    assert r.status_code == 200 and r.json() == {"count": 1}
    assert load_beats(root).get(2).error == ""


def test_prompt_edit_clears_review_and_validates(env, P):
    c, root = env.c, env.root
    ops.set_prompts(root, [{"n": 1, "prompt": P("a cave"), "verdict": "pass", "score": 9}])
    r = c.post("/api/quick/vid/prompt", json={"n": 1, "prompt": P("@MODERNYOU in a cave")})
    assert r.status_code == 200, r.text
    b = load_beats(root).get(1)
    assert b.review is None and b.refs == ["MODERNYOU"]
    assert c.post("/api/quick/vid/prompt", json={"n": 1, "prompt": "no anchors"}).status_code == 422
    r = c.post("/api/quick/vid/prompt", json={"n": 1, "prompt": P("@GHOST")})
    assert r.status_code == 422 and "@GHOST" in r.json()["detail"]
    r = c.post("/api/quick/vid/prompt", json={"n": 1, "prompt": "@MODERNYOU waves", "clip": True})
    assert r.status_code == 200 and load_beats(root).get(1).clip.prompt == "@MODERNYOU waves"


def test_override_marks_review(env, P):
    ops.set_prompts(env.root, [{"n": 1, "prompt": P("x"), "verdict": "fail", "score": 3}])
    assert env.c.post("/api/quick/vid/override", json={"n": 1}).status_code == 200
    assert load_beats(env.root).get(1).review.verdict == "override"
    assert env.c.post("/api/quick/vid/override", json={"n": 2}).status_code == 422  # chưa có prompt


def test_promote(env):
    chars.set_chars(env.root, [FARMER])
    assert env.c.post("/api/quick/vid/chars/FARMER/promote").status_code == 200
    assert "FARMER" in [x.id for x in load_preset("doodle-giai-ma").characters]
    assert env.c.post("/api/quick/vid/chars/FARMER/promote").status_code == 422
    assert env.c.post("/api/quick/vid/chars/bad/promote").status_code == 404


def test_jobs_validation_and_options(env):
    c = env.c
    r = c.post("/api/quick/vid/jobs", json={"kind": "gen"})
    assert r.status_code == 400 and "gen" in r.json()["detail"]
    r = c.post("/api/quick/vid/jobs", json={"kind": "script"})
    assert r.status_code == 400 and "ý tưởng" in r.json()["detail"]
    r = c.post("/api/quick/vid/jobs", json={"kind": "clips"})
    assert r.status_code == 400 and "model clip" in r.json()["detail"]
    for bad in ({"resolution": "4k"}, {"resolution": "1080p; rm -rf /"}, {"output": "/tmp/x.mp4"}):
        assert c.post("/api/quick/vid/jobs", json={"kind": "render", "options": bad}).status_code == 400, bad
    assert env.runner.calls == []
    r = c.post("/api/quick/vid/jobs", json={"kind": "render", "options": {"resolution": "720p", "zoom": False}})
    assert r.status_code == 202 and r.json()["label"] == "Xuất MP4 (Remotion)"
    assert env.runner.calls[-1] == ("render", "", {"resolution": "720p", "zoom": False}, None)
    wait_idle(c)
    assert c.post("/api/quick/nope/jobs", json={"kind": "voice"}).status_code == 404


@pytest.mark.parametrize("exc,code", [(ValueError("Nguồn gen sai"), 400), (VidflowError("quick.yaml hỏng"), 400),
                                      (RuntimeError("Đang chạy: X"), 409),
                                      (JobLaunchError("Không chạy được lệnh: claude (No such file)"), 503)])
def test_jobs_maps_runner_start_errors(env, monkeypatch, exc, code):
    def boom(*a, **kw):
        raise exc
    monkeypatch.setattr(env.runner, "start", boom)
    r = env.c.post("/api/quick/vid/jobs", json={"kind": "voice"})
    assert r.status_code == code and r.json()["detail"] == str(exc)


def test_providers_settings_create_and_job_override(env):
    c, root = env.c, env.root
    r = c.post("/api/quick/vid/settings", json={"image_provider": "gemini", "video_provider": "aistudio"})
    assert r.status_code == 200, r.text
    q = load_quick(root)
    assert (q.flow.image_provider, q.flow.video_provider) == ("gemini", "aistudio")
    assert c.post("/api/quick/vid/settings", json={"image_provider": "midjourney"}).status_code == 422
    r = c.post("/api/quick", json={"preset": "doodle-giai-ma", "name": "p1", "max_clips": 0, "start": False,
                                   "image_provider": "aistudio", "video_provider": "gemini"})
    assert r.status_code == 201, r.text
    q1 = load_quick(env.tmp / "p1")
    assert (q1.flow.image_provider, q1.flow.video_provider) == ("aistudio", "gemini")
    assert c.post("/api/quick", json={"preset": "doodle-giai-ma", "name": "p2", "max_clips": 0,
                                      "image_provider": "x"}).status_code == 422
    assert c.post("/api/quick/vid/jobs", json={"kind": "voice", "provider": "gemini"}).status_code == 400
    assert c.post("/api/quick/vid/jobs", json={"kind": "flow", "provider": "midjourney"}).status_code == 400
    r = c.post("/api/quick/vid/jobs", json={"kind": "flow"})
    assert r.status_code == 202 and r.json()["provider"] == "gemini"  # theo cài đặt ảnh
    assert env.runner.calls[-1][3] == "gemini"
    wait_idle(c)
    r = c.post("/api/quick/vid/jobs", json={"kind": "flow", "provider": "flow"})  # ghi đè một lần
    assert r.json()["provider"] == "flow" and env.runner.calls[-1][3] == "flow"
    wait_idle(c)
    assert load_quick(root).flow.image_provider == "gemini"  # ghi đè không đổi cài đặt
    j = c.get("/api/quick/vid").json()["job"]
    assert j["provider"] == "flow" and j["quota_exhausted"] is False


def test_quota_exhausted_job_reported(env):
    env.runner.cmd = [sys.executable, "-c", "import sys; print('hết lượt ở gemini'); sys.exit(3)"]
    assert env.c.post("/api/quick/vid/jobs", json={"kind": "flow", "provider": "gemini"}).status_code == 202
    j = wait_idle(env.c)
    assert j["quota_exhausted"] is True and j["provider"] == "gemini" and j["state"] == "failed"
    assert env.c.get("/api/quick/vid").json()["job"]["quota_exhausted"] is True


def test_stop_job(env):
    env.runner.cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    assert env.c.post("/api/quick/vid/jobs", json={"kind": "voice"}).status_code == 202
    r = env.c.post("/api/quick/vid/jobs", json={"kind": "voice"})
    assert r.status_code == 409 and "Đang chạy" in r.json()["detail"]
    assert env.c.post("/api/quick/x1/jobs/stop").status_code == 404
    r = env.c.post("/api/quick/vid/jobs/stop")
    assert r.status_code == 200 and r.json() == {"stopped": True}
    assert env.c.get("/api/jobs/current").json()["state"] == "stopped"
    assert env.c.post("/api/quick/vid/jobs/stop").status_code == 409


def test_broken_quick_yaml_listed_as_error(env):
    bad = env.tmp / "hong"
    create_quick(bad, preset="doodle-giai-ma")
    (bad / "quick.yaml").write_text("title: [unclosed\n", encoding="utf-8")
    with pytest.raises(VidflowError, match="không hợp lệ"):
        load_quick(bad)
    r = env.c.get("/api/quick")
    assert r.status_code == 200
    row = next(x for x in r.json() if x["name"] == "hong")
    assert "không hợp lệ" in row["error"]


def test_media_url_quotes_path(env):
    f = env.root / "images" / "a b#1.png"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"\x89PNGx")
    url = media_url(env.root, "vid", "images/a b#1.png")
    assert url.startswith("/media/vid/images/a%20b%231.png?v=")
    assert env.c.get(url.split("?")[0]).status_code == 200


WRITE_ROUTES = [("/api/quick", {"preset": "doodle-giai-ma"}), ("/api/quick/vid/settings", {}),
                ("/api/quick/vid/pick", {"n": 1}), ("/api/quick/vid/redo", {"ns": [1]}),
                ("/api/quick/vid/retry", {}), ("/api/quick/vid/clip", {"ns": [1], "on": True}),
                ("/api/quick/vid/prompt", {"n": 1, "prompt": "x"}), ("/api/quick/vid/override", {"n": 1}),
                ("/api/quick/vid/chars/FARMER/promote", None), ("/api/quick/vid/jobs", {"kind": "voice"}),
                ("/api/quick/vid/jobs/stop", None), ("/api/quick/vid/review", {"n": 1})]


def test_write_routes_require_login(tmp_path, qroot):
    runner = QuickFakeRunner()
    c = TestClient(create_app(projects_root=tmp_path, runner=runner, password="mật-khẩu-123"))
    for path, body in WRITE_ROUTES:
        assert c.post(path, json=body).status_code == 401, path
    assert runner.calls == [] and not (tmp_path / "x").exists()


def test_review_runs_while_flow_job_running(env, P):
    c, root = env.c, env.root
    ops.set_prompts(root, [{"n": 1, "prompt": P("@MODERNYOU at dawn"), "verdict": "pass", "score": 8}])
    assert c.post("/api/quick/vid/prompt", json={"n": 1, "prompt": P("@MODERNYOU at dusk")}).status_code == 200
    env.reviews.action = lambda: ops.set_review(root, 1, "fail", score=4, issues=["thiếu bối cảnh — thêm hang đá"])
    env.runner.cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    assert c.post("/api/quick/vid/jobs", json={"kind": "flow"}).status_code == 202
    r = c.post("/api/quick/vid/review", json={"n": 1})
    assert r.status_code == 200, r.text
    assert r.json() == {"n": 1, "clip": False, "summary": "Mốc 1: trượt 4/10",
                        "review": {"verdict": "fail", "score": 4.0, "issues": ["thiếu bối cảnh — thêm hang đá"]}}
    assert c.get("/api/jobs/current").json()["state"] == "running"  # job Flow vẫn chạy, kiểm duyệt không bị chặn
    cmd = env.reviews.cmds[0]
    assert cmd[0] == "claude" and "--chrome" not in cmd and "mốc 1" in cmd[-1] and "set-review" in cmd[-1]


def test_review_clip_prompt(env, P):
    from vidflow.quick import clips
    clips.set_clip_prompts(env.root, [{"n": 2, "prompt": "frame-by-frame doodle motion", "verdict": "fail", "score": 2}])
    env.reviews.action = lambda: ops.set_review(env.root, 2, "pass", score=8, clip=True)
    r = env.c.post("/api/quick/vid/review", json={"n": 2, "clip": True})
    assert r.status_code == 200 and r.json()["review"]["verdict"] == "pass"
    assert "--clip" in env.reviews.cmds[0][-1]


def test_review_errors(env, P):
    c, root = env.c, env.root
    assert c.post("/api/quick/vid/review", json={"n": 1}).status_code == 422  # chưa có prompt ảnh
    assert c.post("/api/quick/vid/review", json={"n": 1, "clip": True}).status_code == 422
    assert c.post("/api/quick/vid/review", json={"n": 99}).status_code == 422
    ops.edit_prompt(root, 1, P("a cave"))
    env.reviews.rc, env.reviews.out = 1, "claude: lỗi mạng"
    r = c.post("/api/quick/vid/review", json={"n": 1})
    assert r.status_code == 502 and "lỗi mạng" in r.json()["detail"]
    env.reviews.rc = 0  # chạy xong nhưng không ghi kết quả
    r = c.post("/api/quick/vid/review", json={"n": 1})
    assert r.status_code == 502 and "không ghi kết quả" in r.json()["detail"]
    env.reviews.rc, env.reviews.out = 124, "Kiểm duyệt quá 300 giây"
    assert c.post("/api/quick/vid/review", json={"n": 1}).status_code == 504
    assert env.reviews.cmds and len(env.reviews.cmds) == 3


def test_review_runner_real_subprocess():
    r = ReviewRunner()
    assert r.run([sys.executable, "-c", "print('Mốc 3: đạt 9/10')"]) == (0, "Mốc 3: đạt 9/10")
    r.timeout = 0.3
    rc, out = r.run([sys.executable, "-c", "import time; time.sleep(3)"])
    assert rc == 124 and "quá" in out


def test_review_old_result_unchanged_is_502(env, P):
    ops.set_prompts(env.root, [{"n": 1, "prompt": P("a cave"), "verdict": "pass", "score": 8}])
    r = env.c.post("/api/quick/vid/review", json={"n": 1})  # claude thoát 0 nhưng không ghi gì
    assert r.status_code == 502 and "không ghi kết quả" in r.json()["detail"]
    clips_mod = __import__("vidflow.quick.clips", fromlist=["x"])
    clips_mod.set_clip_prompts(env.root, [{"n": 1, "prompt": "doodle motion", "verdict": "fail", "score": 3}])
    r = env.c.post("/api/quick/vid/review", json={"n": 1, "clip": True})
    assert r.status_code == 502 and "không ghi kết quả" in r.json()["detail"]


def test_review_beats_unreadable_after_run_is_502(env, P):
    ops.edit_prompt(env.root, 1, P("a cave"))
    env.reviews.action = lambda: (env.root / "beats.json").write_text("{hỏng", encoding="utf-8")
    r = env.c.post("/api/quick/vid/review", json={"n": 1})
    assert r.status_code == 502 and "Không đọc được" in r.json()["detail"]


def test_review_runner_timeout_kills_grandchild(tmp_path):
    import os
    pidf = tmp_path / "gc.pid"
    child = "import time; time.sleep(30)"
    parent = (f"import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', {child!r}]); "
              f"open({str(pidf)!r}, 'w').write(str(p.pid)); time.sleep(30)")
    r = ReviewRunner()
    r.timeout = 1
    rc, _ = r.run([sys.executable, "-c", parent])
    assert rc == 124 and pidf.is_file()
    gc = int(pidf.read_text())
    for _ in range(50):
        try:
            os.kill(gc, 0)
        except ProcessLookupError:
            break
        try:  # tiến trình cháu mồ côi thành zombie một lúc trước khi init dọn
            if os.waitpid(gc, os.WNOHANG) != (0, 0):
                break
        except ChildProcessError:
            pass
        time.sleep(0.1)
    else:
        raise AssertionError("tiến trình cháu vẫn sống sau khi quá giờ")


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def test_upload_char_image_video_and_channel(env):
    chars.set_chars(env.root, [FARMER])
    r = env.c.post("/api/quick/vid/chars/FARMER/image", files={"file": ("farmer.PNG", PNG, "image/png")})
    assert r.status_code == 200, r.text
    assert (env.root / "refs" / "FARMER.png").read_bytes() == PNG
    url = r.json()["image_url"]
    assert url.startswith("/media/vid/refs/FARMER.png?v=")
    assert env.c.get(url.split("?")[0]).status_code == 200
    r = env.c.post("/api/quick/vid/chars/MODERNYOU/image",
                   files={"file": ("m.jpg", b"\xff\xd8\xff\xe0" + b"0" * 20, "image/jpeg")})
    assert r.status_code == 200, r.text
    assert (env.presets / "refs" / "doodle-giai-ma" / "MODERNYOU.jpg").is_file()
    assert r.json()["image_url"].startswith("/media/_presets/doodle-giai-ma/MODERNYOU.jpg?v=")
    assert env.c.get("/media/_presets/doodle-giai-ma/MODERNYOU.jpg").status_code == 200
    assert list((env.root / "tmp").iterdir()) == []


def test_upload_validation(env, monkeypatch):
    import vidflow.ui.quick_api as qa

    chars.set_chars(env.root, [FARMER])

    def up(cid, fname, data):
        return env.c.post(f"/api/quick/vid/chars/{cid}/image", files={"file": (fname, data, "application/octet-stream")})

    assert up("FARMER", "f.gif", PNG).status_code == 422
    r = up("FARMER", "f.png", b"<script>alert(1)</script>")
    assert r.status_code == 422 and "không phải ảnh" in r.json()["detail"]
    assert up("GHOST", "f.png", PNG).status_code == 404
    assert up("bad-id", "f.png", PNG).status_code == 404
    r = env.c.post("/api/quick/vid/chars/FARMER/image", data={"other": "x"})
    assert r.status_code == 422 and "Thiếu file" in r.json()["detail"]
    monkeypatch.setattr(qa, "MAX_UPLOAD", 10)
    assert up("FARMER", "f.png", PNG).status_code == 413
    assert not any((env.root / "refs").iterdir())
    assert list((env.root / "tmp").iterdir()) == []


def test_waveform(env):
    assert env.c.get("/api/quick/vid/waveform").json() == {"peaks": [], "duration": 0}
    a = array("h", [0] * 24000 + [16384] * 24000)
    with wave.open(str(env.root / "audio" / "voice.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(a.tobytes())
    r = env.c.get("/api/quick/vid/waveform?bins=100").json()
    assert r["duration"] == 2.0 and len(r["peaks"]) == 100
    assert r["peaks"][0] == 0.0 and r["peaks"][-1] == 0.5
    assert env.c.get("/api/quick/vid/waveform?bins=5").status_code == 422
    assert env.c.get("/api/quick/vid").json()["voice_url"].startswith("/media/vid/audio/voice.wav?v=")


def test_upload_uses_unique_temp_files(env, monkeypatch):
    chars.set_chars(env.root, [FARMER])
    seen = []
    real = chars.set_char_image

    def spy(root, cid, src, **kw):
        seen.append(src)
        assert src.parent == env.root / "tmp" and src.read_bytes() == PNG
        return real(root, cid, src, **kw)

    monkeypatch.setattr(chars, "set_char_image", spy)
    for _ in range(2):
        r = env.c.post("/api/quick/vid/chars/FARMER/image", files={"file": ("f.png", PNG, "image/png")})
        assert r.status_code == 200, r.text
    assert len(seen) == 2 and seen[0].suffix == ".png" and seen[0].name != "upload-FARMER.png"
    assert list((env.root / "tmp").iterdir()) == []


def test_upload_rejects_large_content_length_before_reading(env, monkeypatch):
    import vidflow.ui.quick_api as qa

    chars.set_chars(env.root, [FARMER])
    monkeypatch.setattr(qa, "MAX_UPLOAD", 100)  # PNG (40 byte) lọt qua kiểm tra sau khi đọc
    body = b"--x\r\nContent-Disposition: form-data; name=\"file\"; filename=\"f.png\"\r\n\r\n" + PNG + b"\r\n--x--\r\n"
    r = env.c.post("/api/quick/vid/chars/FARMER/image", content=body,
                   headers={"Content-Type": "multipart/form-data; boundary=x", "Content-Length": str(100 + 65536 + 1)})
    assert r.status_code == 413 and "MB" in r.json()["detail"]
    assert not any((env.root / "refs").iterdir())


def test_waveform_broken_wav_is_422(env):
    (env.root / "audio" / "voice.wav").write_bytes(b"RIFF\x00\x00garbage")
    r = env.c.get("/api/quick/vid/waveform")
    assert r.status_code == 422 and "hỏng" in r.json()["detail"]


def test_jobs_launch_failure_is_clean_error(env):
    env.runner.cmd = [str(env.tmp / "khong-co-claude")]
    r = env.c.post("/api/quick/vid/jobs", json={"kind": "voice"})
    assert r.status_code == 503 and r.json()["detail"].startswith("Không chạy được lệnh:")
    env.runner.cmd = [sys.executable, "-c", "print('ok')"]
    assert env.c.post("/api/quick/vid/jobs", json={"kind": "voice"}).status_code == 202  # không kẹt trạng thái bận


def test_voice_mode_settings_create_and_prompts_before_voice(env):
    c, root = env.c, env.root
    assert load_quick(root).voice_mode == "chunk"
    assert c.post("/api/quick/vid/settings", json={"voice_mode": "full"}).status_code == 200
    assert load_quick(root).voice_mode == "full"
    assert c.get("/api/quick/vid").json()["status"]["voice_mode"] == "full"
    assert c.post("/api/quick/vid/settings", json={"voice_mode": "nhanh"}).status_code == 422
    r = c.post("/api/quick", json={"preset": "doodle-giai-ma", "name": "vm1", "max_clips": 0, "start": False,
                                   "voice_mode": "per_beat"})
    assert r.status_code == 201, r.text
    assert load_quick(env.tmp / "vm1").voice_mode == "per_beat"
    assert c.post("/api/quick", json={"preset": "doodle-giai-ma", "name": "vm2", "max_clips": 0, "start": False,
                                      "voice_mode": "x"}).status_code == 422
    assert not (env.tmp / "vm2").exists()
    # viết prompt không cần chờ giọng đọc: mốc chưa có thời gian vẫn chạy được việc prompts
    b = load_beats(root)
    for x in b.beats:
        x.start = x.end = None
    from vidflow.quick.model import save_beats
    save_beats(root, b)
    assert c.post("/api/quick/vid/jobs", json={"kind": "prompts"}).status_code == 202
    wait_idle(c)
