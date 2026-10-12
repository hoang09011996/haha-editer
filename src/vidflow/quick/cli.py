"""`vidflow quick ...` và `vidflow preset ...`."""
from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from vidflow.config import load_config
from vidflow.errors import VidflowError
from vidflow.quick import chars, clips, jobs, ops
from vidflow.quick.model import create_quick, load_quick, require_beats
from vidflow.quick.preset import import_preset, list_presets, load_preset

quick_app = typer.Typer(no_args_is_help=True, help="Quy trình nhanh: ý tưởng → mốc → giọng → ảnh Flow → CapCut")
preset_app = typer.Typer(no_args_is_help=True, help="Bộ kênh (brief + câu neo + giọng)")

ProjectOpt = Annotated[Path, typer.Option("--project", "-p", help="Thư mục project nhanh")]
ClipOpt = Annotated[bool, typer.Option("--clip", help="Áp dụng cho prompt/clip động thay vì ảnh")]
ConfigOpt = Annotated[Optional[Path], typer.Option("--config", help="Đường dẫn vidflow.toml")]
JsonFile = Annotated[Path, typer.Option("--json", help="File JSON đầu vào")]
PrintOpt = Annotated[bool, typer.Option("--print", help="Chỉ in lệnh giao cho Claude, không chạy")]


