import pytest
from pydantic import ValidationError

from vidflow.inputs import compose_veo_prompt, scene_fields_hash
from vidflow.schema import Script


def full():
    return {
        "title": "T",
        "profile": {"idea": "cà phê sáng", "style_type": "anim_3d", "platform": "tiktok"},
        "characters": [{"id": "tuan", "name": "Tuấn", "hair": "rẽ ngôi trái", "description": "cartoon man"}],
        "locations": [{"id": "bep", "name": "Bếp", "time_of_day": "7h sáng"}],
        "props": [{"id": "ly", "name": "Ly cà phê sữa chua", "description": "tall glass of iced coffee with yogurt"}],
        "scenes": [{"id": "s01", "characters": ["tuan"], "location": "bep", "props": ["ly"],
                    "action": "nhấp một ngụm", "anti_ai": ["film_grain"], "avoid": ["no text"],
                    "veo_prompt": "Close-up."}],
    }


def test_full_schema_parses_with_defaults():
    s = Script.model_validate(full())
    assert s.profile.style_type == "anim_3d"
    assert s.locations[0].name == "Bếp"
    assert s.scenes[0].location == "bep" and s.scenes[0].props == ["ly"]
    assert s.scenes[0].locked is False and s.scenes[0].prompt_fields_hash == ""
    assert Script.model_validate({"title": "x"}).profile.style_type == "anim_3d"


def test_unknown_location_or_prop_rejected():
    d = full(); d["scenes"][0]["location"] = "nope"
    with pytest.raises(ValidationError, match="bối cảnh không tồn tại"):
        Script.model_validate(d)
    d = full(); d["scenes"][0]["props"] = ["nope"]
    with pytest.raises(ValidationError, match="đạo cụ không tồn tại"):
        Script.model_validate(d)


def test_prompt_includes_prop_description():
    s = Script.model_validate(full())
    assert "tall glass of iced coffee with yogurt" in compose_veo_prompt(s, s.scenes[0])


def test_fields_hash_tracks_detail_fields_not_prompt():
    s = Script.model_validate(full())
    sc = s.scenes[0]
    h = scene_fields_hash(s, sc)
    assert h == scene_fields_hash(s, sc.model_copy(update={"veo_prompt": "other", "veo_prompt_vi": "khác"}))
    assert h != scene_fields_hash(s, sc.model_copy(update={"action": "đổ cà phê"}))
    s2 = s.model_copy(update={"props": [s.props[0].model_copy(update={"description": "mug"})]})
    assert h != scene_fields_hash(s2, sc)
