import json

import pytest
from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.quick.model import load_beats, load_quick, save_beats
from vidflow.quick.preset import load_preset

runner = CliRunner()
PRESET = "doodle-giai-ma"


def ok(args):
    r = runner.invoke(app, [str(a) for a in args])
    assert r.exit_code == 0, r.output
    return r


def fail(args):
    r = runner.invoke(app, [str(a) for a in args])
    assert r.exit_code == 1, r.output
    assert "Traceback" not in r.output
    return r


@pytest.fixture
def qp(tmp_path):
    root = tmp_path / "vid"
    ok(["quick", "new", root, "--preset", PRESET, "--title", "Thử nhanh"])
    return root


def _ideas(tmp_path, n=5):
    f = tmp_path / "ideas.json"
    f.write_text(json.dumps([{"title": f"Ý tưởng {i}", "hook": f"hook {i}", "why_viral": "vì"}
                             for i in range(1, n + 1)], ensure_ascii=False), encoding="utf-8")
    return f


def _texts(tmp_path, texts):
    f = tmp_path / "beats_in.json"
    f.write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")
    return f


def _timed(root, starts):
    b = load_beats(root)
    for beat, s in zip(b.beats, starts):
        beat.start, beat.end = s, s + 1.0
    save_beats(root, b)


def test_new_creates_quick_project(qp):
    q = load_quick(qp)
    assert q.preset == PRESET and q.title == "Thử nhanh" and q.stage == "new"


def test_new_unknown_preset(tmp_path):
    fail(["quick", "new", tmp_path / "x", "--preset", "khong-co"])


def test_ideas_and_pick(qp, tmp_path):
    ok(["quick", "set-ideas", "-p", qp, "--json", _ideas(tmp_path)])
    q = load_quick(qp)
    assert len(q.ideas) == 5 and q.stage == "ideas"
    fail(["quick", "pick", "-p", qp, 6])
    ok(["quick", "pick", "-p", qp, 3])
    q = load_quick(qp)
    assert q.picked == 3 and q.stage == "picked"
    assert q.title == "Ý tưởng 3"


def test_set_beats_texts(qp, tmp_path):
    ok(["quick", "set-beats", "-p", qp, "--json", _texts(tmp_path, ["Câu một.", {"text": "Câu hai."}, " "])])
    b = load_beats(qp)
    assert b.aspect == "16:9"
    assert [x.text for x in b.beats] == ["Câu một.", "Câu hai."]
    assert [x.n for x in b.beats] == [1, 2]
    assert all(x.status == "pending" and x.image is None and x.start is None for x in b.beats)
    assert load_quick(qp).stage == "script"


def test_set_prompt_requires_anchors(qp, tmp_path):
    ok(["quick", "set-beats", "-p", qp, "--json", _texts(tmp_path, ["A.", "B."])])
    pr = load_preset(PRESET)
    good = f"{pr.style_anchor_start} a stick figure with spiky orange hair, {pr.style_anchor_end}"
    ok(["quick", "set-prompt", "-p", qp, 1, "--prompt", good, "--verdict", "pass", "--score", 8,
        "--issue", "nhỏ"])
    b = load_beats(qp)
    assert b.beats[0].prompt == good
    assert b.beats[0].review.verdict == "pass" and b.beats[0].review.score == 8
    assert b.beats[0].review.issues == ["nhỏ"]
    r = fail(["quick", "set-prompt", "-p", qp, 2, "--prompt", "a cat", "--verdict", "pass", "--score", 9])
    assert "câu neo" in r.output
    fail(["quick", "set-prompt", "-p", qp, 9, "--prompt", good, "--verdict", "pass", "--score", 9])
    fail(["quick", "set-prompt", "-p", qp, 2, "--prompt", good, "--verdict", "maybe", "--score", 9])


def test_set_prompts_bulk(qp, tmp_path):
    ok(["quick", "set-beats", "-p", qp, "--json", _texts(tmp_path, ["A.", "B."])])
    pr = load_preset(PRESET)
    p = f"{pr.style_anchor_start} x, {pr.style_anchor_end}"
    f = tmp_path / "pr.json"
    f.write_text(json.dumps([{"n": 1, "prompt": p, "verdict": "pass", "score": 8},
                             {"n": 2, "prompt": p, "verdict": "fail", "score": 5, "issues": ["mơ hồ"]}]),
                 encoding="utf-8")
    ok(["quick", "set-prompts", "-p", qp, "--json", f])
    b = load_beats(qp)
    assert [x.review.verdict for x in b.beats] == ["pass", "fail"]
    assert load_quick(qp).stage == "script"  # chưa đủ pass → chưa sang prompts


