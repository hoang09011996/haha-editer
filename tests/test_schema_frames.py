import pytest
from pydantic import ValidationError

from vidflow.schema import Script
from vidflow.state import ProjectState


def sc(**kw):
    d = {"id": "s01"}
    d.update(kw)
    return {"title": "T", "scenes": [d]}


def test_defaults():
    s = Script.model_validate(sc())
    assert s.prompt_language == "vi"
    x = s.scenes[0]
    assert x.mode == "veo" and x.fps == 8 and x.transition == "fade" and x.frames == []


def test_frames_parse():
    s = Script.model_validate(sc(mode="slideshow", frames=[{"id": "f01", "description": "Tuấn ngáp"}, {"id": "f02"}]))
    f = s.scenes[0].frame("f02")
    assert f.seconds == 2.0 and f.motion == "zoom_in" and f.status == "draft" and f.review is None


def test_duplicate_frame_id():
    with pytest.raises(ValidationError, match="khung trùng"):
        Script.model_validate(sc(mode="comic", frames=[{"id": "f01"}, {"id": "f01"}]))


def test_approved_image_scene_needs_frames():
    with pytest.raises(ValidationError, match="cần ít nhất 1 khung"):
        Script.model_validate(sc(mode="slideshow", status="approved"))
    Script.model_validate(sc(mode="slideshow"))  # draft thì được


@pytest.mark.parametrize("bad", [{"fps": 5}, {"fps": 13}])
def test_fps_range(bad):
    with pytest.raises(ValidationError):
        Script.model_validate(sc(mode="stopmotion", **bad))


def test_seconds_range_and_max_frames():
    with pytest.raises(ValidationError):
        Script.model_validate(sc(mode="slideshow", frames=[{"id": "f01", "seconds": 0.2}]))
    with pytest.raises(ValidationError, match="tối đa 60"):
        Script.model_validate(sc(mode="stopmotion", frames=[{"id": f"f{i:02d}"} for i in range(61)]))


def test_state_frames():
    st = ProjectState()
    fs = st.scene("s01").frame("f01")
    assert fs.images == [] and fs.picked is None
    assert st.scenes["s01"].frames["f01"] is fs
