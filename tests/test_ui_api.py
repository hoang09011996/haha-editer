import sys
import time

import pytest
from fastapi.testclient import TestClient

from vidflow.ui.jobs import JobRunner, build_job_cmd
from vidflow.ui.server import create_app


class FakeRunner(JobRunner):
    """Thay lệnh thật bằng lệnh python ngắn để test."""

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def command_for(self, kind, project_root, scenes):
        return self.cmd


@pytest.fixture
def client(tmp_path):
    runner = FakeRunner([sys.executable, "-c", "print('xin chào job')"])
    app = create_app(projects_root=tmp_path / "projects", runner=runner)
    return TestClient(app), tmp_path / "projects", runner


def new(c, name="cafe"):
    return c.post("/api/projects", json={"name": name, "title": "Cà phê", "idea": "sáng", "aspect": "9:16",
                                         "video_model": "Veo 3.1 Fast", "resolution": "720p"})


def test_index_served(client):
    c, _, _ = client
    r = c.get("/")
    assert r.status_code == 200 and "vidflow" in r.text


def test_create_list_get(client):
    c, root, _ = client
    assert new(c).status_code == 201
    assert (root / "cafe" / "script.yaml").is_file()
    assert [p["name"] for p in c.get("/api/projects").json()] == ["cafe"]
    d = c.get("/api/projects/cafe").json()
    assert d["script"]["title"] == "Cà phê"
    assert d["script"]["profile"]["idea"] == "sáng"
    assert d["script"]["flow"] == {"video_model": "Veo 3.1 Fast", "resolution": "720p"}
    assert d["status"] == [] and d["job"] is None


def test_create_rejects_bad_name_and_duplicate(client):
    c, _, _ = client
    assert c.post("/api/projects", json={"name": "Cà phê!", "title": "x"}).status_code == 422
    new(c)
    assert new(c).status_code == 409


def test_put_script_validates_and_saves(client):
    c, root, _ = client
    new(c)
    d = c.get("/api/projects/cafe").json()["script"]
    d["locations"] = [{"id": "bep", "name": "Bếp"}]
    d["scenes"] = [{"id": "s01", "location": "bep", "action": "uống", "duration": 6}]
    r = c.put("/api/projects/cafe/script", json=d)
    assert r.status_code == 200, r.text
    got = c.get("/api/projects/cafe").json()
    assert got["script"]["scenes"][0]["location"] == "bep"
    assert got["prompt_stale"] == {"s01": True}
    d["scenes"][0]["location"] = "nope"
    r = c.put("/api/projects/cafe/script", json=d)
    assert r.status_code == 422 and "bối cảnh không tồn tại" in r.json()["detail"]


def test_media_cannot_escape_project(client):
    c, root, _ = client
    new(c)
    (root / "cafe" / "audio" / "s01.wav").write_bytes(b"RIFF")
    assert c.get("/media/cafe/audio/s01.wav").status_code == 200
    assert c.get("/media/cafe/script.yaml").status_code == 404
    assert c.get("/media/cafe/audio/..%2Fscript.yaml").status_code == 404
    new(c, "other")
    assert c.get("/media/cafe/audio/..%2F..%2Fother%2Fscript.yaml").status_code == 404
    assert c.get("/media/cafe/../../etc/passwd").status_code == 404


def test_unknown_project_404(client):
    c, _, _ = client
    assert c.get("/api/projects/nope").status_code == 404


def test_job_runs_logs_and_blocks_second(client):
    c, _, runner = client
    new(c)
    runner.cmd = [sys.executable, "-c", "import time; print('bắt đầu', flush=True); time.sleep(0.6); print('xong')"]
    assert c.post("/api/projects/cafe/jobs", json={"kind": "tts"}).status_code == 202
    assert c.post("/api/projects/cafe/jobs", json={"kind": "build"}).status_code == 409
    for _ in range(50):
        j = c.get("/api/jobs/current").json()
        if j["state"] != "running":
            break
        time.sleep(0.1)
    assert j["state"] == "done" and "xong" in j["log"] and j["kind"] == "tts"


def test_job_failure_reported(client):
    c, _, runner = client
    new(c)
    runner.cmd = [sys.executable, "-c", "import sys; print('lỗi rồi'); sys.exit(3)"]
    c.post("/api/projects/cafe/jobs", json={"kind": "build"})
    for _ in range(50):
        j = c.get("/api/jobs/current").json()
        if j["state"] != "running":
            break
        time.sleep(0.1)
    assert j["state"] == "failed" and j["returncode"] == 3


def test_unknown_job_kind(client):
    c, _, _ = client
    new(c)
    assert c.post("/api/projects/cafe/jobs", json={"kind": "gen_api"}).status_code == 422


def test_build_job_cmd_shapes(tmp_path):
    cmd = build_job_cmd("tts", tmp_path / "p", ["s01"])
    assert cmd[1:4] == ["-m", "vidflow", "tts"] and cmd[-2:] == ["-s", "s01"]
    flow = build_job_cmd("flow", tmp_path / "p", None)
    assert flow[0] == "claude" and "--chrome" in flow and "flow-operator.md" in flow[-1]
    script = build_job_cmd("script", tmp_path / "p", None)
    assert "--chrome" not in script and "scriptwriter.md" in script[-1]
