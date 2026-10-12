import pytest
from fastapi.testclient import TestClient

from vidflow.ui.jobs import JobRunner
from vidflow.ui.server import create_app

PW = "đúng-mật-khẩu-123"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(projects_root=tmp_path / "p", runner=JobRunner(), password=PW))


def test_no_password_means_open(tmp_path):
    c = TestClient(create_app(projects_root=tmp_path / "p", runner=JobRunner()))
    assert c.get("/api/projects").status_code == 200


def test_api_requires_login(client):
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/projects", json={"name": "x", "title": "x"}).status_code == 401
    assert client.get("/media/x/audio/a.wav").status_code == 401


def test_page_redirects_to_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert client.get("/static/app.js", follow_redirects=False).status_code == 303
    assert "Mật khẩu" in client.get("/login").text


def test_wrong_then_right_password(client):
    r = client.post("/login", data={"password": "sai"}, follow_redirects=False)
    assert r.status_code == 401
    r = client.post("/login", data={"password": PW}, follow_redirects=False)
    assert r.status_code == 303
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie.replace("Strict", "strict")
    assert client.get("/api/projects").status_code == 200
    assert client.get("/").status_code == 200


def test_secure_cookie_behind_https_proxy(client):
    r = client.post("/login", data={"password": PW}, headers={"X-Forwarded-Proto": "https"}, follow_redirects=False)
    assert "Secure" in r.headers["set-cookie"]


def test_lockout_after_failures(client):
    for _ in range(5):
        client.post("/login", data={"password": "sai"})
    r = client.post("/login", data={"password": PW}, follow_redirects=False)
    assert r.status_code == 429


def test_logout(client):
    client.post("/login", data={"password": PW})
    client.post("/logout")
    assert client.get("/api/projects").status_code == 401


def test_forged_cookie_rejected(client):
    client.cookies.set("vf_session", "gia-mao")
    assert client.get("/api/projects").status_code == 401


QUICK_ROUTES = [
    ("get", "/api/quick"), ("get", "/api/presets"), ("get", "/api/quick/vid"), ("post", "/api/quick"),
    ("post", "/api/quick/vid/settings"), ("post", "/api/quick/vid/pick"), ("post", "/api/quick/vid/redo"),
    ("post", "/api/quick/vid/retry"), ("post", "/api/quick/vid/clip"), ("post", "/api/quick/vid/prompt"),
    ("post", "/api/quick/vid/review"), ("post", "/api/quick/vid/override"),
    ("post", "/api/quick/vid/chars/FARMER/image"), ("post", "/api/quick/vid/chars/FARMER/promote"),
    ("post", "/api/quick/vid/jobs"), ("post", "/api/quick/vid/jobs/stop"), ("get", "/api/quick/vid/waveform"),
    ("get", "/media/vid/images/001_00-00.jpg"), ("get", "/media/_presets/doodle-giai-ma/MODERNYOU.png"),
]


@pytest.mark.parametrize("method,path", QUICK_ROUTES)
def test_quick_routes_require_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401
