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


def command(fn=None, *, name: str | None = None):
    def register(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except VidflowError as e:
                typer.secho(str(e), fg=typer.colors.RED, err=True)
                raise typer.Exit(1)

        return app.command(name)(wrapper)

    return register(fn) if fn else register


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


@command
def tts(project: ProjectOpt, scene: ScenesOpt = None, force: ForceOpt = False, config: ConfigOpt = None):
    """Tạo voice-over bằng Gemini TTS."""
    from vidflow.gemini import GeminiSpeechClient
    from vidflow.inputs import MIN_CLIP_SPEED, SCENE_PAD_S
    from vidflow.tts import run_tts

    p = Project.open(project)
    done = run_tts(p, load_config(config), GeminiSpeechClient(), scene_ids=scene, force=force)
    script, state = p.load_script(), p.load_state()
    for s in script.scenes:
        t = state.scenes.get(s.id)
        if not t or not t.tts:
            continue
        need = t.tts.duration_s / script.voice.speed + SCENE_PAD_S
        mark = "mới" if s.id in done else "giữ"
        warn = f"  ⚠ dài hơn clip {s.duration}s có thể kéo (tối đa {s.duration / MIN_CLIP_SPEED:.1f}s)" \
            if need > s.duration / MIN_CLIP_SPEED else ""
        typer.echo(f"  {s.id} [{mark}] {t.tts.file} {t.tts.duration_s:.2f}s{warn}")


@command
def gen(project: ProjectOpt, scene: ScenesOpt = None, takes: TakesOpt = 1, force: ForceOpt = False,
        yes: Annotated[bool, typer.Option("--yes", help="Không hỏi xác nhận chi phí")] = False,
        config: ConfigOpt = None):
    """Gen clip Veo cho các cảnh approved (hỏi xác nhận chi phí trước)."""
    from vidflow.cost import check_budget, plan_gen
    from vidflow.gemini import GeminiVideoClient
    from vidflow.video import run_gen

    p = Project.open(project)
    cfg = load_config(config)
    script, state = p.load_script(), p.load_state()
    est = plan_gen(p, script, state, cfg, scene_ids=scene, takes=takes, force=force)
    check_budget(script, state, est)
    typer.echo(f"Sẽ gen {len(est.jobs)} clip, {est.seconds}s ≈ {est.usd:.2f} USD")
    if est.jobs and not yes and not typer.confirm("Tiếp tục?"):
        raise typer.Exit(0)
    rep = run_gen(p, cfg, GeminiVideoClient(), scene_ids=scene, takes=takes, force=force)
    for f in rep.created:
        typer.echo(f"  ✓ {f}")
    for sid, err in rep.failed.items():
        typer.secho(f"  ✗ {sid}: {err}", fg=typer.colors.YELLOW)
    typer.echo(f"Đã tiêu: {p.load_state().spent_usd:.2f}/{script.budget_usd:.2f} USD")


@command
def pick(project: ProjectOpt, scene_id: Annotated[str, typer.Argument()], take: Annotated[int, typer.Argument()]):
    """Chọn take (đánh số từ 1) dùng cho cảnh."""
    from vidflow.video import pick_take

    typer.echo(f"{scene_id} dùng {pick_take(Project.open(project), scene_id, take)}")


@command
def refimg(project: ProjectOpt,
           character: Annotated[Optional[list[str]], typer.Option("--character", "-c")] = None,
           force: ForceOpt = False, config: ConfigOpt = None):
    """Tạo ảnh tham chiếu nhân vật vào refs/."""
    from vidflow.gemini import GeminiImageClient
    from vidflow.refimg import run_refimg

    p = Project.open(project)
    for f in run_refimg(p, load_config(config), GeminiImageClient(), character_ids=character, force=force):
        typer.echo(f"  ✓ {f}")
    for c in p.load_script().characters:
        if c.ref_image:
            typer.echo(f"  {c.id}: đang dùng ảnh chỉ định {c.ref_image} (xóa ref_image để dùng ảnh trong refs/)")


@command
def preview(project: ProjectOpt):
    """Sinh preview.html để xem toàn bộ cảnh."""
    from vidflow.preview import render_preview

    p = Project.open(project)
    typer.echo(f"Mở: {render_preview(p, p.load_script(), p.load_state())}")


@command
def status(project: ProjectOpt, config: ConfigOpt = None):
    """Trạng thái từng cảnh và chi phí."""
    from vidflow.status import scene_rows

    p = Project.open(project)
    script, state = p.load_script(), p.load_state()
    cols = ["id", "status", "tts", "takes", "picked", "clip", "pending", "error"]
    typer.echo("  ".join(f"{c:<9}" for c in cols))
    for r in scene_rows(p, script, state, load_config(config)):
        typer.echo("  ".join(f"{r[c]:<9}" for c in cols))
    typer.echo(f"Đã tiêu {state.spent_usd:.2f}/{script.budget_usd:.2f} USD · draft: {state.draft_path or '-'}")


@command
def build(project: ProjectOpt, config: ConfigOpt = None):
    """Dựng draft CapCut Desktop từ clip đã chọn, voice-over, phụ đề, nhạc."""
    from vidflow.capcut_draft import build_draft
    from vidflow.media import video_duration
    from vidflow.timeline import plan_timeline

    p = Project.open(project)
    cfg = load_config(config)
    script, state = p.load_script(), p.load_state()
    clips = {st.takes[st.picked].file for st in state.scenes.values() if st.picked is not None}
    tl = plan_timeline(script, state, {c: video_duration(p.path(c)) for c in clips})
    for sid, why in tl.skipped.items():
        typer.secho(f"  bỏ qua {sid}: {why}", fg=typer.colors.YELLOW)
    path = build_draft(p, cfg, script, tl)
    typer.echo(f"Đã dựng {len(tl.scenes)} cảnh, {tl.total:.1f}s → {path}. Mở CapCut để xem.")


@command
def prompts(project: ProjectOpt, json_out: Annotated[bool, typer.Option("--json", help="In JSON cho agent")] = False,
            config: ConfigOpt = None):
    """Xuất prompt các cảnh cần gen để làm trong Google Flow (ghi prompts.md)."""
    import json

    from vidflow.frames import veo_blocked
    from vidflow.manual import pending_prompts, write_prompts_md

    p = Project.open(project)
    items = pending_prompts(p, load_config(config))
    out = write_prompts_md(p, items)
    for b in veo_blocked(p):
        typer.secho(f"  ⛔ {b['scene']}: {b['reason']}", fg=typer.colors.YELLOW, err=json_out)
    if json_out:
        typer.echo(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        for i in items:
            typer.echo(f"  {i['id']} · {i['aspect']} · {i['duration']}s · {len(i['ref_images'])} ảnh tham chiếu")
        typer.echo(f"{len(items)} cảnh cần gen · chi tiết: {out}")


@command(name="import")
def import_(project: ProjectOpt,
            scene_id: Annotated[Optional[str], typer.Argument(help="Cảnh nhận clip")] = None,
            file: Annotated[Optional[Path], typer.Argument(help="File video đã tải từ Flow")] = None,
            inbox: Annotated[bool, typer.Option("--inbox", help="Nhập mọi file <scene>*.mp4 trong inbox/")] = False,
            config: ConfigOpt = None):
    """Nhập clip gen ngoài API (Google Flow) làm take của cảnh."""
    from vidflow.manual import import_clip, import_inbox

    p = Project.open(project)
    cfg = load_config(config)
    if inbox:
        imported, unmatched = import_inbox(p, cfg)
        for name, rel in imported.items():
            typer.echo(f"  ✓ {name} → {rel}")
        for name in unmatched:
            typer.secho(f"  ? {name}: tên file không bắt đầu bằng id cảnh", fg=typer.colors.YELLOW)
        return
    if not scene_id or not file:
        raise VidflowError("Dùng: vidflow import -p <project> <scene> <file.mp4>  hoặc  --inbox")
    typer.echo(f"  ✓ {scene_id} ← {import_clip(p, cfg, scene_id, file)}")


@command(name="mark-prompts")
def mark_prompts(project: ProjectOpt, scene: ScenesOpt = None):
    """Đánh dấu veo_prompt đã viết khớp các ô chi tiết hiện tại (agent chạy sau khi viết prompt)."""
    from vidflow.inputs import scene_fields_hash

    p = Project.open(project)
    script = p.load_script()
    targets = scene or [s.id for s in script.scenes if s.veo_prompt.strip()]
    for sid in targets:
        sc = script.scene(sid)
        sc.prompt_fields_hash = scene_fields_hash(script, sc)
    p.save_script(script)
    typer.echo(f"Đã đánh dấu {len(targets)} cảnh: {', '.join(targets)}")


PASSWORD_FILE = Path.home() / ".vidflow" / "ui_password"


def ui_password(create: bool) -> str | None:
    """Mật khẩu UI: biến môi trường VIDFLOW_UI_PASSWORD, hoặc file ~/.vidflow/ui_password (chmod 600)."""
    import os
    import secrets

    if os.environ.get("VIDFLOW_UI_PASSWORD"):
        return os.environ["VIDFLOW_UI_PASSWORD"]
    if PASSWORD_FILE.is_file():
        return PASSWORD_FILE.read_text(encoding="utf-8").strip() or None
    if not create:
        return None
    PASSWORD_FILE.parent.mkdir(mode=0o700, exist_ok=True)
    pw = secrets.token_urlsafe(12)
    PASSWORD_FILE.write_text(pw, encoding="utf-8")
    PASSWORD_FILE.chmod(0o600)
    return pw


@command
def ui(projects: Annotated[Path, typer.Option("--projects", help="Thư mục chứa các project")] = Path("projects"),
       port: Annotated[int, typer.Option(help="Cổng web")] = 8777, config: ConfigOpt = None,
       open_browser: Annotated[bool, typer.Option("--open/--no-open", help="Tự mở trình duyệt")] = True,
       auth: Annotated[bool, typer.Option("--auth/--no-auth", help="Bắt đăng nhập (mặc định bật; chỉ tắt khi không mở ra internet)")] = True):
    """Mở giao diện web cục bộ (http://127.0.0.1:<port>)."""
    import threading
    import webbrowser

    from vidflow.ui.server import serve

    password = ui_password(create=True) if auth else None
    url = f"http://127.0.0.1:{port}"
    typer.echo(f"vidflow UI: {url}  (Ctrl+C để dừng)")
    if password:
        typer.echo(f"Đăng nhập bằng mật khẩu trong {PASSWORD_FILE} (hoặc biến VIDFLOW_UI_PASSWORD).")
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    serve(projects, port=port, config_path=config, password=password)


@command
def frames(project: ProjectOpt, json_out: Annotated[bool, typer.Option("--json", help="In JSON cho agent")] = False,
           config: ConfigOpt = None):
    """Liệt kê khung ảnh cần gen trong Google Flow (đã duyệt, đã qua kiểm duyệt, chưa có ảnh khớp prompt)."""
    import json

    from vidflow.frames import pending_frames

    items, blocked = pending_frames(Project.open(project), load_config(config))
    if json_out:
        typer.echo(json.dumps({"frames": items, "blocked": blocked}, ensure_ascii=False, indent=2))
        return
    for i in items:
        typer.echo(f"  {i['scene']}/{i['frame']} · {i['mode']} · {i['aspect']}")
    for b in blocked:
        typer.secho(f"  ⛔ {b['scene']}/{b['frame']}: {b['reason']}", fg=typer.colors.YELLOW)
    typer.echo(f"{len(items)} khung cần gen, {len(blocked)} khung bị chặn")


@command(name="import-frame")
def import_frame_cmd(project: ProjectOpt, scene_id: Annotated[str, typer.Argument()], frame_id: Annotated[str, typer.Argument()],
                     file: Annotated[Path, typer.Argument(help="Ảnh png/jpg/webp tải từ Flow")], config: ConfigOpt = None):
    """Nhập ảnh tải từ Flow làm bản của khung."""
    from vidflow.frames import import_frame

    typer.echo(f"  ✓ {scene_id}/{frame_id} ← {import_frame(Project.open(project), load_config(config), scene_id, frame_id, file)}")


@command(name="pick-frame")
def pick_frame_cmd(project: ProjectOpt, scene_id: Annotated[str, typer.Argument()], frame_id: Annotated[str, typer.Argument()],
                   n: Annotated[int, typer.Argument(help="Bản số (từ 1)")]):
    """Chọn bản ảnh dùng cho khung."""
    from vidflow.frames import pick_frame

    typer.echo(f"{scene_id}/{frame_id} dùng {pick_frame(Project.open(project), scene_id, frame_id, n)}")


@command(name="review-set")
def review_set(project: ProjectOpt, scene_id: Annotated[str, typer.Argument()],
               frame_id: Annotated[Optional[str], typer.Argument(help="Bỏ trống = prompt veo của cảnh")] = None,
               verdict: Annotated[str, typer.Option(help="pass | fail | override")] = "pass",
               score: Annotated[float, typer.Option(help="Điểm 0–10")] = 0,
               issue: Annotated[Optional[list[str]], typer.Option("--issue", help="Vấn đề (lặp được)")] = None,
               suggestion: Annotated[str, typer.Option(help="Gợi ý sửa")] = ""):
    """Ghi kết quả kiểm duyệt cho prompt hiện tại (agent prompt-reviewer dùng)."""
    from vidflow.frames import set_review

    if verdict not in ("pass", "fail", "override"):
        raise VidflowError("verdict phải là pass, fail hoặc override")
    set_review(Project.open(project), scene_id, frame_id, verdict=verdict, score=score, issues=issue or [], suggestion=suggestion)
    typer.echo(f"Đã ghi kiểm duyệt {scene_id}{'/' + frame_id if frame_id else ''}: {verdict} ({score:g}/10)")


@command
def render(project: ProjectOpt, scene: ScenesOpt = None, config: ConfigOpt = None):
    """Ghép ảnh đã chọn của cảnh slideshow/stopmotion/comic thành clip (ffmpeg)."""
    from vidflow.render import run_render

    rep = run_render(Project.open(project), load_config(config), scene_ids=scene)
    for f in rep["created"]:
        typer.echo(f"  ✓ {f}")
    for sid, why in rep["skipped"].items():
        typer.secho(f"  bỏ qua {sid}: {why}", fg=typer.colors.YELLOW)
    if not rep["created"] and not rep["skipped"]:
        typer.echo("Không có cảnh ảnh nào cần render lại.")


@command
def assemble(images: Annotated[Path, typer.Option("--images", help="Thư mục ảnh NNN_MM-SS.jpg")],
             audio: Annotated[Optional[Path], typer.Option("--audio", help="File giọng đọc (wav/mp3)")] = None,
             beats: Annotated[Optional[Path], typer.Option("--beats", help="beats.json (mốc ms + phụ đề)")] = None,
             name: Annotated[Optional[str], typer.Option("--name", help="Tên draft CapCut")] = None,
             aspect: Annotated[str, typer.Option("--aspect", help="auto | 16:9 | 9:16")] = "auto",
             zoom: Annotated[bool, typer.Option("--zoom/--no-zoom", help="Zoom nhẹ xen kẽ")] = True,
             subtitles: Annotated[bool, typer.Option("--subtitles/--no-subtitles", help="Phụ đề từ beats.json")] = True,
             config: ConfigOpt = None):
    """Dựng draft CapCut thẳng từ thư mục ảnh NNN_MM-SS (+ voice, + beats.json)."""
    import time

    from vidflow.assemble import assemble as run_assemble

    t0 = time.perf_counter()
    rep = run_assemble(images, audio=audio, beats=beats, name=name, aspect=aspect, zoom=zoom, subtitles=subtitles,
                       cfg=load_config(config))
    for f in rep.skipped_files:
        typer.secho(f"  bỏ qua {f}: tên không đúng mẫu NNN_MM-SS", fg=typer.colors.YELLOW)
    for w in rep.warnings:
        typer.secho(f"  ! {w}", fg=typer.colors.YELLOW)
    typer.echo(f"Đã dựng {rep.count} ảnh, {rep.total_s:.1f}s trong {time.perf_counter() - t0:.1f}s → {rep.draft_dir}. "
               "Mở CapCut để xem.")
