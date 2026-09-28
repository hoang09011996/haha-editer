from __future__ import annotations

import functools
from pathlib import Path
from typing import Annotated, Optional

import typer

from vidflow.errors import VidflowError
from vidflow.project import Project, create_project

app = typer.Typer(no_args_is_help=True, help="vidflow: kịch bản → Veo/TTS → draft CapCut")

ProjectOpt = Annotated[Path, typer.Option("--project", "-p", help="Thư mục project")]
ScenesOpt = Annotated[Optional[list[str]], typer.Option("--scene", "-s", help="Chỉ xử lý cảnh này (lặp được)")]
ConfigOpt = Annotated[Optional[Path], typer.Option("--config", help="Đường dẫn vidflow.toml")]


def command(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except VidflowError as e:
            typer.secho(str(e), fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

    return app.command()(wrapper)


@command
def new(
    root: Annotated[Path, typer.Argument(help="Thư mục project mới")],
    title: Annotated[str, typer.Option(help="Tựa video")],
    aspect: Annotated[str, typer.Option(help="9:16 hoặc 16:9")] = "9:16",
):
    """Tạo project mới với script.yaml mẫu."""
    p = create_project(root, title=title, aspect=aspect)
    typer.echo(f"Đã tạo {p.script_path}")


@command
def validate(project: ProjectOpt):
    """Kiểm tra script.yaml."""
    script = Project.open(project).load_script()
    approved = sum(1 for s in script.scenes if s.status == "approved")
    typer.echo(f"OK: {len(script.scenes)} cảnh ({approved} approved), tỉ lệ {script.aspect}")
