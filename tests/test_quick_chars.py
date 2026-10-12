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
