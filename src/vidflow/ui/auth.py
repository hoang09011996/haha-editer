"""Đăng nhập bằng mật khẩu cho UI khi mở ra ngoài (Tailscale Funnel)."""
from __future__ import annotations

import hmac
import secrets
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

COOKIE = "vf_session"
MAX_FAILS = 5
WINDOW_S = 600
SESSION_TTL_S = 7 * 24 * 3600
OPEN_PATHS = ("/login", "/logout")

LOGIN_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>vidflow · Đăng nhập</title><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:Arial,sans-serif;color:#eef1ff;
background:radial-gradient(40% 35% at 20% 25%,rgba(139,92,246,.35),transparent 70%),radial-gradient(45% 40% at 70% 80%,rgba(0,105,186,.35),transparent 70%),#03021a}
form{width:min(360px,90vw);padding:28px;border-radius:20px;background:rgba(18,16,64,.6);border:1px solid rgba(160,170,255,.25);box-shadow:0 0 50px rgba(139,92,246,.35)}
h1{margin:0 0 18px;font-size:22px}h1 span{color:#fbbf24}
input{width:100%;box-sizing:border-box;padding:10px 12px;border-radius:10px;border:1px solid rgba(160,170,255,.3);background:rgba(5,4,40,.7);color:#fff;font-size:15px}
button{margin-top:14px;width:100%;padding:10px;border:none;border-radius:999px;color:#fff;font-size:15px;cursor:pointer;background:linear-gradient(135deg,#0069ba,#8b5cf6)}
p{color:#ff8fa3;font-size:13px;min-height:1em}</style></head><body>
<form method="post" action="/login"><h1><span>✦</span> vidflow Studio</h1>
<label>Mật khẩu<br><input type="password" name="password" autofocus autocomplete="current-password"></label>
<p>{msg}</p><button>Đăng nhập</button></form></body></html>"""


class Auth:
    def __init__(self, password: str):
        self.password = password.encode()
        self.sessions: dict[str, float] = {}
        self.fails: dict[str, deque] = defaultdict(deque)

    @staticmethod
    def client_ip(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for", "")
        return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")

    def locked(self, ip: str) -> bool:
        q = self.fails[ip]
        while q and q[0] < time.time() - WINDOW_S:
            q.popleft()
        return len(q) >= MAX_FAILS

    def valid(self, request: Request) -> bool:
        tok = request.cookies.get(COOKIE, "")
        exp = self.sessions.get(tok)
        if exp is None or exp < time.time():
            self.sessions.pop(tok, None)
            return False
        return True

    def login_page(self, msg: str = "", status: int = 200) -> HTMLResponse:
        return HTMLResponse(LOGIN_HTML.replace("{msg}", msg), status_code=status)

    async def login(self, request: Request):
        ip = self.client_ip(request)
        if self.locked(ip):
            return self.login_page("Sai quá nhiều lần. Thử lại sau 10 phút.", 429)
        form = await request.form()
        given = str(form.get("password", "")).encode()
        if not hmac.compare_digest(given, self.password):
            self.fails[ip].append(time.time())
            return self.login_page("Sai mật khẩu.", 401)
        self.fails.pop(ip, None)
        tok = secrets.token_urlsafe(32)
        self.sessions[tok] = time.time() + SESSION_TTL_S
        secure = request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
        r = RedirectResponse("/", status_code=303)
        r.set_cookie(COOKIE, tok, max_age=SESSION_TTL_S, httponly=True, samesite="strict", secure=secure)
        return r

    def logout(self, request: Request):
        self.sessions.pop(request.cookies.get(COOKIE, ""), None)
        r = RedirectResponse("/login", status_code=303)
        r.delete_cookie(COOKIE)
        return r

    async def middleware(self, request: Request, call_next):
        path = request.url.path
        if path in OPEN_PATHS or self.valid(request):
            return await call_next(request)
        if path.startswith("/api/") or path.startswith("/media/"):
            return JSONResponse({"detail": "Cần đăng nhập"}, status_code=401)
        return RedirectResponse("/login", status_code=303)