def _cmd(app: typer.Typer, name: str | None = None):
    def register(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except VidflowError as e:
                typer.secho(str(e), fg=typer.colors.RED, err=True)
                raise typer.Exit(1)

        return app.command(name)(wrapper)

    return register


def _read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise VidflowError(f"Không thấy {path}") from e
    except json.JSONDecodeError as e:
        raise VidflowError(f"{path}: JSON sai: {e}") from e


def project_root(name: str) -> Path:
    p = Path(name).expanduser()
    return p if p.is_absolute() or len(p.parts) > 1 else Path("projects") / p


# ---- project ----

@_cmd(quick_app, "new")
def new(name: Annotated[str, typer.Argument(help="Tên project (tạo trong projects/) hoặc đường dẫn")],
        preset: Annotated[str, typer.Option(help="id bộ kênh trong presets/")],
        title: Annotated[str, typer.Option(help="Tựa tạm")] = ""):
    """Tạo project nhanh."""
    load_preset(preset)
    root = project_root(name)
    create_quick(root, preset=preset, title=title)
    typer.echo(f"Đã tạo {root}/quick.yaml (bộ kênh {preset})")


def _claude(kind: str, project: Path, print_only: bool):
    q = load_quick(project)
    if kind == "script" and not q.picked_idea():
        raise VidflowError("Chưa chọn ý tưởng — `vidflow quick pick -p ... <n>`.")
    if kind in ("prompts", "flow", "clips"):
        require_beats(project)
    preset = load_preset(q.preset)
    if print_only:
        typer.echo(jobs.claude_task(kind, project, preset))
        return
    typer.echo(f"{jobs.LABELS[kind]}…")
    rc = jobs.run_claude(kind, project, preset)
    if rc:
        raise VidflowError(f"Job Claude '{kind}' lỗi (mã {rc}).")
    typer.echo(ops.format_status(ops.status_summary(project)))


@_cmd(quick_app, "ideas")
def ideas(project: ProjectOpt, print_only: PrintOpt = False):
    """Claude đề xuất 5 ý tưởng (ghi quick.yaml)."""
    _claude("ideas", project, print_only)


@_cmd(quick_app, "script")
def script(project: ProjectOpt, print_only: PrintOpt = False):
    """Claude viết kịch bản và tách mốc (ghi beats.json)."""
    _claude("script", project, print_only)


@_cmd(quick_app, "prompts")
def prompts(project: ProjectOpt, print_only: PrintOpt = False):
    """Claude viết + tự kiểm duyệt prompt ảnh từng mốc."""
    _claude("prompts", project, print_only)


@_cmd(quick_app, "flow")
def flow(project: ProjectOpt, print_only: PrintOpt = False):
    """Gen ảnh mốc pending/redo trong Google Flow (claude --chrome)."""
    _claude("flow", project, print_only)


@_cmd(quick_app, "sheets")
def sheets(project: ProjectOpt, print_only: PrintOpt = False):
    """Gen character sheet còn thiếu trong Google Flow (claude --chrome)."""
    _claude("sheets", project, print_only)


@_cmd(quick_app, "clips")
def clips_flow(project: ProjectOpt, print_only: PrintOpt = False):
    """Gen clip động trong Google Flow (claude --chrome)."""
    _claude("clips", project, print_only)


@_cmd(quick_app, "review")
def review(project: ProjectOpt, n: Annotated[int, typer.Argument()], clip: ClipOpt = False,
           print_only: PrintOpt = False):
    """Kiểm duyệt độc lập prompt ảnh/clip của một mốc."""
    import subprocess

    from vidflow.quick.preset import REPO

    preset = load_preset(load_quick(project).preset)
    if print_only:
        typer.echo(jobs.review_task(project, preset, n, clip=clip))
        return
    rc = subprocess.run(jobs.review_cmd(project, preset, n, clip=clip), cwd=REPO, stdin=subprocess.DEVNULL).returncode
    if rc:
        raise VidflowError(f"Kiểm duyệt mốc {n} lỗi (mã {rc}).")


@_cmd(quick_app, "pick")
def pick(project: ProjectOpt, n: Annotated[int, typer.Argument(help="Số ý tưởng (1-based)")]):
    """Chọn ý tưởng."""
    q = ops.pick_idea(project, n)
    typer.echo(f"Đã chọn #{n}: {q.title}")


@_cmd(quick_app, "voice")
def voice(project: ProjectOpt, config: ConfigOpt = None):
    """TTS từng mốc (Gemini free tier), ghép audio/voice.wav, điền mốc thời gian."""
    from vidflow.quick.voice import gemini_voice

    secs = gemini_voice(project, load_config(config), on_progress=lambda d, t: typer.echo(f"  đọc {d}/{t}"))
    m, s = divmod(secs, 60)
    typer.echo(f"Đã ghép audio/voice.wav: {int(m)}:{s:05.2f}")


@_cmd(quick_app, "redo")
def redo(project: ProjectOpt, n: Annotated[list[int], typer.Argument(help="Các mốc cần gen lại")],
         clip: Annotated[bool, typer.Option("--clip", help="Gen lại clip thay vì ảnh")] = False):
    """Đánh dấu mốc cần gen lại ảnh (hoặc clip)."""
    ops.mark_redo(project, n, clip=clip)
    typer.echo(f"Đã đánh dấu gen lại {'clip' if clip else 'ảnh'}: {', '.join(map(str, n))}")


@_cmd(quick_app, "status")
def status(project: ProjectOpt, json_out: Annotated[bool, typer.Option("--json")] = False):
    """Tóm tắt tiến độ."""
    s = ops.status_summary(project)
    typer.echo(json.dumps(s, ensure_ascii=False, indent=1) if json_out else ops.format_status(s))


@_cmd(quick_app, "beats")
def beats(project: ProjectOpt, json_out: Annotated[bool, typer.Option("--json")] = False,
          todo: Annotated[bool, typer.Option("--todo", help="Chỉ mốc cần gen ảnh")] = False,
          todo_clips: Annotated[bool, typer.Option("--todo-clips", help="Chỉ clip cần gen")] = False):
    """Liệt kê mốc (agent dùng --json)."""
    if todo_clips:
        data = clips.clip_todo(project)
        if json_out:
            typer.echo(json.dumps(data, ensure_ascii=False, indent=1))
        else:
            for c in data["clips"]:
                typer.echo(f"{c['n']:03d} {c['duration']:.1f}s {c['prompt'][:60]}")
        return
    data = ops.list_beats(project, todo=todo)
    if json_out:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=1))
        return
    for b in data["beats"]:
        t = "--:--" if b["start"] is None else f"{int(b['start'] // 60):02d}:{int(b['start'] % 60):02d}"
        v = b["review"]["verdict"] if b["review"] else "-"
        typer.echo(f"{b['n']:03d} [{t}] {b['status']:<7} {v:<5} {b['text'][:60]}")
    for x in data.get("blocked", []):
        typer.echo(f"{x['n']:03d} BỊ CHẶN: {x['reason']}")


