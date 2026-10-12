import json

import pytest
from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.errors import VidflowError
from vidflow.quick import chars, ops
from vidflow.quick.model import load_beats, load_quick
from vidflow.quick.model import Character
from vidflow.quick.preset import load_preset, save_preset

runner = CliRunner()
FARMER = {"id": "FARMER", "name": "Nông dân", "desc": "hunched neolithic farmer, rough tunic", "color": "#8B5E3C"}


def test_parse_refs_order_unique_and_punctuation():
    assert chars.parse_refs("@FARMER's hoe, @MODERNYOU and @FARMER.") == ["FARMER", "MODERNYOU"]
    assert chars.parse_refs("") == []


def test_parse_refs_rejects_lowercase():
    with pytest.raises(VidflowError, match="IN HOA"):
        chars.parse_refs("a doodle of @modernyou waking up")


def test_lookup_merges_channel_and_video(qroot):
    chars.set_chars(qroot, [FARMER])
    known = chars.lookup(qroot)
    assert set(known) == {"MODERNYOU", "FARMER"}
    assert known["MODERNYOU"].scope == "channel" and known["FARMER"].scope == "video"
    assert known["FARMER"].image is None


def test_channel_chars_filter(qroot):
    ops.update_settings(qroot, channel_chars=[])
    assert "MODERNYOU" not in chars.lookup(qroot)


def test_set_chars_validation(qroot):
    with pytest.raises(VidflowError, match="Trùng id"):
        chars.set_chars(qroot, [FARMER, FARMER])
    with pytest.raises(VidflowError, match="bộ kênh"):
        chars.set_chars(qroot, [{"id": "MODERNYOU", "desc": "x"}])
    with pytest.raises(VidflowError, match="không hợp lệ"):
        chars.set_chars(qroot, [{"id": "farmer", "desc": "x"}])


@pytest.mark.parametrize("color", ["red", "#FFF", "#12345G", "#123456;background:url(x)", "#123456\n", "url(x)"])
def test_set_chars_rejects_bad_color(qroot, color):
    with pytest.raises(VidflowError, match="Màu nhân vật"):
        chars.set_chars(qroot, [{**FARMER, "color": color}])
    assert load_quick(qroot).characters == []


def test_set_chars_accepts_hex_or_empty_color(qroot):
    q = chars.set_chars(qroot, [{**FARMER, "color": "#8B5E3C"}, {"id": "ANCESTOR", "desc": "x", "color": ""}])
    assert [c.color for c in q.characters] == ["#8B5E3C", ""]


def test_set_chars_refuses_removing_char_in_use(qroot, P):
    chars.set_chars(qroot, [FARMER])
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("@FARMER digging"), "verdict": "pass", "score": 8}])
    with pytest.raises(VidflowError, match="@FARMER"):
        chars.set_chars(qroot, [])
    assert [c.id for c in load_quick(qroot).characters] == ["FARMER"]


def test_set_char_image_video_and_channel(qroot, img, quick_presets):
    chars.set_chars(qroot, [FARMER])
    dest = chars.set_char_image(qroot, "FARMER", img("f.jpeg"))
    assert dest == qroot / "refs" / "FARMER.jpg" and dest.is_file()
    dest2 = chars.set_char_image(qroot, "FARMER", img("f.png"))
    assert dest2.name == "FARMER.png" and not dest.exists()  # thay ảnh cũ khác đuôi
    with pytest.raises(VidflowError, match="--channel"):
        chars.set_char_image(qroot, "MODERNYOU", img())
    ch = chars.set_char_image(qroot, "MODERNYOU", img(), channel=True)
    assert ch == quick_presets / "refs" / "doodle-giai-ma" / "MODERNYOU.png"
    assert chars.lookup(qroot)["MODERNYOU"].image == ch
    with pytest.raises(VidflowError, match="không hỗ trợ"):
        chars.set_char_image(qroot, "FARMER", img("x.gif"))


def test_promote_moves_char_and_image(qroot, img, quick_presets):
    chars.set_chars(qroot, [FARMER])
    chars.set_char_image(qroot, "FARMER", img())
    chars.promote(qroot, "FARMER")
    assert "FARMER" in [c.id for c in load_preset("doodle-giai-ma").characters]
    assert load_quick(qroot).characters == []
    assert (quick_presets / "refs" / "doodle-giai-ma" / "FARMER.png").is_file()
    assert chars.lookup(qroot)["FARMER"].scope == "channel"


