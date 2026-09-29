import sys

import pytest
from fastapi.testclient import TestClient

from vidflow.ui.jobs import JobRunner, build_job_cmd
from vidflow.ui.server import create_app
from vidflow.ui.suggest import Suggester, parse_suggestions


class FakeSuggester(Suggester):
    def __init__(self, out):
        self.out = out
        self.prompts = []

    def run_llm(self, prompt):
        self.prompts.append(prompt)
        return self.out


def test_parse_suggestions_tolerates_noise():
    assert parse_suggestions('Đây:\n```json\n["a", "b", "c"]\n```') == ["a", "b", "c"]
    assert parse_suggestions('["x"]') == ["x"]
    with pytest.raises(ValueError):
        parse_suggestions("không có json")
    with pytest.raises(ValueError):
        parse_suggestions("[1, 2]")


@pytest.fixture
def app_client(tmp_path):
    sug = FakeSuggester('["Gợi ý một", "Gợi ý hai", "Gợi ý ba"]')
    app = create_app(projects_root=tmp_path / "projects", runner=JobRunner(), suggester=sug)
    c = TestClient(app)
    c.post("/api/projects", json={"name": "cafe", "title": "Cà phê", "idea": "video hài cà phê sáng"})
    return c, sug


def test_suggest_uses_project_context(app_client):
    c, sug = app_client
    r = c.post("/api/suggest", json={"project": "cafe", "field": "narration", "label": "Lời dẫn",
                                     "current": "", "scene_id": None})
    assert r.status_code == 200, r.text
    assert r.json()["suggestions"] == ["Gợi ý một", "Gợi ý hai", "Gợi ý ba"]
    assert "video hài cà phê sáng" in sug.prompts[0] and "Lời dẫn" in sug.prompts[0]


def test_suggest_without_project(app_client):
    c, sug = app_client
    r = c.post("/api/suggest", json={"field": "idea", "label": "Ý tưởng", "current": "cà phê"})
    assert r.status_code == 200 and len(r.json()["suggestions"]) == 3


def test_suggest_bad_llm_output_502(tmp_path):
    app = create_app(projects_root=tmp_path / "p", runner=JobRunner(), suggester=FakeSuggester("xin lỗi"))
    r = TestClient(app).post("/api/suggest", json={"field": "idea", "label": "Ý tưởng"})
    assert r.status_code == 502


def test_assist_job_carries_instruction(tmp_path):
    cmd = build_job_cmd("assist", tmp_path / "p", ["s02"], instruction="làm cảnh 2 hài hơn")
    assert cmd[0] == "claude" and "làm cảnh 2 hài hơn" in cmd[-1] and "s02" in cmd[-1]
    with pytest.raises(ValueError):
        build_job_cmd("assist", tmp_path / "p", None, instruction="")


def test_suggester_default_command_uses_claude_haiku():
    cmd = Suggester().command("hỏi")
    assert cmd[:2] == ["claude", "-p"] and "--model" in cmd and cmd[-1] == "hỏi"
