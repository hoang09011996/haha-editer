"""Bước 6 — dựng draft CapCut thẳng từ một thư mục ảnh `NNN_MM-SS.<jpg|png|webp>` (+ voice, + beats.json).

Backup draft cũ: `cfg.media_folder/backups/<stamp>/<draft>` (cùng chỗ CapCut đọc được, không làm bẩn thư mục ảnh).
"""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from vidflow.capcut_draft import _MediaStage, _stamp, _us, canvas_size, capcut_running, cover_scale
from vidflow.config import Config
from vidflow.errors import CapCutRunningError, ConfigError, VidflowError

NAME_RE = re.compile(r"^(\d{3})_(\d{2})-(\d{2})\.(jpe?g|png|webp)$", re.IGNORECASE)
TAIL_S = 4.0          # ảnh cuối kéo thêm khi không có audio
ZOOM = 1.08           # zoom nhẹ xen kẽ 1.0 ↔ 1.08 (so với mức phủ kín)
SUB_STYLE = dict(size=7.0, color=(1.0, 1.0, 1.0), align=1, auto_wrapping=True, max_line_width=0.82)
SUB_BG = dict(color="#000000", alpha=0.6, round_radius=0.2, style=1)
SUB_Y = -0.8
CLIP_VOLUME = 0.5     # tiếng clip Veo, nhỏ dưới giọng đọc


@dataclass(frozen=True)
class Placement:
    file: Path
    start: float
    end: float
    n: int = 0  # số mốc NNN


@dataclass
class AssembleReport:
    draft_dir: Path
    count: int
    total_s: float
    skipped_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    clips: int = 0


