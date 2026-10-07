import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from vidflow.ui.jobs import JobRunner, build_job_cmd
from vidflow.ui.server import create_app

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")


@pytest.fixture
def c(tmp_path):
    app = create_app(projects_root=tmp_path / "projects", runner=JobRunner())
    cl = TestClient(app)
    cl.post("/api/projects", json={"name": "anh", "title": "Ảnh"})
    d = cl.get("/api/projects/anh").json()["script"]
    d["scenes"] = [{"id": "s01", "mode": "comic", "status": "approved",
                    "frames": [{"id": "f01", "prompt": "Tuấn ngáp", "status": "approved", "caption": "Ủa?"}]}]
    assert cl.put("/api/projects/anh/script", json=d).status_code == 200
    return cl, tmp_path / "projects" / "anh"


def test_project_lists_blocked_frames(c):
    cl, _ = c
    d = cl.get("/api/projects/anh").json()
    assert d["frames_pending"] == []
    assert d["blocked"] == [{"scene": "s01", "frame": "f01", "reason": "chưa kiểm duyệt"}]


def test_review_override_unblocks(c):
    cl, _ = c
    r = cl.post("/api/projects/anh/review-override", json={"scene": "s01", "frame": "f01"})
    assert r.status_code == 200, r.text
    d = cl.get("/api/projects/anh").json()
    assert d["script"]["scenes"][0]["frames"][0]["review"]["verdict"] == "override"
    assert [x["frame"] for x in d["frames_pending"]] == ["f01"]


def test_pick_frame_endpoint(c):
    cl, root = c
    from vidflow.frames import import_frame
    from vidflow.config import Config
    from vidflow.project import Project
    img = root.parent.parent / "x.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=64x64", "-frames:v", "1", str(img)], check=True)
    for _ in range(2):
        import_frame(Project.open(root), Config(), "s01", "f01", img)
    r = cl.post("/api/projects/anh/pick-frame", json={"scene": "s01", "frame": "f01", "n": 1})
    assert r.status_code == 200 and r.json()["file"] == "frames/s01/f01_1.png"
    assert cl.get("/media/anh/frames/s01/f01_1.png").status_code == 200
    assert cl.post("/api/projects/anh/pick-frame", json={"scene": "s01", "frame": "f01", "n": 9}).status_code == 422


def test_new_job_kinds(tmp_path):
    r = build_job_cmd("render", tmp_path / "p", ["s01"])
    assert r[1:4] == ["-m", "vidflow", "render"]
    rv = build_job_cmd("review", tmp_path / "p", None)
    assert rv[0] == "claude" and "prompt-reviewer.md" in rv[-1] and "--chrome" not in rv
    ff = build_job_cmd("frames_flow", tmp_path / "p", None)
    assert "--chrome" in ff and "frames" in ff[-1] and "import-frame" in ff[-1]
