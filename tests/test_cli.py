from typer.testing import CliRunner

from vidflow.cli import app

runner = CliRunner()


def test_new_then_validate(tmp_path):
    root = tmp_path / "p1"
    r = runner.invoke(app, ["new", str(root), "--title", "Thử", "--aspect", "16:9"])
    assert r.exit_code == 0, r.output
    assert (root / "script.yaml").is_file()
    r = runner.invoke(app, ["validate", "-p", str(root)])
    assert r.exit_code == 0, r.output
    assert "0 cảnh" in r.output


def test_validate_error_is_clean(tmp_path):
    root = tmp_path / "p2"
    runner.invoke(app, ["new", str(root), "--title", "X"])
    (root / "script.yaml").write_text("title: T\naspect: '4:3'\n", encoding="utf-8")
    r = runner.invoke(app, ["validate", "-p", str(root)])
    assert r.exit_code == 1
    assert "không hợp lệ" in r.output
    assert "Traceback" not in r.output


def test_import_command_name_and_usage_error(tmp_path):
    root = tmp_path / "p3"
    runner.invoke(app, ["new", str(root), "--title", "X"])
    r = runner.invoke(app, ["import", "-p", str(root)])
    assert r.exit_code == 1
    assert "vidflow import" in r.output


def test_mark_prompts_sets_fields_hash(tmp_path):
    import yaml
    from vidflow.inputs import scene_fields_hash
    from vidflow.project import Project
    root = tmp_path / "p4"
    runner.invoke(app, ["new", str(root), "--title", "X"])
    (root / "script.yaml").write_text('title: X\nscenes:\n  - {id: s01, action: "a", veo_prompt: "p"}\n  - {id: s02, veo_prompt: "q"}\n',
                                      encoding="utf-8")
    r = runner.invoke(app, ["mark-prompts", "-p", str(root), "-s", "s01"])
    assert r.exit_code == 0, r.output
    script = Project.open(root).load_script()
    assert script.scenes[0].prompt_fields_hash == scene_fields_hash(script, script.scenes[0])
    assert script.scenes[1].prompt_fields_hash == ""


def test_review_set_and_frames_cli(tmp_path):
    root = tmp_path / "p5"
    runner.invoke(app, ["new", str(root), "--title", "X"])
    (root / "script.yaml").write_text('title: X\nscenes:\n  - {id: s01, mode: comic, status: approved, frames: [{id: f01, prompt: "p", status: approved}]}\n',
                                      encoding="utf-8")
    r = runner.invoke(app, ["frames", "-p", str(root)])
    assert r.exit_code == 0 and "chưa kiểm duyệt" in r.output, r.output
    r = runner.invoke(app, ["review-set", "-p", str(root), "s01", "f01", "--verdict", "pass", "--score", "9"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["frames", "-p", str(root), "--json"])
    assert '"frame": "f01"' in r.output
    assert runner.invoke(app, ["review-set", "-p", str(root), "s01", "--verdict", "maybe"]).exit_code == 1
