"""Clip động (Veo trong Google Flow) cho các mốc được chọn — spec 2026-10-12."""
from __future__ import annotations

import shutil
from pathlib import Path

from vidflow.errors import VidflowError
from vidflow.quick.chars import check_known, lookup, parse_refs
from vidflow.quick.model import VIDEO_EXTS, Beat, Beats, Review, image_name, load_quick, require_beats, save_beats
from vidflow.quick.ops import PASSING


def _enabled(beats: Beats) -> int:
    return sum(1 for b in beats.beats if b.clip.enabled)


def _check_limit(beats: Beats, new: int, max_clips: int) -> None:
    cur = _enabled(beats)
    if cur + new > max_clips:
        raise VidflowError(f"Tối đa {max_clips} clip (đang bật {cur}) — tăng bằng "
                           "`vidflow quick settings --max-clips <n>`.")


def set_clip_enabled(root: Path, ns: list[int], on: bool) -> Beats:
    q = load_quick(root)
    beats = require_beats(root)
    targets = [beats.get(n) for n in ns]
    if on:
        _check_limit(beats, len({b.n for b in targets if not b.clip.enabled}), q.max_clips)
    for b in targets:
        b.clip.enabled = on
    save_beats(root, beats)
    return beats


def set_clip_prompts(root: Path, items: list[dict]) -> Beats:
    """items: [{n, prompt, verdict, score, issues?}] — ghi prompt clip + tự kiểm duyệt, bật clip cho mốc."""
    q = load_quick(root)
    beats = require_beats(root)
    known = lookup(root, q)
    staged = []
    for it in items:
        b = beats.get(int(it["n"]))
        prompt = str(it.get("prompt", "")).strip()
        if not prompt:
            raise VidflowError(f"Mốc {b.n}: prompt clip rỗng.")
        check_known(parse_refs(prompt), known)
        verdict = it.get("verdict", "pass")
        if verdict not in ("pass", "fail"):
            raise VidflowError("verdict phải là pass hoặc fail")
        staged.append((b, prompt, Review(verdict=verdict, score=float(it.get("score", 0)),
                                         issues=list(it.get("issues") or []))))
    _check_limit(beats, len({b.n for b, _, _ in staged if not b.clip.enabled}), q.max_clips)
    for b, prompt, review in staged:
        if b.clip.status == "error" and prompt != b.clip.prompt:
            b.clip.status, b.clip.error = "redo", ""
        b.clip.prompt, b.clip.review, b.clip.enabled = prompt, review, True
    save_beats(root, beats)
    return beats


def set_clip(root: Path, n: int, src: Path) -> Beat:
    """Nhập clip đã gen → clips/NNN_MM-SS.<ext>."""
    root, src = Path(root), Path(src)
    if not src.is_file():
        raise VidflowError(f"Không thấy file clip {src}")
    ext = VIDEO_EXTS.get(src.suffix.lower())
    if not ext:
        raise VidflowError(f"Định dạng clip không hỗ trợ: {src.suffix} (dùng mp4/mov/webm)")
    beats = require_beats(root)
    b = beats.get(n)
    if b.start is None:
        raise VidflowError("Mốc chưa có thời gian — chạy `vidflow quick voice` trước.")
    if not b.clip.enabled:
        raise VidflowError(f"Mốc {n} chưa bật clip.")
    rel = f"clips/{image_name(n, b.start)}{ext}"
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    if b.clip.file and b.clip.file != rel:
        (root / b.clip.file).unlink(missing_ok=True)
    b.clip.file, b.clip.status, b.clip.error = rel, "ok", ""
    save_beats(root, beats)
    return b


def clip_todo(root: Path) -> dict:
    """Clip cần gen: đã bật, prompt đạt, ảnh mốc ok, status pending/redo (lỗi phải `retry --clip`)."""
    root = Path(root)
    q = load_quick(root)
    beats = require_beats(root)
    rows = []
    for b in beats.beats:
        c = b.clip
        if not (c.enabled and c.status in ("pending", "redo") and c.prompt and c.review
                and c.review.verdict in PASSING and b.image and b.status == "ok"
                and b.start is not None and b.end is not None):
            continue
        rows.append({"n": b.n, "duration": round(b.end - b.start, 3), "image": str((root / b.image).resolve()),
                     "prompt": c.prompt, "file": f"clips/{image_name(b.n, b.start)}.mp4"})
    if rows and not q.flow.video_model:
        raise VidflowError("Chưa chọn model clip — `vidflow quick settings -p <project> --video-model \"Veo 3.1 Lite\"`.")
    return {"aspect": beats.aspect, "video_model": q.flow.video_model, "resolution": q.flow.resolution, "clips": rows}