@_cmd(quick_app, "settings")
def settings(project: ProjectOpt,
             image_model: Annotated[Optional[str], typer.Option(help="Model ảnh Flow")] = None,
             video_model: Annotated[Optional[str], typer.Option(help="Model clip Flow, ví dụ \"Veo 3.1 Lite\"")] = None,
             resolution: Annotated[Optional[str], typer.Option(help="720p | 1080p")] = None,
             max_clips: Annotated[Optional[int], typer.Option(help="Số clip tối đa (0 = chỉ ảnh)")] = None,
             allow_cont: Annotated[Optional[bool], typer.Option("--allow-cont/--no-allow-cont")] = None,
             channel_char: Annotated[Optional[list[str]], typer.Option("--channel-char", help="Nhân vật bộ kênh dùng (lặp được)")] = None):
    """Cài đặt Flow, giới hạn clip, nối cảnh, nhân vật bộ kênh."""
    q = ops.update_settings(project, image_model=image_model, video_model=video_model, resolution=resolution,
                            max_clips=max_clips, allow_cont=allow_cont, channel_chars=channel_char)
    typer.echo(f"Ảnh: {q.flow.image_model} · clip: {q.flow.video_model or '(chưa chọn)'} {q.flow.resolution} · "
               f"tối đa {q.max_clips} clip · nối cảnh: {'bật' if q.allow_cont else 'tắt'}")


@_cmd(quick_app, "clip")
def clip_toggle(project: ProjectOpt, action: Annotated[str, typer.Argument(help="on | off")],
                n: Annotated[list[int], typer.Argument(help="Các mốc")]):
    """Bật/tắt clip động cho mốc."""
    if action not in ("on", "off"):
        raise VidflowError("Dùng `clip on <n...>` hoặc `clip off <n...>`.")
    clips.set_clip_enabled(project, n, action == "on")
    typer.echo(f"Clip {action}: {', '.join(map(str, n))}")


@_cmd(quick_app, "set-clip-prompts")
def set_clip_prompts(project: ProjectOpt, json_file: JsonFile):
    """Ghi prompt clip [{n, prompt, verdict, score, issues}] và bật clip các mốc đó."""
    items = _read_json(json_file)
    clips.set_clip_prompts(project, items)
    typer.echo(f"Đã ghi {len(items)} prompt clip")


@_cmd(quick_app, "set-clip")
def set_clip(project: ProjectOpt, n: Annotated[int, typer.Argument()], file: Annotated[Path, typer.Argument()]):
    """Nhập clip đã gen → clips/NNN_MM-SS.<ext>."""
    b = clips.set_clip(project, n, file)
    typer.echo(f"Mốc {n} → {b.clip.file}")


@_cmd(quick_app, "build")
def build(project: ProjectOpt, name: Annotated[Optional[str], typer.Option(help="Tên draft")] = None,
          zoom: Annotated[bool, typer.Option("--zoom/--no-zoom")] = True,
          subtitles: Annotated[bool, typer.Option("--subtitles/--no-subtitles")] = True, config: ConfigOpt = None):
    """Dựng draft CapCut từ images/ + audio/voice.wav + beats.json."""
    from vidflow.quick.build import build_quick

    res = build_quick(project, load_config(config), name=name, zoom=zoom, subtitles=subtitles)
    typer.echo(f"Đã dựng draft: {res}")


