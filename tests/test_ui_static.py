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


@pytest.mark.skipif(shutil.which("node") is None, reason="cần node để kiểm tra cú pháp JS")
@pytest.mark.parametrize("js", sorted(p.name for p in STATIC.glob("*.js")))
def test_js_syntax(js):
    r = subprocess.run(["node", "--check", str(STATIC / js)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
