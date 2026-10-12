import pytest

from vidflow.errors import VidflowError
from vidflow.quick.preset import (REPO, Preset, brief_path, import_preset, list_presets, load_preset)


def _sample_brief():
    for base in (REPO, REPO.parents[2]):  # worktree nằm trong <repo>/.claude/worktrees/<x>
        p = base / "samples" / "doodle-brief.txt"
        if p.is_file():
            return p
    return None


def test_doodle_preset_loads():
    p = load_preset("doodle-giai-ma")
    assert isinstance(p, Preset)
    assert p.id == "doodle-giai-ma"
    assert p.aspect == "16:9" and p.language == "vi"
    assert p.brief_file == "samples/doodle-brief.txt"
    assert p.style_anchor_start.startswith("Hand-drawn 2D doodle")
    assert p.style_anchor_end.endswith("doodle style.")
    assert p.voice.name
    assert "doodle-giai-ma" in [x.id for x in list_presets()]


def test_doodle_anchors_verbatim_in_brief():
    sample = _sample_brief()
    if sample is None:
        pytest.skip("Không có samples/doodle-brief.txt")
    text = sample.read_text(encoding="utf-8")
    p = load_preset("doodle-giai-ma")
    assert p.style_anchor_start in text
    assert p.style_anchor_end in text


def test_brief_path_resolves_relative_to_repo():
    p = load_preset("doodle-giai-ma")
    assert brief_path(p) == REPO / "samples" / "doodle-brief.txt"


def test_load_preset_unknown(tmp_path):
    with pytest.raises(VidflowError, match="nope"):
        load_preset("nope", presets_dir=tmp_path)


BRIEF = "Kênh X.\nMỗi prompt mở đầu: *\"Flat doodle, bold lines,\"*\nKết thúc: *\"no 3D, 16:9.\"*\n"


def _fake_extract(text: str) -> dict:
    assert "Kênh X" in text
    return {"name": "Kênh X", "aspect": "16:9", "language": "vi",
            "style_anchor_start": "Flat doodle, bold lines,", "style_anchor_end": "no 3D, 16:9.",
            "voice": {"name": "Charon", "style": "điềm tĩnh"}}


def test_import_txt(tmp_path):
    src = tmp_path / "brief.txt"
    src.write_text(BRIEF, encoding="utf-8")
    pdir = tmp_path / "presets"
    p = import_preset(src, preset_id="kenh-x", extract=_fake_extract, presets_dir=pdir)
    assert (pdir / "kenh-x.yaml").is_file()
    assert load_preset("kenh-x", presets_dir=pdir) == p
    assert brief_path(p).read_text(encoding="utf-8") == BRIEF


def test_import_rejects_non_verbatim_anchor(tmp_path):
    src = tmp_path / "brief.txt"
    src.write_text(BRIEF, encoding="utf-8")

    def bad(text):
        d = _fake_extract(text)
        d["style_anchor_start"] = "Flat doodles, bold lines,"
        return d

    with pytest.raises(VidflowError, match="nguyên văn"):
        import_preset(src, preset_id="kenh-x", extract=bad, presets_dir=tmp_path / "presets")


def test_import_refuses_overwrite(tmp_path):
    src = tmp_path / "brief.txt"
    src.write_text(BRIEF, encoding="utf-8")
    pdir = tmp_path / "presets"
    import_preset(src, preset_id="kenh-x", extract=_fake_extract, presets_dir=pdir)
    with pytest.raises(VidflowError, match="đã có"):
        import_preset(src, preset_id="kenh-x", extract=_fake_extract, presets_dir=pdir)
    import_preset(src, preset_id="kenh-x", extract=_fake_extract, presets_dir=pdir, force=True)


def test_import_docx_uses_converter(tmp_path):
    src = tmp_path / "brief.docx"
    src.write_bytes(b"PK fake docx")
    calls = []

    def conv(path):
        calls.append(path)
        return BRIEF

    pdir = tmp_path / "presets"
    p = import_preset(src, preset_id="kenh-x", extract=_fake_extract, presets_dir=pdir, docx_to_text=conv)
    assert calls == [src]
    assert brief_path(p).read_text(encoding="utf-8") == BRIEF
    assert brief_path(p).suffix == ".txt"


def test_preset_characters_and_channel_refs_dir(quick_presets):
    from vidflow.quick.preset import channel_refs_dir, load_preset
    p = load_preset("doodle-giai-ma")
    assert [c.id for c in p.characters] == ["MODERNYOU"]
    assert p.logo == ""
    assert channel_refs_dir(p) == quick_presets / "refs" / "doodle-giai-ma"


def test_real_preset_without_characters_loads():
    from vidflow.quick.preset import load_preset
    assert load_preset("doodle-giai-ma").characters == []