# ---- helper cho job Claude ----

@_cmd(quick_app, "set-chars")
def set_chars(project: ProjectOpt, json_file: JsonFile):
    """Ghi nhân vật riêng của video [{id, name, desc, color}]."""
    q = chars.set_chars(project, _read_json(json_file))
    typer.echo(f"Đã ghi {len(q.characters)} nhân vật: {', '.join('@' + c.id for c in q.characters)}")


@_cmd(quick_app, "char-image")
def char_image(project: ProjectOpt, char_id: Annotated[str, typer.Argument(help="ID nhân vật (IN HOA)")],
               file: Annotated[Path, typer.Argument()],
               channel: Annotated[bool, typer.Option("--channel", help="Nhân vật của bộ kênh")] = False):
    """Gắn ảnh character sheet cho nhân vật."""
    dest = chars.set_char_image(project, char_id, file, channel=channel)
    typer.echo(f"@{char_id} → {dest}")


@_cmd(quick_app, "chars")
def chars_list(project: ProjectOpt, json_out: Annotated[bool, typer.Option("--json")] = False):
    """Liệt kê nhân vật (bộ kênh + video), ảnh, số mốc dùng, số mốc bị chặn."""
    rows = chars.char_rows(project)
    if json_out:
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    for r in rows:
        img = "có ảnh" if r["image"] else f"THIẾU ẢNH (chặn {r['blocked']})"
        typer.echo(f"@{r['id']:<14} {r['scope']:<7} {r['uses']:>3} mốc · {img} · {r['desc'][:50]}")


@_cmd(quick_app, "promote")
def promote(project: ProjectOpt, char_id: Annotated[str, typer.Argument()]):
    """Đưa nhân vật riêng của video vào bộ kênh."""
    p = chars.promote(project, char_id)
    typer.echo(f"@{char_id} đã thuộc bộ kênh {p.id}")


@_cmd(quick_app, "set-ideas")
def set_ideas(project: ProjectOpt, json_file: JsonFile):
    """Ghi danh sách ý tưởng [{title, hook, why_viral}]."""
    q = ops.set_ideas(project, _read_json(json_file))
    typer.echo(f"Đã ghi {len(q.ideas)} ý tưởng")


@_cmd(quick_app, "set-beats")
def set_beats(project: ProjectOpt, json_file: JsonFile):
    """Ghi mới beats.json từ mảng câu (chuỗi hoặc {text})."""
    b = ops.set_beat_texts(project, _read_json(json_file))
    typer.echo(f"Đã ghi {len(b.beats)} mốc")


@_cmd(quick_app, "set-prompt")
def set_prompt(project: ProjectOpt, n: Annotated[int, typer.Argument()],
               prompt: Annotated[str, typer.Option(help="Prompt đầy đủ (có câu neo)")],
               verdict: Annotated[str, typer.Option(help="pass | fail")] = "pass",
               score: Annotated[float, typer.Option(help="Điểm 0–10")] = 0,
               issue: Annotated[Optional[list[str]], typer.Option("--issue", help="Vấn đề (lặp được)")] = None,
               cont: Annotated[Optional[bool], typer.Option("--cont/--no-cont", help="Nối cảnh với mốc trước")] = None):
    """Ghi prompt + kết quả tự kiểm duyệt cho một mốc."""
    ops.set_prompt(project, n, prompt, verdict=verdict, score=score, issues=issue or [], cont=cont)
    typer.echo(f"Mốc {n}: {verdict} ({score:g}/10)")


@_cmd(quick_app, "set-prompts")
def set_prompts(project: ProjectOpt, json_file: JsonFile):
    """Ghi nhiều prompt [{n, prompt, verdict, score, issues}]."""
    items = _read_json(json_file)
    ops.set_prompts(project, items)
    typer.echo(f"Đã ghi {len(items)} prompt")


