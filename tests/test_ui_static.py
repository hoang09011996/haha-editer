"""Kiểm tra tĩnh giao diện (spec 2026-10-12, Giai đoạn 3): token, phông, không thiên hà/gradient/glow/emoji."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from vidflow.ui import auth
from vidflow.ui.server import STATIC

TOKENS = ("--page:#E3EBE2", "--surface:#F2F6F1", "--line:#CCD8CB", "--input:#EAF1E9", "--btn-line:#B8C7B7",
          "--text:#0E1238", "--muted:#4A4F6E", "--primary:#000080", "--secondary:#0069ba", "--success:#1fba00",
          "--success-text:#157A00", "--error:#C8283E", "--warn:#8A4B00", "--warn-bg:#FDEBD2")
FORBIDDEN = re.compile("[\U0001F000-\U0001FAFF⌀-⏿☀-➿⬀-⯿️]")
ALLOWED = {"✓"}


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_tokens_fonts_and_shell():
    css, html = _read("style.css"), _read("index.html")
    for t in TOKENS:
        assert t in css, t
    assert "family=Be+Vietnam+Pro" in html and "JetBrains+Mono" in html
    for el in ('id="railNav"', 'id="currentBox"', 'id="projectSel"', 'id="jobPill"', 'id="main"', 'action="/logout"',
               'class="shell"'):
        assert el in html, el


def test_no_galaxy_gradient_or_glow():
    css, html = _read("style.css"), _read("index.html")
    assert not (STATIC / "galaxy.js").exists()
    for bad in ("galaxy.js", 'id="stars"', "nebula"):
        assert bad not in html
    for bad in ("gradient", "glow", "nebula", "#stars"):
        assert bad not in css
    assert "gradient" not in auth.LOGIN_HTML


def test_login_page_restyled():
    page = auth.Auth("x").login_page().body.decode()
    assert "#E3EBE2" in page and "Be+Vietnam+Pro" in page and "Mật khẩu" in page
    assert not FORBIDDEN.search(page)


def test_no_emoji_in_ui():
    """Mọi file tĩnh (html/js/css, kể cả quick.js về sau) và trang đăng nhập: không emoji/dingbat, trừ dấu ✓."""
    files = {p.name: p.read_text(encoding="utf-8") for p in STATIC.iterdir() if p.suffix in (".html", ".js", ".css")}
    files["auth.LOGIN_HTML"] = auth.LOGIN_HTML
    bad = {name: sorted({c for c in FORBIDDEN.findall(text) if c not in ALLOWED}) for name, text in files.items()}
    assert {k: v for k, v in bad.items() if v} == {}


@pytest.mark.skipif(shutil.which("node") is None, reason="cần node để kiểm tra cú pháp JS")
@pytest.mark.parametrize("js", sorted(p.name for p in STATIC.glob("*.js")))
def test_js_syntax(js):
    r = subprocess.run(["node", "--check", str(STATIC / js)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_savebar_space_reserved():
    css, js = _read("style.css"), _read("app.js")
    assert "body.has-savebar .rail{height:calc(100vh - 64px)}" in css
    assert "body.has-savebar .assistant" in css and "max-height:calc(100vh - 64px)" in css
    assert 'document.body.classList.toggle("has-savebar"' in js


def test_job_state_text_shared_and_no_double_step_number():
    js = _read("app.js")
    assert js.count("function jobStateText(") == 1
    assert "jobStateText(S.job.state)" in js and "jobStateText(j.state)" in js
    assert "}, S.job.state)" not in js
    assert 'class: "f7n" }, `${i + 1}.' not in js


def test_quick_script_loaded_after_app():
    html = _read("index.html")
    assert html.index('src="/static/app.js"') < html.index('src="/static/quick.js"')
    js = _read("quick.js")
    assert "QSCREENS.board = qBoard" in js and "Lưu & kiểm duyệt" in js and "Duyệt tay" in js
    assert "qQuotaBanner" in js and "Nguồn: theo cài đặt" in js and "provider:" in js
    assert "j.quota_exhausted" in _read("app.js")


def test_quick_async_actions_guarded_against_screen_switch():
    """Phản hồi chậm (kiểm duyệt tới 300 s) về sau khi đã chuyển video/trang chủ: không vẽ đè, không toast, không gọi sai video."""
    js = _read("quick.js")
    assert 'function qActive(name = Q.name) { return S.kind === "quick" && S.name === name && Q.name === name; }' in js
    assert "if (!d || !qActive()) return;" in js  # Q.render
    assert "async function qPost(path, body, name = Q.name)" in js
    for fn in ("qSaveReview", "qOverride", "qRedo", "qToggleClip", "qPick", "qStop", "qRetryErrors", "qJob"):
        body = js[js.index(f"async function {fn}("):]
        body = body[: body.index("\n}\n")]
        assert "const name = Q.name" in body, fn
        assert "toast(e.message" not in body, fn  # lỗi qua qSay(name, …)
    retry = js[js.index("async function qRetryErrors("):]
    assert retry.index("qConfirmGen(kind)") < retry.index('"/retry"')  # hỏi trước khi xóa lỗi
    assert "/^#[0-9A-Fa-f]{6}$/" in js and 'qColor(qChar(id)?.color, "#4A4F6E")' in js
    assert "keepPanel: Q.sel !== n" in js
