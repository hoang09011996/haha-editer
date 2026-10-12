"""Khóa project (.vidflow.lock): nhiều tiến trình ghi beats.json/quick.yaml không làm mất cập nhật."""
import subprocess
import sys
import textwrap

import pytest

from vidflow.errors import VidflowError
from vidflow.quick import chars, clips, model, ops
from vidflow.quick.model import LOCK_FILE, load_beats, load_quick, project_lock


@pytest.fixture
def fast_lock(monkeypatch):
    monkeypatch.setattr(model, "LOCK_TIMEOUT", 0.3)


def test_lock_file_in_root_and_busy_raises(qroot, fast_lock):
    with project_lock(qroot):
        assert (qroot / LOCK_FILE).is_file()
        with pytest.raises(VidflowError, match="đang bận"):
            ops.record_fail(qroot, 1, "x")
    assert ops.record_fail(qroot, 1, "x").error == "x"


@pytest.mark.parametrize("call", [
    lambda r, img: ops.advance(r, "built"),
    lambda r, img: ops.set_ideas(r, [{"title": "a"}]),
    lambda r, img: ops.pick_idea(r, 1),
    lambda r, img: ops.set_beat_texts(r, ["x"]),
    lambda r, img: ops.set_prompts(r, []),
    lambda r, img: ops.edit_prompt(r, 1, "m", clip=True),
    lambda r, img: ops.set_review(r, 1, "pass"),
    lambda r, img: ops.record_fail(r, 1, "x"),
    lambda r, img: ops.clear_errors(r),
    lambda r, img: ops.record_limit(r, "flow", "image"),
    lambda r, img: ops.clear_limits(r, "flow"),
    lambda r, img: ops.set_image(r, 1, img()),
    lambda r, img: ops.mark_redo(r, [1]),
    lambda r, img: ops.update_settings(r, allow_cont=False),
    lambda r, img: chars.set_chars(r, []),
    lambda r, img: chars.set_char_image(r, "MODERNYOU", img(), channel=True),
    lambda r, img: chars.promote(r, "NOPE"),
    lambda r, img: clips.set_clip_enabled(r, [1], True),
    lambda r, img: clips.set_clip_prompts(r, []),
    lambda r, img: clips.set_clip(r, 1, img("c.mp4")),
])
def test_mutators_take_the_lock(qroot, img, fast_lock, call):
    with project_lock(qroot):
        with pytest.raises(VidflowError, match="đang bận"):
            call(qroot, img)


def test_no_nested_locking(qroot, P, img, fast_lock):
    """set_prompts/set_review/set_image gọi advance bên trong — khóa lồng nhau sẽ hết giờ chờ."""
    ops.set_prompts(qroot, [{"n": n, "prompt": P("x"), "verdict": "pass", "score": 8} for n in (1, 2, 3)])
    ops.set_prompts(qroot, [{"n": 4, "prompt": P("x"), "verdict": "fail", "score": 3}])
    ops.set_review(qroot, 4, "override")
    assert load_quick(qroot).stage == "prompted"
    for n in (1, 2, 3, 4):
        ops.set_image(qroot, n, img())
    assert load_quick(qroot).stage == "imaged"


def test_concurrent_processes_keep_all_updates(qroot, P):
    n_beats = 12
    ops.set_beat_texts(qroot, [f"Câu {i}." for i in range(1, n_beats + 1)])
    ops.set_prompts(qroot, [{"n": n, "prompt": P("x"), "verdict": "fail", "score": 1}
                            for n in range(1, n_beats + 1)])
    script = textwrap.dedent("""
        import sys
        from vidflow.quick import ops
        root, n = sys.argv[1], int(sys.argv[2])
        for k in range(5):
            ops.record_fail(root, n, f"lỗi {n}-{k}")
            ops.set_review(root, n, "pass", score=n + k)
    """)
    procs = [subprocess.Popen([sys.executable, "-c", script, str(qroot), str(n)])
             for n in range(1, n_beats + 1)]
    assert all(p.wait(timeout=60) == 0 for p in procs)
    beats = load_beats(qroot).beats
    assert [b.error for b in beats] == [f"lỗi {n}-4" for n in range(1, n_beats + 1)]
    assert [b.review.score for b in beats] == [float(n + 4) for n in range(1, n_beats + 1)]
    assert load_quick(qroot).stage == "prompted"