@_cmd(quick_app, "edit-prompt")
def edit_prompt(project: ProjectOpt, n: Annotated[int, typer.Argument()],
                prompt: Annotated[str, typer.Option(help="Prompt mới")], clip: ClipOpt = False):
    """Sửa tay prompt một mốc (xóa kết quả kiểm duyệt cũ)."""
    ops.edit_prompt(project, n, prompt, clip=clip)
    typer.echo(f"Mốc {n}: đã lưu prompt {'clip' if clip else 'ảnh'} — cần kiểm duyệt lại")


@_cmd(quick_app, "set-review")
def set_review(project: ProjectOpt, n: Annotated[int, typer.Argument()],
               verdict: Annotated[str, typer.Option(help="pass | fail | override")],
               score: Annotated[float, typer.Option(help="Điểm 0–10")] = 0,
               issue: Annotated[Optional[list[str]], typer.Option("--issue", help="Vấn đề/gợi ý (lặp được)")] = None,
               clip: ClipOpt = False):
    """Ghi kết quả kiểm duyệt một mốc."""
    ops.set_review(project, n, verdict, score=score, issues=issue or [], clip=clip)
    typer.echo(f"Mốc {n} ({'clip' if clip else 'ảnh'}): {verdict} ({score:g}/10)")


@_cmd(quick_app, "fail")
def fail_cmd(project: ProjectOpt, n: Annotated[int, typer.Argument()],
             reason: Annotated[str, typer.Option(help="Nguyên văn thông báo lỗi của Flow")], clip: ClipOpt = False):
    """Ghi lỗi Flow cho ảnh/clip của mốc (mốc rời danh sách việc tới khi retry)."""
    ops.record_fail(project, n, reason, clip=clip)
    typer.echo(f"Mốc {n}: ghi lỗi {'clip' if clip else 'ảnh'}")


@_cmd(quick_app, "retry")
def retry(project: ProjectOpt, n: Annotated[Optional[list[int]], typer.Argument(help="Mốc (trống = mọi mốc lỗi)")] = None,
          clip: ClipOpt = False):
    """Xóa lỗi để mốc được gen lại."""
    count = ops.clear_errors(project, n or None, clip=clip)
    typer.echo(f"Đã đưa lại {count} mốc lỗi vào danh sách gen")


@_cmd(quick_app, "set-image")
def set_image(project: ProjectOpt, n: Annotated[int, typer.Argument()], file: Annotated[Path, typer.Argument()]):
    """Gắn ảnh cho mốc → images/NNN_MM-SS.<ext>."""
    b = ops.set_image(project, n, file)
    typer.echo(f"Mốc {n} → {b.image}")


# ---- preset ----

@_cmd(preset_app, "list")
def preset_list():
    """Liệt kê bộ kênh."""
    for p in list_presets():
        typer.echo(f"{p.id}\t{p.name}\t{p.aspect}\t{p.voice.name}")


@_cmd(preset_app, "show")
def preset_show(preset_id: Annotated[str, typer.Argument()]):
    """In nội dung bộ kênh."""
    typer.echo(json.dumps(load_preset(preset_id).model_dump(), ensure_ascii=False, indent=1))


@_cmd(preset_app, "import")
def preset_import(file: Annotated[Path, typer.Argument(help="Brief .docx hoặc .txt")],
                  preset_id: Annotated[str, typer.Option("--id", help="id bộ kênh (chữ thường-gạch-ngang)")],
                  force: Annotated[bool, typer.Option("--force", help="Ghi đè")] = False):
    """Tạo bộ kênh từ brief (Claude trích câu neo nguyên văn, giọng đọc)."""
    p = import_preset(file, preset_id=preset_id, force=force)
    typer.echo(f"Đã tạo presets/{p.id}.yaml\n  neo đầu: {p.style_anchor_start}\n  neo cuối: {p.style_anchor_end}\n"
               f"  giọng: {p.voice.name} — {p.voice.style}")
