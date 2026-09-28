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
