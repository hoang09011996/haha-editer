from vidflow.inputs import (compose_frame_prompt, compose_veo_prompt, frame_input_hash, prompt_text_hash,
                            review_ok, scene_fields_hash)
from vidflow.schema import Review, Script


def script(lang="vi", mode="slideshow"):
    return Script.model_validate({
        "title": "T", "style": "hoạt hình 3D ấm", "prompt_language": lang,
        "characters": [{"id": "tuan", "description": "nam 30 tuổi, kính tròn"}],
        "props": [{"id": "ly", "name": "Ly", "description": "ly cà phê sữa chua đá"}],
        "scenes": [{"id": "s01", "mode": mode, "characters": ["tuan"], "props": ["ly"], "veo_prompt": "Tuấn ngáp",
                    "frames": [{"id": "f01", "prompt": "Tuấn dụi mắt", "caption": "Ủa?"}]}],
    })


def test_veo_compose_vietnamese():
    s = script()
    p = compose_veo_prompt(s, s.scenes[0])
    assert p.startswith("Phong cách: hoạt hình 3D ấm.")
    assert "tuan: nam 30 tuổi, kính tròn." in p and "Ly: ly cà phê sữa chua đá." in p
    assert p.endswith("Không thoại, không lời dẫn, không nhạc.")


def test_veo_compose_english_unchanged():
    s = script("en")
    p = compose_veo_prompt(s, s.scenes[0])
    assert p.startswith("Style: hoạt hình 3D ấm.") and p.endswith("No dialogue, no narration, no music.")


def test_frame_compose():
    s = script(mode="comic")
    sc = s.scenes[0]
    p = compose_frame_prompt(s, sc, sc.frames[0])
    assert "Phong cách: hoạt hình 3D ấm." in p and "nam 30 tuổi" in p and "Tuấn dụi mắt" in p
    assert "Ảnh tĩnh" in p and "chừa khoảng trống phía trên" in p
    s2 = script(mode="slideshow")
    assert "chừa khoảng trống" not in compose_frame_prompt(s2, s2.scenes[0], s2.scenes[0].frames[0])


def test_review_ok():
    text = "abc"
    h = prompt_text_hash(text)
    assert review_ok(Review(verdict="pass", prompt_hash=h), text)
    assert review_ok(Review(verdict="override", prompt_hash=h), text)
    assert not review_ok(Review(verdict="fail", prompt_hash=h), text)
    assert not review_ok(Review(verdict="pass", prompt_hash=h), "abc sửa")
    assert not review_ok(None, text)


def test_frame_hash_changes(project, cfg):
    s = script()
    sc = s.scenes[0]
    h1 = frame_input_hash(project, s, sc, sc.frames[0])
    sc.frames[0].prompt = "khác"
    assert h1 != frame_input_hash(project, s, sc, sc.frames[0])


def test_fields_hash_ignores_frames_and_review():
    s = script()
    sc = s.scenes[0]
    h = scene_fields_hash(s, sc)
    sc.frames[0].prompt = "khác"; sc.review = Review(verdict="pass")
    assert h == scene_fields_hash(s, sc)
