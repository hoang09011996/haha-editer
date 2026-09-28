from __future__ import annotations

import math
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pycapcut as cc

from vidflow.config import Config
from vidflow.errors import CapCutRunningError, ConfigError, ScriptError, VidflowError
from vidflow.project import Project
from vidflow.schema import Script
from vidflow.timeline import Timeline

SUB_STYLE = dict(size=8.0, color=(1.0, 1.0, 1.0), align=1, auto_wrapping=True)
SUB_Y = -0.7


def canvas_size(aspect: str) -> tuple[int, int]:
    return (1080, 1920) if aspect == "9:16" else (1920, 1080)


def capcut_running() -> bool:
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def draft_name(project: Project) -> str:
    return f"vidflow_{project.root.name}"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _us(seconds: float) -> int:
    return round(seconds * 1_000_000)


def _range(start: float, end: float) -> cc.Timerange:
    return cc.Timerange(_us(start), _us(end) - _us(start))


class _MediaStage:
    """CapCut macOS bị sandbox (chỉ đọc ~/Movies): copy media vào media_folder/<draft> và trỏ draft tới bản copy."""

    def __init__(self, project: Project, root: Path):
        self.project = project
        self.root = root

    def __call__(self, rel: str) -> str:
        src = self.project.path(rel)
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.stat().st_size != src.stat().st_size or dest.stat().st_mtime < src.stat().st_mtime:
            shutil.copy2(src, dest)
        return str(dest)


def build_draft(project: Project, cfg: Config, script: Script, timeline: Timeline, *,
                is_running: Callable[[], bool] = capcut_running, stamp: Callable[[], str] = _stamp) -> Path:
    if is_running():
        raise CapCutRunningError("CapCut đang mở. Thoát CapCut (Cmd+Q) rồi chạy lại `vidflow build`.")
    if not timeline.scenes:
        reasons = "; ".join(f"{k}: {v}" for k, v in timeline.skipped.items()) or "script không có cảnh"
        raise VidflowError(f"Không có cảnh nào dựng được ({reasons})")
    if not cfg.draft_folder.is_dir():
        raise ConfigError(f"Không thấy thư mục draft CapCut {cfg.draft_folder}; đặt draft_folder trong vidflow.toml.")
    if script.music and not project.path(script.music.file).is_file():
        raise ScriptError(f"Không thấy file nhạc {script.music.file}")

    folder = cc.DraftFolder(str(cfg.draft_folder))
    name = draft_name(project)
    if folder.has_draft(name):
        shutil.copytree(cfg.draft_folder / name, project.backups_dir / stamp() / name)
    stage = _MediaStage(project, cfg.media_folder / name)

    try:
        draft_dir = _write_draft(project, folder, name, script, timeline, stage)
    except ValueError as e:  # pyCapCut báo lỗi thời gian/segment bằng ValueError
        raise VidflowError(f"pyCapCut từ chối dựng draft: {e}") from e

    state = project.load_state()
    state.draft_path = str(draft_dir)
    state.last_build_at = stamp()
    project.save_state(state)
    return draft_dir


def _write_draft(project: Project, folder, name: str, script: Script, timeline: Timeline, stage) -> Path:
    w, h = canvas_size(script.aspect)
    draft = folder.create_draft(name, w, h, allow_replace=True)
    draft.add_track(cc.TrackType.video)
    draft.add_track(cc.TrackType.audio, "voice")
    if script.music:
        draft.add_track(cc.TrackType.audio, "music")
    if any(p.subtitles for p in timeline.scenes):
        draft.add_track(cc.TrackType.text, "subs")

    style = cc.TextStyle(**SUB_STYLE)
    clip_settings = cc.ClipSettings(transform_y=SUB_Y)
    for p in timeline.scenes:
        target = _range(p.start, p.end)
        if p.clip_speed == 1.0:
            src_us, speed = target.duration, 1.0
        else:
            src_us = math.floor(p.clip_len * 1_000_000)
            speed = src_us / target.duration
        draft.add_segment(cc.VideoSegment(stage(p.clip), target, source_timerange=cc.Timerange(0, src_us),
                                          speed=speed, volume=p.clip_volume))
        if p.voice:
            draft.add_segment(cc.AudioSegment(stage(p.voice),
                                              cc.Timerange(_us(p.start), math.floor(p.voice_len * 1_000_000)),
                                              speed=p.voice_speed), "voice")
        for s in p.subtitles:
            draft.add_segment(cc.TextSegment(s.text, _range(s.start, s.end), style=style,
                                             clip_settings=clip_settings), "subs")

    if script.music:
        material = cc.AudioMaterial(stage(script.music.file))
        total_us, t = _us(timeline.total), 0
        while t < total_us:
            d = min(material.duration, total_us - t)
            draft.add_segment(cc.AudioSegment(material, cc.Timerange(t, d), volume=script.music.volume), "music")
            t += d

    draft.save()
    # CapCut 9.5 macOS đọc draft_info.json; pyCapCut chỉ ghi draft_content.json
    draft_dir = Path(folder.folder_path) / name
    shutil.copy(draft_dir / "draft_content.json", draft_dir / "draft_info.json")
    return draft_dir
