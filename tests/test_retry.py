import pytest

from vidflow.retry import is_transient, with_retry


class ApiErr(Exception):
    def __init__(self, code):
        self.code = code


def test_is_transient():
    assert is_transient(ApiErr(429))
    assert is_transient(ApiErr(503))
    assert is_transient(ConnectionError())
    assert not is_transient(ApiErr(400))
    assert not is_transient(ValueError())


def test_retries_then_succeeds():
    calls, sleeps = [], []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ApiErr(503)
        return "ok"

    assert with_retry(fn, sleep=sleeps.append) == "ok"
    assert sleeps == [2.0, 4.0]


def test_gives_up_after_attempts():
    with pytest.raises(ApiErr):
        with_retry(lambda: (_ for _ in ()).throw(ApiErr(500)), sleep=lambda s: None)


def test_non_transient_not_retried():
    calls = []

    def fn():
        calls.append(1)
        raise ApiErr(400)

    with pytest.raises(ApiErr):
        with_retry(fn, sleep=lambda s: None)
    assert len(calls) == 1


def test_http_transport_errors_are_transient():
    import httpx
    assert is_transient(httpx.ReadTimeout("treo"))
    assert is_transient(httpx.RemoteProtocolError("máy chủ đóng kết nối"))
    assert is_transient(httpx.ConnectError("mất mạng"))
