from __future__ import annotations

import functools
from pathlib import Path
from typing import Annotated, Optional

import typer

from vidflow.config import load_config
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


TakesOpt = Annotated[int, typer.Option("--takes", help="Số bản gen mỗi cảnh")]
ForceOpt = Annotated[bool, typer.Option("--force", help="Chạy lại dù đã có kết quả")]


@command
def estimate(project: ProjectOpt, scene: ScenesOpt = None, takes: TakesOpt = 1, force: ForceOpt = False,
             config: ConfigOpt = None):
    """Ước tính số giây và chi phí Veo."""
    from vidflow.cost import plan_gen

    p = Project.open(project)
    script, state = p.load_script(), p.load_state()
    est = plan_gen(p, script, state, load_config(config), scene_ids=scene, takes=takes, force=force)
    for j in est.jobs:
        typer.echo(f"  gen {j.scene_id}: {j.seconds}s")
    for sid, why in est.skipped.items():
        typer.echo(f"  bỏ qua {sid}: {why}")
    typer.echo(f"Tổng: {est.seconds}s ≈ {est.usd:.2f} USD · đã tiêu {state.spent_usd:.2f}/{script.budget_usd:.2f} USD")
