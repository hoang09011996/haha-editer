import pytest

from vidflow.errors import ScriptError
from vidflow.project import Project, create_project
from vidflow.state import ProjectState, Take


def test_create_project_layout(tmp_path):
    p = create_project(tmp_path / "x", title='Tựa "đẹp"', aspect="16:9")
    for d in ("audio", "clips", "refs", "music", "logs"):
        assert (p.root / d).is_dir()
    s = p.load_script()
    assert s.title == 'Tựa "đẹp"'
    assert s.aspect == "16:9"
    assert s.scenes == []


def test_create_refuses_existing(project):
    with pytest.raises(ScriptError, match="đã có"):
        create_project(project.root, title="A", aspect="9:16")


def test_create_rejects_bad_aspect(tmp_path):
    with pytest.raises(ScriptError, match="aspect"):
        create_project(tmp_path / "y", title="A", aspect="1:1")


def test_open_missing(tmp_path):
    with pytest.raises(ScriptError, match="vidflow new"):
        Project.open(tmp_path / "none")


def test_invalid_yaml_reports(project):
    project.script_path.write_text("title: [unclosed", encoding="utf-8")
    with pytest.raises(ScriptError, match="YAML"):
        project.load_script()


def test_invalid_schema_reports(project):
    project.script_path.write_text("title: T\naspect: '4:3'\n", encoding="utf-8")
    with pytest.raises(ScriptError, match="không hợp lệ"):
        project.load_script()


def test_state_roundtrip(project):
    st = project.load_state()
    assert st == ProjectState()
    st.scene("s01").takes.append(Take(file="clips/s01_t1.mp4", input_hash="h", cost_usd=4.0, created_at="t"))
    st.spent_usd = 4.0
    project.save_state(st)
    again = project.load_state()
    assert again.scenes["s01"].takes[0].file == "clips/s01_t1.mp4"
    assert again.spent_usd == 4.0
    assert not list(project.root.glob("*.tmp"))


def test_ref_image_lookup(project):
    script = project.load_script()
    an = script.character("an")
    assert project.ref_image(an) is None
    (project.refs_dir / "an.jpg").write_bytes(b"\xff\xd8\xff")
    assert project.ref_image(an) == project.refs_dir / "an.jpg"


def test_explicit_ref_image_missing(project):
    script = project.load_script()
    an = script.character("an").model_copy(update={"ref_image": "refs/missing.png"})
    with pytest.raises(ScriptError, match="missing.png"):
        project.ref_image(an)
