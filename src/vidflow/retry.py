from __future__ import annotations

import threading
import time
from typing import Callable, TypeVar

T = TypeVar("T")
TRANSIENT_CODES = {429, 500, 502, 503, 504}


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    try:  # lỗi mạng của httpx (SDK Gemini): hết thời gian chờ, máy chủ đóng kết nối, mất mạng
        import httpx
    except ImportError:
        httpx = None
    if httpx is not None and isinstance(exc, httpx.TransportError):
        return True
    return getattr(exc, "code", None) in TRANSIENT_CODES


def with_retry(fn: Callable[[], T], *, attempts: int = 3, base_delay: float = 2.0,
               sleep: Callable[[float], None] = time.sleep) -> T:
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if i == attempts - 1 or not is_transient(exc):
                raise
            sleep(base_delay * 2 ** i)
    raise AssertionError("unreachable")


def call_with_deadline(fn: Callable[[], T], seconds: float) -> T:
    """Chạy fn trong luồng nền, quá `seconds` thì ném TimeoutError (lỗi tạm thời → with_retry thử lại).
    Dùng khi SDK không tôn trọng timeout (ví dụ Gemini TTS treo khi hết lượt miễn phí); luồng treo là daemon
    nên không giữ tiến trình lại khi thoát."""
    box: dict = {}

    def run():
        try:
            box["value"] = fn()
        except BaseException as e:  # chuyển lỗi về luồng gọi
            box["error"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise TimeoutError(f"Không phản hồi sau {seconds:g} giây")
    if "error" in box:
        raise box["error"]
    return box["value"]