def test_char_rows_counts_uses_and_blocked(qroot, P):
    chars.set_chars(qroot, [FARMER])
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("@FARMER digging"), "verdict": "pass", "score": 8},
                            {"n": 2, "prompt": P("@FARMER and @MODERNYOU"), "verdict": "pass", "score": 8}])
    rows = {r["id"]: r for r in chars.char_rows(qroot)}
    assert rows["FARMER"]["uses"] == 2 and rows["FARMER"]["blocked"] == 2
    assert rows["MODERNYOU"]["uses"] == 1 and rows["MODERNYOU"]["scope"] == "channel"


def test_cli_chars_commands(qroot, tmp_path, img):
    f = tmp_path / "chars.json"
    f.write_text(json.dumps([FARMER]), encoding="utf-8")
    r = runner.invoke(app, ["quick", "set-chars", "-p", str(qroot), "--json", str(f)])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quick", "char-image", "-p", str(qroot), "FARMER", str(img())])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quick", "chars", "-p", str(qroot), "--json"])
    data = json.loads(r.output)
    assert {d["id"] for d in data} == {"MODERNYOU", "FARMER"}
    r = runner.invoke(app, ["quick", "char-image", "-p", str(qroot), "NOBODY", str(img())])
    assert r.exit_code == 1 and "Traceback" not in r.output


def test_promote_refuses_duplicate_in_channel(qroot, img, quick_presets):
    chars.set_chars(qroot, [FARMER])
    chars.set_char_image(qroot, "FARMER", img())
    preset = load_preset("doodle-giai-ma")
    preset.characters.append(Character(id="FARMER", desc="x"))
    save_preset(preset)
    with pytest.raises(VidflowError, match="đã có"):
        chars.promote(qroot, "FARMER")
    assert [c.id for c in load_quick(qroot).characters] == ["FARMER"]
    assert [c.id for c in load_preset("doodle-giai-ma").characters].count("FARMER") == 1
    assert (qroot / "refs" / "FARMER.png").is_file()
    assert not (quick_presets / "refs" / "doodle-giai-ma" / "FARMER.png").exists()


def _second_project(tmp_path):
    from vidflow.quick.model import create_quick, save_beats
    root = tmp_path / "vid2"
    create_quick(root, preset="doodle-giai-ma", title="T2")
    ops.set_beat_texts(root, ["A.", "B."])
    b = load_beats(root)
    for i, beat in enumerate(b.beats):
        beat.start, beat.end = i * 4.0, i * 4.0 + 4.0
    save_beats(root, b)
    return root


def test_promote_from_one_video_does_not_break_other(qroot, tmp_path, P):
    other = _second_project(tmp_path)
    for root in (qroot, other):
        chars.set_chars(root, [FARMER])
        ops.set_prompts(root, [{"n": 1, "prompt": P("@FARMER digging"), "verdict": "pass", "score": 8}])
    chars.promote(qroot, "FARMER")
    known = chars.lookup(other)
    assert known["FARMER"].scope == "channel"
    ops.status_summary(other)
    chars.set_chars(other, [])
    assert load_quick(other).characters == []


def test_set_chars_in_use_still_counts_when_channel_filtered_out(qroot, tmp_path, P):
    other = _second_project(tmp_path)
    for root in (qroot, other):
        chars.set_chars(root, [FARMER])
    ops.set_prompts(other, [{"n": 1, "prompt": P("@FARMER digging"), "verdict": "pass", "score": 8}])
    ops.update_settings(other, channel_chars=[])
    chars.promote(qroot, "FARMER")
    with pytest.raises(VidflowError, match="@FARMER"):
        chars.set_chars(other, [])


def test_narrowing_channel_chars_refuses_referenced(qroot, P):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("@MODERNYOU waking"), "verdict": "pass", "score": 8}])
    with pytest.raises(VidflowError, match="@MODERNYOU"):
        ops.update_settings(qroot, channel_chars=[])
    assert load_quick(qroot).channel_chars is None


def test_narrowing_channel_chars_refuses_clip_prompt_ref(qroot, P):
    from vidflow.quick import clips
    clips.set_clip_prompts(qroot, [{"n": 2, "prompt": "@MODERNYOU stretching", "verdict": "pass", "score": 8}])
    with pytest.raises(VidflowError, match="@MODERNYOU"):
        ops.update_settings(qroot, channel_chars=[])


def test_status_chars_missing_includes_unknown(qroot, P):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("@MODERNYOU waking"), "verdict": "pass", "score": 8}])
    b = load_beats(qroot)
    b.beats[1].refs = ["GHOST"]
    from vidflow.quick.model import save_beats
    save_beats(qroot, b)
    s = ops.status_summary(qroot)
    assert s["chars_missing"] == ["GHOST", "MODERNYOU"]
