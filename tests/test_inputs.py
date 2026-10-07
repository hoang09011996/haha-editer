import pytest

from vidflow.errors import ScriptError
from vidflow.inputs import compose_veo_prompt, scene_ref_images, tts_hash, video_hash


def test_compose_prompt_includes_style_character_and_mute(project):
    script = project.load_script()
    p = compose_veo_prompt(script, script.scene("s01"))
    assert p.startswith("Phong cách: cinematic, warm tone.")
    assert "an: cô gái 25 tuổi" in p
    assert "Close-up of a young woman sipping coffee." in p
    assert p.endswith("Không thoại, không lời dẫn, không nhạc.")


def test_compose_prompt_keeps_audio_when_enabled(project):
    script = project.load_script()
    scene = script.scene("s02").model_copy(update={"veo_audio": True})
    assert "Không thoại" not in compose_veo_prompt(script, scene)


def test_tts_hash_changes_with_text_and_voice(project, cfg):
    script = project.load_script()
    s = script.scene("s01")
    h1 = tts_hash(script, s, cfg)
    assert h1 == tts_hash(script, s, cfg)
    assert h1 != tts_hash(script, s.model_copy(update={"narration": "khác"}), cfg)
    other = script.model_copy(update={"voice": script.voice.model_copy(update={"name": "Puck"})})
    assert h1 != tts_hash(other, s, cfg)


def test_video_hash_changes_with_ref_image(project, cfg):
    script = project.load_script()
    s = script.scene("s01")
    h1 = video_hash(project, script, s, cfg)
    (project.refs_dir / "an.png").write_bytes(b"img1")
    h2 = video_hash(project, script, s, cfg)
    (project.refs_dir / "an.png").write_bytes(b"img2")
    h3 = video_hash(project, script, s, cfg)
    assert len({h1, h2, h3}) == 3


def test_too_many_ref_images(project):
    script = project.load_script()
    chars = [script.characters[0].model_copy(update={"id": f"c{i}"}) for i in range(4)]
    for c in chars:
        (project.refs_dir / f"{c.id}.png").write_bytes(b"x")
    script2 = script.model_copy(update={"characters": chars})
    scene = script.scene("s01").model_copy(update={"characters": [c.id for c in chars]})
    with pytest.raises(ScriptError, match="tối đa 3"):
        scene_ref_images(project, script2, scene)