def load_beats(path: Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise VidflowError(f"Không đọc được {path}: {e}") from e
    beats = data.get("beats") if isinstance(data, dict) else data
    if not isinstance(beats, list):
        raise VidflowError(f"{path}: thiếu danh sách 'beats'")
    return beats


def plan_images(images_dir: Path, beats: Path | list[dict] | None = None, audio_len: float | None = None, *,
                skipped: list[str] | None = None, warnings: list[str] | None = None) -> list[Placement]:
    """Xếp ảnh theo NNN; mốc = MM-SS (hoặc beat.start khi có beats.json); ảnh i kéo tới mốc ảnh i+1."""
    images_dir = Path(images_dir)
    skipped = skipped if skipped is not None else []
    warnings = warnings if warnings is not None else []
    if not images_dir.is_dir():
        raise VidflowError(f"Không thấy thư mục ảnh {images_dir}")

    found: list[tuple[int, float, Path]] = []
    for f in sorted(images_dir.iterdir()):
        if f.name.startswith(".") or not f.is_file():
            continue
        m = NAME_RE.match(f.name)
        if not m:
            skipped.append(f.name)
            continue
        found.append((int(m[1]), int(m[2]) * 60 + int(m[3]), f))
    if not found:
        raise VidflowError(f"Không có ảnh đúng mẫu NNN_MM-SS.jpg trong {images_dir}"
                           + (f" (bỏ qua: {', '.join(skipped)})" if skipped else ""))
    found.sort(key=lambda x: (x[0], x[2].name))

    dup = [n for n, c in Counter(n for n, _, _ in found).items() if c > 1]
    if dup:
        names = "; ".join(", ".join(f.name for k, _, f in found if k == n) for n in dup)
        raise VidflowError(f"Trùng số thứ tự ảnh: {names}")

    if beats is not None:
        beat_list = load_beats(beats) if not isinstance(beats, list) else beats
        by_n = {int(b["n"]): b for b in beat_list if isinstance(b, dict) and "n" in b}
        nums = {n for n, _, _ in found}
        timed = []
        for n, t, f in found:
            b = by_n.get(n)
            if b is None or b.get("start") is None:
                warnings.append(f"{f.name}: không có mốc trong beats.json, dùng mốc tên file")
                timed.append((n, float(t), f))
            else:
                timed.append((n, round(float(b["start"]), 3), f))
        orphan = sorted(set(by_n) - nums)
        if orphan:
            warnings.append(f"beats.json có mốc không có ảnh: {', '.join(str(n) for n in orphan)}")
        found = timed

    for (_, ta, fa), (_, tb, fb) in zip(found, found[1:]):
        if tb <= ta:
            raise VidflowError(f"Mốc thời gian không tăng: {fa.name} ({ta:g}s) → {fb.name} ({tb:g}s)")

    last_start = found[-1][1]
    if audio_len is not None and audio_len > last_start:
        last_end = float(audio_len)
    else:
        if audio_len is not None:
            warnings.append(f"Audio dài {audio_len:.2f}s ngắn hơn mốc ảnh cuối {last_start:g}s; ảnh cuối kéo {TAIL_S:g}s")
        last_end = last_start + TAIL_S
    ends = [t for _, t, _ in found[1:]] + [last_end]
    return [Placement(f, float(t), float(e), n) for (n, t, f), e in zip(found, ends)]


def default_name(images_dir: Path) -> str:
    d = Path(images_dir).resolve()
    base = d.parent.name if d.name.lower() == "images" and d.parent.name else d.name
    return f"vidflow_{base}"


class _Dir:
    """Bộ chuyển cho _MediaStage: thay Project bằng một thư mục bất kỳ."""

    def __init__(self, root: Path):
        self.root = root

    def path(self, rel: str) -> Path:
        return self.root / rel


def _image_size(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as im:  # chỉ đọc header
        return im.size


def _pick_aspect(plan: list[Placement]) -> str:
    sizes = Counter(_image_size(p.file) for p in plan)
    landscape = sum(c for (w, h), c in sizes.items() if w >= h)
    return "16:9" if landscape * 2 >= len(plan) else "9:16"


def assemble(images_dir: Path, *, audio: Path | None = None, beats: Path | None = None, name: str | None = None,
             aspect: str = "auto", zoom: bool = True, subtitles: bool = True, clips: dict[int, Path] | None = None,
             cfg: Config,
             is_running: Callable[[], bool] | None = None, stamp: Callable[[], str] = _stamp) -> AssembleReport:
    import pycapcut as cc

    is_running = is_running or capcut_running
    if is_running():
        raise CapCutRunningError("CapCut đang mở. Thoát CapCut (Cmd+Q) rồi chạy lại `vidflow assemble`.")
    if aspect not in ("auto", "16:9", "9:16"):
        raise VidflowError("aspect phải là auto, 16:9 hoặc 9:16")
    if not cfg.draft_folder.is_dir():
        raise ConfigError(f"Không thấy thư mục draft CapCut {cfg.draft_folder}; đặt draft_folder trong vidflow.toml.")
    images_dir = Path(images_dir)
    if audio is not None and not Path(audio).is_file():
        raise VidflowError(f"Không thấy file audio {audio}")
    name = name or default_name(images_dir)
    stage_root = cfg.media_folder / name

    audio_mat = None
    if audio is not None:
        audio = Path(audio)
        staged = _MediaStage(_Dir(audio.parent), stage_root / "audio")(audio.name)
        audio_mat = cc.AudioMaterial(staged)  # đo bằng pymediainfo như pyCapCut → segment không vượt material

    skipped: list[str] = []
    warnings: list[str] = []
    beat_list = load_beats(beats) if beats is not None else None
    plan = plan_images(images_dir, beat_list, audio_mat.duration / 1_000_000 if audio_mat else None,
                       skipped=skipped, warnings=warnings)
    if aspect == "auto":
        aspect = _pick_aspect(plan)
    w, h = canvas_size(aspect)

    folder = cc.DraftFolder(str(cfg.draft_folder))
    if folder.has_draft(name):
        shutil.copytree(cfg.draft_folder / name, cfg.media_folder / "backups" / stamp() / name)

    try:
        draft = folder.create_draft(name, w, h, allow_replace=True)
        draft.add_track(cc.TrackType.video)
        if audio_mat is not None:
            draft.add_track(cc.TrackType.audio, "voice")
        sub_beats = [b for b in (beat_list or []) if str(b.get("text") or "").strip() and b.get("start") is not None]
        if subtitles and sub_beats:
            draft.add_track(cc.TrackType.text, "subs")

        stage = _MediaStage(_Dir(images_dir), stage_root / "images")
        materials: dict[str, cc.VideoMaterial] = {}
        kp = cc.KeyframeProperty
        clips = clips or {}
        n_clips = 0
        for i, p in enumerate(plan):
            a, b = _us(p.start), _us(p.end)
            clip_path = clips.get(p.n)
            if clip_path is not None:
                # clip thay ảnh: cắt theo độ dài mốc; clip ngắn hơn mốc → làm chậm cho vừa (pyCapCut không giữ khung cuối)
                clip_path = Path(clip_path)
                path = _MediaStage(_Dir(clip_path.parent), stage_root / "clips")(clip_path.name)
                mat = materials.get(path) or materials.setdefault(path, cc.VideoMaterial(path))
                base = cover_scale(mat.width, mat.height, w, h)
                src_len = min(mat.duration, b - a)
                dur = b - a
                if src_len * 10 < dur:  # tốc độ < x0.1 (giới hạn CapCut) → giữ x0.1, clip phủ ngắn hơn mốc
                    dur = src_len * 10
                    warnings.append(f"Mốc {p.n}: clip quá ngắn so với mốc (cần tốc độ x{src_len / (b - a):.2f}), "
                                    f"giữ x0.1 — clip chỉ phủ {dur / 1e6:.2f}s/{(b - a) / 1e6:.2f}s.")
                draft.add_segment(cc.VideoSegment(mat, cc.Timerange(a, dur),
                                                  source_timerange=cc.Timerange(0, src_len),
                                                  clip_settings=cc.ClipSettings(scale_x=base, scale_y=base),
                                                  volume=CLIP_VOLUME))
                n_clips += 1
                continue
            path = stage(p.file.name)
            mat = materials.get(path) or materials.setdefault(path, cc.VideoMaterial(path))
            base = cover_scale(mat.width, mat.height, w, h)
            seg = cc.VideoSegment(mat, cc.Timerange(a, b - a), clip_settings=cc.ClipSettings(scale_x=base, scale_y=base),
                                  volume=0.0)
            if zoom:
                lo, hi = (base, base * ZOOM) if i % 2 == 0 else (base * ZOOM, base)
                seg.add_keyframe(kp.uniform_scale, 0, lo)
                seg.add_keyframe(kp.uniform_scale, b - a, hi)
            draft.add_segment(seg)

        total_us = _us(plan[-1].end)
        if audio_mat is not None:
            draft.add_segment(cc.AudioSegment(audio_mat, cc.Timerange(0, min(audio_mat.duration, total_us))), "voice")

        if subtitles and sub_beats:
            style = cc.TextStyle(**SUB_STYLE)
            bg = cc.TextBackground(**SUB_BG)
            clip = cc.ClipSettings(transform_y=SUB_Y)
            sub_beats.sort(key=lambda x: float(x["start"]))
            for j, bt in enumerate(sub_beats):
                a = _us(float(bt["start"]))
                end = bt.get("end")
                b = _us(float(end)) if end is not None else total_us
                if j + 1 < len(sub_beats):
                    b = min(b, _us(float(sub_beats[j + 1]["start"])))
                b = min(b, total_us)
                if b <= a:
                    warnings.append(f"Bỏ phụ đề beat {bt.get('n')}: thời lượng không hợp lệ")
                    continue
                draft.add_segment(cc.TextSegment(str(bt["text"]).strip(), cc.Timerange(a, b - a), style=style,
                                                 background=bg, clip_settings=clip), "subs")
        draft.save()
    except ValueError as e:  # pyCapCut báo lỗi thời gian/segment bằng ValueError
        raise VidflowError(f"pyCapCut từ chối dựng draft: {e}") from e

    draft_dir = Path(folder.folder_path) / name
    # CapCut 9.5 macOS đọc draft_info.json; pyCapCut chỉ ghi draft_content.json
    shutil.copy(draft_dir / "draft_content.json", draft_dir / "draft_info.json")
    return AssembleReport(draft_dir=draft_dir, count=len(plan), total_s=plan[-1].end,
                          skipped_files=skipped, warnings=warnings, clips=n_clips)
