from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")
TRANSIENT_CODES = {429, 500, 502, 503, 504}


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError)):
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
