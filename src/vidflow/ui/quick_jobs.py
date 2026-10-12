"""Lệnh việc nền của quy trình nhanh trên UI: job Claude (vidflow.quick.jobs) và CLI `vidflow quick voice|render|build`."""
from __future__ import annotations

import sys
from pathlib import Path

from vidflow.errors import VidflowError
from vidflow.quick import jobs as qjobs
from vidflow.quick.model import PROVIDERS, load_quick, require_beats
from vidflow.quick.preset import load_preset

CLI_QUICK = ("voice", "render", "build")
QUICK_UI_KINDS = qjobs.QUICK_KINDS + CLI_QUICK
QUICK_LABELS = {**qjobs.LABELS, "voice": "Tạo giọng đọc (Gemini)", "render": "Xuất MP4 (Remotion)",
                "build": "Dựng draft CapCut"}
RENDER_CHOICES = {"resolution": ("1080p", "720p"), "transition": ("scene", "cut", "fade"), "clip_fit": ("trim", "speed")}
RENDER_FLAGS = ("zoom", "subtitles", "clip_audio", "logo", "music")
BUILD_FLAGS = ("zoom", "subtitles")
NEEDS_BEATS = ("voice", "prompts", "flow", "clips", "render", "build")
PROVIDER_KINDS = qjobs.GEN_KINDS


def check_provider(kind: str, provider: str | None) -> None:
    """Ghi đè nguồn gen một lần (None = theo cài đặt video). Chỉ cho việc gen sheet/ảnh/clip."""
    if provider is None:
        return
    if kind not in PROVIDER_KINDS:
        raise ValueError(f"Việc '{kind}' không chọn nguồn gen.")
    if provider not in PROVIDERS:
        raise ValueError(f"Nguồn gen chỉ nhận: {', '.join(PROVIDERS)}")


def option_args(kind: str, options: dict | None) -> list[str]:
    """Đổi tùy chọn UI thành cờ CLI — chỉ nhận khóa/giá trị trong danh sách trắng. Sai → ValueError."""
    options = dict(options or {})
    choices = RENDER_CHOICES if kind == "render" else {}
    flags = RENDER_FLAGS if kind == "render" else BUILD_FLAGS if kind == "build" else ()
    unknown = sorted(set(options) - set(choices) - set(flags))
    if unknown:
        raise ValueError(f"Tùy chọn không hỗ trợ cho '{kind}': {', '.join(unknown)}")
    args: list[str] = []
    for key, allowed in choices.items():
        if key in options:
            if options[key] not in allowed:
                raise ValueError(f"{key} chỉ nhận: {', '.join(allowed)}")
            args += [f"--{key.replace('_', '-')}", options[key]]
    for key in flags:
        if key in options:
            if not isinstance(options[key], bool):
                raise ValueError(f"{key} phải là true/false")
            name = key.replace("_", "-")
            args.append(f"--{name}" if options[key] else f"--no-{name}")
    return args


def build_quick_cmd(kind: str, root: Path, instruction: str = "", options: dict | None = None,
                    provider: str | None = None) -> list[str]:
    root = Path(root)
    check_provider(kind, provider)
    if kind in CLI_QUICK:
        return [sys.executable, "-m", "vidflow", "quick", kind, "-p", str(root)] + option_args(kind, options)
    if kind in qjobs.QUICK_KINDS:
        option_args(kind, options)  # việc Claude không nhận tùy chọn nào
        cmd = qjobs.claude_cmd(kind, root, load_preset(load_quick(root).preset), provider=provider)
        if instruction.strip():
            cmd[-1] += f' Ghi chú của người dùng (ưu tiên làm theo): "{instruction.strip()}".'
        return cmd
    raise ValueError(f"Không hỗ trợ việc '{kind}'")


def check_quick_job(kind: str, root: Path, options: dict | None = None, provider: str | None = None) -> None:
    """Kiểm tra trước khi chạy (giống CLI). Loại việc/tùy chọn/nguồn sai → ValueError; điều kiện chưa đủ → VidflowError."""
    if kind not in QUICK_UI_KINDS:
        raise ValueError(f"Việc không hỗ trợ: {kind}")
    option_args(kind, options)
    check_provider(kind, provider)
    q = load_quick(root)
    if kind == "script" and not q.picked_idea():
        raise VidflowError("Chưa chọn ý tưởng — chọn một ý tưởng trước khi viết kịch bản.")
    if kind in NEEDS_BEATS:
        require_beats(root)
    if kind == "clips" and not q.flow.video_model:
        raise VidflowError("Chưa chọn model clip — chọn trong Cài đặt video.")
