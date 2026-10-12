"""Bước cuối quy trình nhanh: gọi `vidflow.assemble.assemble` (bước 6) với images/, voice.wav, beats.json, clip ok."""
from __future__ import annotations

from pathlib import Path

from vidflow.config import Config
from vidflow.errors import VidflowError
from vidflow.quick.clips import ready_clips
from vidflow.quick.model import BEATS_FILE, load_beats, load_quick
from vidflow.quick.ops import IMAGE_EXTS, VOICE_FILE, advance


def build_quick(root: Path, cfg: Config, *, name: str | None = None, zoom: bool = True, subtitles: bool = True):
    from vidflow.assemble import assemble  # bước 6, viết song song

    root = Path(root)
    q = load_quick(root)
    images = root / "images"
    if not images.is_dir() or not any(f.suffix.lower() in IMAGE_EXTS for f in images.iterdir()):
        raise VidflowError(f"Chưa có ảnh trong {images} — chạy `vidflow quick flow` hoặc thả ảnh NNN_MM-SS.jpg vào.")
    beats = load_beats(root)
    voice = root / VOICE_FILE
    res = assemble(images, audio=voice if voice.is_file() else None,
                   beats=root / BEATS_FILE if beats and beats.timed else None,
                   name=name or root.name, aspect=beats.aspect if beats else "auto",
                   zoom=zoom, subtitles=subtitles, clips=ready_clips(root, beats) if beats else {}, cfg=cfg)
    advance(root, "built", q)
    return res
