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
from vidflow.timeline import ImagePlan, ScenePlan, Timeline

SUB_STYLE = dict(size=8.0, color=(1.0, 1.0, 1.0), align=1, auto_wrapping=True)
SUB_Y = -0.7

# cảnh ảnh dựng trực tiếp trong CapCut (assemble=capcut)
ZOOM = 1.15          # mức phóng của zoom_in/zoom_out và khi pan
PAN = 0.1            # độ dời khi pan, đơn vị nửa canvas (CapCut position)
TRANSITIONS = {"fade": cc.TransitionType.叠化, "slide": cc.TransitionType.滑动}  # cut → không chuyển cảnh
TRANSITION_MAX_SHARE = 0.5  # chuyển cảnh không dài quá nửa ảnh ngắn hơn
BUBBLE_STYLE = dict(size=7.0, color=(0.0, 0.0, 0.0), align=1, auto_wrapping=True, max_line_width=0.8)
BUBBLE_BG = dict(color="#FFFFFF", alpha=1.0, round_radius=0.3, style=1)
BUBBLE_Y = 0.7


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


def cover_scale(img_w: int, img_h: int, canvas_w: int, canvas_h: int) -> float:
    """CapCut mặc định đặt ảnh vừa khít (fit) trong canvas; hệ số phóng thêm để ảnh phủ kín (cover) không méo."""
    fit = min(canvas_w / img_w, canvas_h / img_h)
    cover = max(canvas_w / img_w, canvas_h / img_h)
    return cover / fit


def _motion(seg: cc.VideoSegment, motion: str, base: float, dur_us: int) -> None:
    """Ken Burns bằng keyframe: scale/position tuyến tính từ đầu tới cuối ảnh; base = hệ số phủ kín canvas."""
    kp = cc.KeyframeProperty
    if motion in ("zoom_in", "zoom_out"):
        a, b = (base, base * ZOOM) if motion == "zoom_in" else (base * ZOOM, base)
        seg.add_keyframe(kp.uniform_scale, 0, a)
        seg.add_keyframe(kp.uniform_scale, dur_us, b)
        return
    pans = {"pan_left": (kp.position_x, PAN, -PAN), "pan_right": (kp.position_x, -PAN, PAN),
            "pan_up": (kp.position_y, -PAN, PAN), "pan_down": (kp.position_y, PAN, -PAN)}
    if motion in pans:
        prop, a, b = pans[motion]
        seg.add_keyframe(prop, 0, a)
        seg.add_keyframe(prop, dur_us, b)


def _add_images(draft, p: ScenePlan, stage, canvas: tuple[int, int], materials: dict) -> None:
    style = cc.TextStyle(**BUBBLE_STYLE)
    background = cc.TextBackground(**BUBBLE_BG)
    bubble_clip = cc.ClipSettings(transform_y=BUBBLE_Y)
    ranges = [_range(im.start, im.end) for im in p.images]
    transition = TRANSITIONS.get(p.transition)
    for i, (im, rng) in enumerate(zip(p.images, ranges)):
        path = stage(im.file)
        if path not in materials:
            materials[path] = cc.VideoMaterial(path)
        mat = materials[path]
        base = cover_scale(mat.width, mat.height, *canvas)
        moving = p.mode != "stopmotion" and im.motion != "static"
        scale = base * ZOOM if moving and im.motion.startswith("pan_") else base
        seg = cc.VideoSegment(mat, rng, clip_settings=cc.ClipSettings(scale_x=scale, scale_y=scale), volume=0.0)
        if moving:
            _motion(seg, im.motion, base, rng.duration)
        if transition is not None and i + 1 < len(p.images):
            limit = int(min(rng.duration, ranges[i + 1].duration) * TRANSITION_MAX_SHARE)
            seg.add_transition(transition, duration=min(transition.value.default_duration, limit))
        draft.add_segment(seg)
        if im.caption.strip():
            draft.add_segment(cc.TextSegment(im.caption, rng, style=style, background=background,
                                             clip_settings=bubble_clip), "bubbles")


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
    if any(im.caption.strip() for p in timeline.scenes for im in p.images):
        draft.add_track(cc.TrackType.text, "bubbles")

    style = cc.TextStyle(**SUB_STYLE)
    clip_settings = cc.ClipSettings(transform_y=SUB_Y)
    images: dict[str, cc.VideoMaterial] = {}
    for p in timeline.scenes:
        target = _range(p.start, p.end)
        if p.images:
            _add_images(draft, p, stage, (w, h), images)
        else:
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