def test_set_image_and_redo(qp, tmp_path):
    ok(["quick", "set-beats", "-p", qp, "--json", _texts(tmp_path, ["A.", "B.", "C."])])
    src = tmp_path / "dl.jpeg"
    src.write_bytes(b"\xff\xd8img")
    r = fail(["quick", "set-image", "-p", qp, 2, src])
    assert "voice" in r.output  # chưa có mốc thời gian
    _timed(qp, [0.0, 125.4, 130.0])
    ok(["quick", "set-image", "-p", qp, 2, src])
    b = load_beats(qp)
    assert b.beats[1].image == "images/002_02-05.jpg" and b.beats[1].status == "ok"
    assert (qp / "images" / "002_02-05.jpg").read_bytes() == b"\xff\xd8img"
    ok(["quick", "redo", "-p", qp, 2, 3])
    b = load_beats(qp)
    assert [x.status for x in b.beats] == ["pending", "redo", "redo"]
    assert b.beats[1].image == "images/002_02-05.jpg"  # giữ ảnh cũ tới khi có ảnh mới
    png = tmp_path / "new.png"
    png.write_bytes(b"\x89PNGx")
    ok(["quick", "set-image", "-p", qp, 2, png])
    b = load_beats(qp)
    assert b.beats[1].image == "images/002_02-05.png" and b.beats[1].status == "ok"
    assert not (qp / "images" / "002_02-05.jpg").exists()
    fail(["quick", "redo", "-p", qp, 7])


def test_beats_json_todo_lists_pending_and_redo(qp, tmp_path):
    ok(["quick", "set-beats", "-p", qp, "--json", _texts(tmp_path, ["A.", "B."])])
    _timed(qp, [0.0, 3.0])
    pr = load_preset(PRESET)
    p = f"{pr.style_anchor_start} x, {pr.style_anchor_end}"
    ok(["quick", "set-prompt", "-p", qp, 1, "--prompt", p, "--verdict", "pass", "--score", 8])
    ok(["quick", "set-prompt", "-p", qp, 2, "--prompt", p, "--verdict", "pass", "--score", 8])
    src = tmp_path / "a.jpg"
    src.write_bytes(b"x")
    ok(["quick", "set-image", "-p", qp, 1, src])
    r = ok(["quick", "beats", "-p", qp, "--json", "--todo"])
    data = json.loads(r.output)
    assert [d["n"] for d in data["beats"]] == [2]
    assert data["beats"][0]["file"] == "images/002_00-03.jpg"
    assert data["aspect"] == "16:9"


def test_status_output(qp, tmp_path):
    ok(["quick", "set-ideas", "-p", qp, "--json", _ideas(tmp_path)])
    ok(["quick", "set-beats", "-p", qp, "--json", _texts(tmp_path, ["A.", "B."])])
    r = ok(["quick", "status", "-p", qp, "--json"])
    s = json.loads(r.output)
    assert s["stage"] == "script" and s["ideas"] == 5
    assert s["beats"]["total"] == 2 and s["beats"]["imaged"] == 0
    r = ok(["quick", "status", "-p", qp])
    assert "2 mốc" in r.output


def test_llm_commands_call_run_claude(qp, tmp_path, monkeypatch):
    import vidflow.quick.jobs as jobs
    calls = []
    monkeypatch.setattr(jobs, "run_claude", lambda kind, root, preset, **kw: calls.append((kind, root, preset.id)) or 0)
    ok(["quick", "ideas", "-p", qp])
    fail(["quick", "script", "-p", qp])  # chưa chọn ý tưởng
    fail(["quick", "prompts", "-p", qp])  # chưa có beats
    ok(["quick", "set-ideas", "-p", qp, "--json", _ideas(tmp_path)])
    ok(["quick", "pick", "-p", qp, 1])
    ok(["quick", "script", "-p", qp])
    ok(["quick", "set-beats", "-p", qp, "--json", _texts(tmp_path, ["A."])])
    for kind in ("prompts", "sheets", "flow", "clips"):
        ok(["quick", kind, "-p", qp])
    monkeypatch.setattr(jobs, "run_claude", lambda *a, **kw: 2)
    assert "mã 2" in fail(["quick", "flow", "-p", qp]).output
    assert [c[0] for c in calls] == ["ideas", "script", "prompts", "sheets", "flow", "clips"]
    assert all(c[2] == PRESET for c in calls)


def test_llm_command_print_task(qp):
    r = ok(["quick", "ideas", "-p", qp, "--print"])
    assert "doodle-brief.txt" in r.output


def test_preset_list_and_show():
    r = ok(["preset", "list"])
    assert PRESET in r.output
    r = ok(["preset", "show", PRESET])
    assert "Hand-drawn 2D doodle" in r.output
