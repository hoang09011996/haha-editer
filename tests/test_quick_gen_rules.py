import json

from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.quick import chars, ops
from vidflow.quick.model import load_beats

runner = CliRunner()
FARMER = {"id": "FARMER", "desc": "hunched farmer"}


def _prompt_all(qroot, P, texts, conts=()):
    ops.set_prompts(qroot, [{"n": i, "prompt": P(t), "verdict": "pass", "score": 8, "cont": i in conts}
                            for i, t in enumerate(texts, 1)])


def test_missing_char_image_blocks(qroot, P, img):
    chars.set_chars(qroot, [FARMER])
    _prompt_all(qroot, P, ["@FARMER a", "b", "@MODERNYOU c", "d"])
    data = ops.list_beats(qroot, todo=True)
    assert [b["n"] for b in data["beats"]] == [2, 4]
    reasons = {x["n"]: x["reason"] for x in data["blocked"]}
    assert "@FARMER" in reasons[1] and "@MODERNYOU" in reasons[3]
    sheet = chars.set_char_image(qroot, "FARMER", img())
    data = ops.list_beats(qroot, todo=True)
    row1 = next(b for b in data["beats"] if b["n"] == 1)
    assert row1["attach"] == [str(sheet.resolve())]


def test_cont_waits_for_previous_then_attaches_it(qroot, P, img):
    _prompt_all(qroot, P, ["a", "b", "c", "d"], conts=(2,))
    data = ops.list_beats(qroot, todo=True)
    assert 2 not in [b["n"] for b in data["beats"]]
    assert {"n": 2, "reason": "chờ ảnh mốc 1"} in data["blocked"]
    ops.set_image(qroot, 1, img())
    row2 = next(b for b in ops.list_beats(qroot, todo=True)["beats"] if b["n"] == 2)
    assert row2["attach"] == [str((qroot / "images" / "001_00-00.png").resolve())]


def test_cont_waits_when_previous_marked_redo(qroot, P, img):
    _prompt_all(qroot, P, ["a", "b", "c", "d"], conts=(2,))
    ops.set_image(qroot, 1, img())
    ops.mark_redo(qroot, [1])
    assert 2 not in [b["n"] for b in ops.list_beats(qroot, todo=True)["beats"]]


def test_errored_beats_leave_todo_until_retry(qroot, P):
    _prompt_all(qroot, P, ["a", "b", "c", "d"])
    ops.record_fail(qroot, 3, "Flow từ chối")
    assert 3 not in [b["n"] for b in ops.list_beats(qroot, todo=True)["beats"]]
    ops.clear_errors(qroot, [3])
    assert 3 in [b["n"] for b in ops.list_beats(qroot, todo=True)["beats"]]


def test_non_todo_rows_carry_blocked_reason(qroot, P):
    chars.set_chars(qroot, [FARMER])
    _prompt_all(qroot, P, ["@FARMER a", "b", "c", "d"])
    rows = ops.list_beats(qroot)["beats"]
    assert "@FARMER" in rows[0]["blocked"] and rows[1]["blocked"] is None
    assert "blocked" not in ops.list_beats(qroot)  # khóa tổng chỉ có khi --todo


def test_status_summary_counts(qroot, P):
    chars.set_chars(qroot, [FARMER])
    _prompt_all(qroot, P, ["@FARMER a", "b", "c", "d"])
    ops.record_fail(qroot, 2, "x")
    s = ops.status_summary(qroot)
    assert s["blocked"] == 1 and s["errors"] == 1
    assert s["chars_missing"] == ["FARMER"]
    assert s["clips"] == {"max": 12, "enabled": 0, "ok": 0, "error": 0}
    assert "Bị chặn: 1" in ops.format_status(s)


def test_cli_beats_todo_json_has_blocked(qroot, P):
    chars.set_chars(qroot, [FARMER])
    _prompt_all(qroot, P, ["@FARMER a", "b", "c", "d"])
    r = runner.invoke(app, ["quick", "beats", "-p", str(qroot), "--json", "--todo"])
    data = json.loads(r.output)
    assert data["blocked"][0]["n"] == 1 and [b["n"] for b in data["beats"]] == [2, 3, 4]
