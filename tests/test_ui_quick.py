"""API quy trình nhanh trên UI (spec 2026-10-12, Giai đoạn 3)."""
import sys
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vidflow.quick import chars, ops
from vidflow.quick.model import create_quick
from vidflow.ui.jobs import JobRunner
from vidflow.ui.quick_api import beat_state
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


@pytest.fixture
def env(tmp_path, qroot, quick_presets):
    runner = QuickFakeRunner()
    c = TestClient(create_app(projects_root=tmp_path, runner=runner))
    yield SimpleNamespace(c=c, root=qroot, tmp=tmp_path, presets=quick_presets, runner=runner)
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
