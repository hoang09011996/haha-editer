import pytest
from pydantic import ValidationError

from vidflow.errors import ScriptError
from vidflow.schema import Script


def base(**over):
    data = {"title": "T", "scenes": [{"id": "s01"}]}
    data.update(over)
    return data


def test_defaults():
    s = Script.model_validate(base())
    assert s.aspect == "9:16"
    assert s.voice.name == "Kore"
    assert s.scenes[0].duration == 8
    assert s.scenes[0].status == "draft"
    assert s.subtitles.max_chars_per_line == 32


def test_rejects_bad_duration():
    with pytest.raises(ValidationError):
        Script.model_validate(base(scenes=[{"id": "s01", "duration": 5}]))


def test_rejects_bad_aspect():
    with pytest.raises(ValidationError):
        Script.model_validate(base(aspect="4:3"))


def test_rejects_duplicate_scene_ids():
    with pytest.raises(ValidationError, match="trùng"):
        Script.model_validate(base(scenes=[{"id": "s01"}, {"id": "s01"}]))


def test_rejects_unknown_character():
    with pytest.raises(ValidationError, match="không tồn tại"):
        Script.model_validate(base(scenes=[{"id": "s01", "characters": ["bob"]}]))


def test_scene_lookup():
    s = Script.model_validate(base())
    assert s.scene("s01").id == "s01"
    with pytest.raises(ScriptError):
        s.scene("nope")


def test_flow_resolution_limited():
    with pytest.raises(ValidationError):
        Script.model_validate(base(flow={"resolution": "4k"}))
