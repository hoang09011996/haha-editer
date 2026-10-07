import json

import pytest

from vidflow.errors import VidflowError
from vidflow.quick.model import (Beat, Beats, Idea, QuickProject, create_quick, image_name, load_beats,
                                 load_quick, save_beats, save_quick)


@pytest.mark.parametrize("n,start,expected", [
    (1, 0.0, "001_00-00"),
    (29, 125.0, "029_02-05"),
    (29, 125.999, "029_02-05"),
    (112, 487.4, "112_08-07"),
    (5, 59.9999, "005_00-59"),
])
def test_image_name(n, start, expected):
    assert image_name(n, start) == expected


def test_quick_roundtrip(tmp_path):
    root = tmp_path / "q"
    q = create_quick(root, preset="doodle-giai-ma", title="Thử")
    assert (root / "quick.yaml").is_file()
    assert (root / "images").is_dir() and (root / "audio").is_dir()
    assert q.stage == "new" and q.picked is None
    q.ideas = [Idea(title="A", hook="h", why_viral="w")]
    q.picked = 1
    q.stage = "picked"
    save_quick(root, q)
    q2 = load_quick(root)
    assert q2 == q
    assert isinstance(q2, QuickProject)


def test_create_quick_refuses_existing(tmp_path):
    create_quick(tmp_path / "q", preset="x", title="T")
    with pytest.raises(VidflowError):
        create_quick(tmp_path / "q", preset="x", title="T")


def test_load_quick_missing(tmp_path):
    with pytest.raises(VidflowError, match="quick.yaml"):
        load_quick(tmp_path)


def test_beats_roundtrip_matches_spec_shape(tmp_path):
    b = Beats(aspect="16:9", beats=[Beat(n=1, start=0.0, end=2.31, text="Bạn bước vào bếp.", prompt="P",
                                         image="images/001_00-00.jpg",
                                         review={"verdict": "pass", "score": 8, "issues": []}, status="ok")])
    save_beats(tmp_path, b)
    raw = json.loads((tmp_path / "beats.json").read_text(encoding="utf-8"))
    assert raw == {"aspect": "16:9", "beats": [
        {"n": 1, "start": 0.0, "end": 2.31, "text": "Bạn bước vào bếp.", "prompt": "P",
         "image": "images/001_00-00.jpg", "review": {"verdict": "pass", "score": 8, "issues": []}, "status": "ok"}]}
    assert load_beats(tmp_path) == b


def test_load_beats_missing_returns_none(tmp_path):
    assert load_beats(tmp_path) is None
