"""Xuất MP4 bằng Remotion (spec 2026-10-12, giai đoạn 2).

`build_render_props` (thuần) đọc quick.yaml + beats.json → props cho remotion/src/DoodleVideo.tsx.
Đường dẫn trong props tương đối với public dir của Remotion, cùng cấu trúc với project (images/…, clips/…, audio/…).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from vidflow.errors import VidflowError
from vidflow.media import probe_duration, wav_duration
from vidflow.quick.clips import ready_clips
from vidflow.quick.model import load_quick, require_beats
from vidflow.quick.ops import VOICE_FILE
from vidflow.quick.preset import REPO, load_preset

FPS = 30
FADE_S = 0.3              # mờ chéo khi mở cảnh mới
SPEED_RANGE = (0.5, 2.0)  # clip-fit=speed: giới hạn tốc độ; ngoài khoảng → cắt / giữ khung cuối
CLIP_VOLUME = 0.5         # tiếng clip, nhỏ dưới giọng đọc
MUSIC_VOLUME = 0.12       # nhạc nền rất nhỏ
SIZES = {"1080p": (1920, 1080), "720p": (1280, 720)}
TRANSITIONS = ("scene", "cut", "fade")
CLIP_FITS = ("trim", "speed")
MUSIC_FILES = ("audio/music.mp3", "audio/music.wav")
PROPS_FILE = "tmp/render-props.json"
PUBLIC_DIR = "tmp/render/public"
REMOTION_DIR = REPO / "remotion"
COMPOSITION = "DoodleVideo"


@dataclass
class RenderOptions:
    resolution: str | None = None  # None = flow.resolution của quick.yaml
    transition: str = "scene"
    clip_fit: str = "trim"
    zoom: bool = True
    subtitles: bool = True
    clip_audio: bool = True
    logo: bool = True
    music: bool = True


@dataclass
class RenderPlan:
    props: dict
    assets: dict[str, Path]  # đường dẫn trong public dir (= giá trị trong props) → file thật
    warnings: list[str] = field(default_factory=list)


def canvas(resolution: str, aspect: str) -> tuple[int, int]:
    if resolution not in SIZES:
        raise VidflowError(f"Độ phân giải phải là 1080p hoặc 720p, nhận {resolution!r}.")
    w, h = SIZES[resolution]
    return (h, w) if aspect == "9:16" else (w, h)


def _check(opts: RenderOptions) -> None:
    if opts.transition not in TRANSITIONS:
        raise VidflowError(f"--transition phải là scene, cut hoặc fade (nhận {opts.transition!r}).")
    if opts.clip_fit not in CLIP_FITS:
        raise VidflowError(f"--clip-fit phải là trim hoặc speed (nhận {opts.clip_fit!r}).")


def _fade(i: int, cont: bool, span: float, transition: str) -> float:
    """Giây mờ chéo khi vào mốc i. scene: nối cảnh (cont) cắt thẳng, cảnh mới mờ chéo."""
    if i == 0 or transition == "cut" or (transition == "scene" and cont):
        return 0.0
    return round(min(FADE_S, span / 2), 3)


def _logo_path(logo: str) -> Path:
    p = Path(logo).expanduser()
    return p if p.is_absolute() else REPO / p


def build_render_props(root: Path, opts: RenderOptions | None = None, *,
                       probe: Callable[[Path], float] | None = None) -> RenderPlan:
    root = Path(root)
    opts = opts or RenderOptions()
    probe = probe or probe_duration
    _check(opts)
    q = load_quick(root)
    beats = require_beats(root)
    if not beats.timed:
        raise VidflowError("Mốc chưa có thời gian — chạy `vidflow quick voice` trước khi xuất video.")
    width, height = canvas(opts.resolution or q.flow.resolution, beats.aspect)
    warnings: list[str] = []
    assets: dict[str, Path] = {}

    voice = root / VOICE_FILE
    audio = None
    voice_s = 0.0
    if voice.is_file():
        audio, voice_s = VOICE_FILE, wav_duration(voice)
        assets[VOICE_FILE] = voice
    else:
        warnings.append("Chưa có audio/voice.wav — video không có giọng đọc.")
    bl = beats.beats
    duration = round(max(voice_s, bl[-1].end), 3)

    ready = ready_clips(root, beats)
    rows: list[dict] = []
    blank: list[int] = []
    for i, b in enumerate(bl):
        start = round(b.start, 3)
        end = round(bl[i + 1].start, 3) if i + 1 < len(bl) else duration
        if end <= start:
            raise VidflowError(f"Mốc {b.n}: thời gian không tăng ({start:g}s → {end:g}s).")
        span = end - start
        row = {"n": b.n, "src": None, "kind": "blank", "start": start, "end": end, "cont": b.cont,
               "fade": _fade(i, b.cont, span, opts.transition), "rate": 1.0, "clipLen": None}
        clip = ready.get(b.n)
        clip_len = 0.0
        if clip is not None:
            try:
                clip_len = round(probe(clip), 3)
            except VidflowError as e:
                warnings.append(f"Mốc {b.n}: không đọc được clip ({e}) — dùng ảnh.")
                clip = None
        if clip is not None:
            rate = 1.0
            if opts.clip_fit == "speed":
                lo, hi = SPEED_RANGE
                want = clip_len / span
                rate = round(min(hi, max(lo, want)), 4)
                if want < lo or want > hi:
                    warnings.append(f"Mốc {b.n}: clip cần tốc độ x{want:.2f}, giới hạn x{rate:g} "
                                    "— phần thừa bị cắt, phần thiếu giữ khung cuối.")
            row.update(src=b.clip.file, kind="video", rate=rate, clipLen=clip_len)
            assets[b.clip.file] = clip
        elif b.image and (root / b.image).is_file():
            row.update(src=b.image, kind="image")
            assets[b.image] = root / b.image
        else:
            blank.append(b.n)
        rows.append(row)
    if len(blank) == len(rows):
        raise VidflowError("Chưa có ảnh mốc nào — gen ảnh (`vidflow quick flow`) trước khi xuất video.")
    if blank:
        warnings.append(f"{len(blank)} mốc chưa có ảnh (khung trống): {', '.join(map(str, blank))}")

    subs = [{"start": round(b.start, 3), "end": round(b.end, 3), "text": b.text.strip()}
            for b in bl if opts.subtitles and b.text.strip()]

    logo = None
    preset = load_preset(q.preset)
    if opts.logo and preset.logo:
        src = _logo_path(preset.logo)
        if src.is_file():
            logo = f"logo/logo{src.suffix.lower()}"
            assets[logo] = src
        else:
            warnings.append(f"Không thấy logo {src} (presets/{preset.id}.yaml) — xuất không có logo.")

    music = None
    if opts.music:
        for rel in MUSIC_FILES:
            if (root / rel).is_file():
                music = rel
                assets[rel] = root / rel
                break

    props = {"fps": FPS, "width": width, "height": height, "duration": duration, "beats": rows, "audio": audio,
             "subtitles": subs, "zoom": opts.zoom, "clipVolume": CLIP_VOLUME if opts.clip_audio else 0.0,
             "logo": logo, "music": music, "musicVolume": MUSIC_VOLUME}
    return RenderPlan(props=props, assets=assets, warnings=warnings)
