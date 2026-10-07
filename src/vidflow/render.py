"""Render cảnh dựng từ ảnh (slideshow / stopmotion / comic) thành clip mp4 bằng ffmpeg."""
from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from vidflow.capcut_draft import canvas_size
from vidflow.config import Config
from vidflow.errors import VidflowError
from vidflow.inputs import SCENE_PAD_S, _digest, _file_digest
from vidflow.media import floor_ms
from vidflow.project import Project
from vidflow.schema import Frame, Scene, Script
from vidflow.state import ProjectState, SceneState, Take
from vidflow.timeline import split_subtitle
from vidflow.video import _now_iso

FPS = 30
ZOOM = 0.15
XFADE = {"fade": "fade", "slide": "slideleft"}
FONT_SIZE = {"9:16": 56, "16:9": 48}
WRAP = {"9:16": 22, "16:9": 40}


def _picked(state: ProjectState, scene: Scene) -> tuple[list[tuple[Frame, str]], list[str]]:
    """(khung đã duyệt có ảnh chọn, id khung đã duyệt thiếu ảnh)."""
    st = state.scenes.get(scene.id) or SceneState()
    ok, missing = [], []
    for f in scene.frames:
        if f.status != "approved":
            continue
        fs = st.frames.get(f.id)
        if fs is None or fs.picked is None:
            missing.append(f.id)
        else:
            ok.append((f, fs.images[fs.picked].file))
    return ok, missing


def _voice_target(script: Script, state: ProjectState, scene: Scene) -> float:
    st = state.scenes.get(scene.id)
    if not scene.narration.strip() or st is None or st.tts is None:
        return 0.0
    return round(floor_ms(st.tts.duration_s / script.voice.speed) + SCENE_PAD_S, 3)


def planned_durations(script: Script, state: ProjectState, scene: Scene) -> list[float]:
    """Thời lượng từng ảnh trên clip. Stop-motion: chuỗi lặp, mỗi ảnh 1/fps."""
    frames = [f for f, _ in _picked(state, scene)[0]]
    if not frames:
        return []
    voice = _voice_target(script, state, scene)
    if scene.mode == "stopmotion":
        step = 1 / scene.fps
        target = max(len(frames) * step, voice)
        n = math.ceil(round(target / step, 6))
        durs = [step] * n
        durs[-1] = round(target - step * (n - 1), 6)
        return durs
    base = sum(f.seconds for f in frames)
    factor = max(1.0, voice / base) if voice else 1.0
    return [f.seconds * factor for f in frames]


def render_hash(project: Project, script: Script, state: ProjectState, scene: Scene) -> str | None:
    picked, missing = _picked(state, scene)
    if missing or not picked:
        return None
    return _digest({
        "mode": scene.mode, "fps": scene.fps, "transition": scene.transition, "aspect": script.aspect,
        "frames": [[_file_digest(project.path(file)), f.seconds, f.motion, f.caption] for f, file in picked],
        "durations": [round(d, 4) for d in planned_durations(script, state, scene)],
    })


def _ff(args: list[str]) -> None:
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise VidflowError(f"ffmpeg lỗi: {r.stderr.strip()[-600:]}")


def _cover(src: Path, dest: Path, w: int, h: int) -> None:
    """Chuẩn hóa ảnh: phủ kín w×h (scale tăng rồi crop giữa), không méo."""
    _ff(["-i", str(src), "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1",
         "-frames:v", "1", str(dest)])


def _zoompan(motion: str, n: int) -> str:
    d = max(n - 1, 1)
    center = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    return {
        "zoom_in": f"z='1+{ZOOM}*on/{d}':{center}",
        "zoom_out": f"z='{1 + ZOOM}-{ZOOM}*on/{d}':{center}",
        "pan_right": f"z='{1 + ZOOM}':x='(iw-iw/zoom)*on/{d}':y='ih/2-(ih/zoom/2)'",
        "pan_left": f"z='{1 + ZOOM}':x='(iw-iw/zoom)*(1-on/{d})':y='ih/2-(ih/zoom/2)'",
        "pan_down": f"z='{1 + ZOOM}':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/{d}'",
        "pan_up": f"z='{1 + ZOOM}':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{d})'",
        "static": "z='1':x='0':y='0'",
    }[motion]


def _bubble(caption: str, aspect: str, w: int, h: int, font: Path, tmp: Path, idx: int) -> Path:
    """Bong bóng thoại: PNG trong suốt cỡ canvas, hộp trắng toàn chiều ngang phía trên + chữ đen căn giữa.
    Vẽ bằng Pillow (ffmpeg Homebrew không có drawtext); font hỗ trợ tiếng Việt."""
    from PIL import Image, ImageDraw, ImageFont

    lines = split_subtitle(caption, WRAP[aspect])
    size = FONT_SIZE[aspect]
    fnt = ImageFont.truetype(str(font), size)
    line_h = size + 14
    box_h = len(lines) * line_h + 60
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 60, w - 40, 60 + box_h], radius=36, fill=(255, 255, 255, 242))
    y = 60 + 30
    for line in lines:
        tw = d.textlength(line, font=fnt)
        d.text(((w - tw) / 2, y), line, font=fnt, fill=(0, 0, 0, 255))
        y += line_h
    out = tmp / f"bubble{idx}.png"
    img.save(out)
    return out


def _segment(img: Path, out: Path, seconds: float, motion: str, w: int, h: int, bubble: Path | None) -> None:
    n = max(1, round(seconds * FPS))
    zp = f"scale={w * 2}:{h * 2},zoompan={_zoompan(motion, n)}:d={n}:s={w}x{h}:fps={FPS}"
    if bubble:
        args = ["-i", str(img), "-i", str(bubble), "-filter_complex", f"[0:v]{zp}[b];[b][1:v]overlay=0:0,format=yuv420p"]
    else:
        args = ["-i", str(img), "-vf", f"{zp},format=yuv420p"]
    _ff([*args, "-frames:v", str(n), "-c:v", "libx264", "-r", str(FPS), str(out)])


def _join(segments: list[Path], durs: list[float], transition: str, out: Path) -> None:
    if len(segments) == 1 or transition == "cut":
        listing = out.with_suffix(".txt")
        listing.write_text("".join(f"file '{p}'\n" for p in segments), encoding="utf-8")
        _ff(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)])
        return
    t = min(0.4, min(durs) / 2)
    inputs, chains, acc, last = [], [], 0.0, "[0:v]"
    for i, p in enumerate(segments):
        inputs += ["-i", str(p)]
    acc = durs[0] + t
    for i in range(1, len(segments)):
        label = f"[v{i}]"
        chains.append(f"{last}[{i}:v]xfade=transition={XFADE[transition]}:duration={t:.3f}:offset={acc - t:.3f}{label}")
        acc += (durs[i] + (t if i < len(segments) - 1 else 0)) - t
        last = label
    _ff([*inputs, "-filter_complex", ";".join(chains), "-map", last, "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-r", str(FPS), str(out)])


def render_scene(project: Project, cfg: Config, script: Script, state: ProjectState, scene: Scene, out: Path) -> None:
    w, h = canvas_size(script.aspect)
    picked, _ = _picked(state, scene)
    durs = planned_durations(script, state, scene)
    with tempfile.TemporaryDirectory(prefix="vidflow-render-") as td:
        tmp = Path(td)
        norm = []
        for i, (_, file) in enumerate(picked):
            p = tmp / f"n{i}.png"
            _cover(project.path(file), p, w, h)
            norm.append(p)
        if scene.mode == "stopmotion":
            listing = tmp / "stop.txt"
            body = "".join(f"file '{norm[i % len(norm)]}'\nduration {d:.6f}\n" for i, d in enumerate(durs))
            listing.write_text(body + f"file '{norm[(len(durs) - 1) % len(norm)]}'\n", encoding="utf-8")
            _ff(["-f", "concat", "-safe", "0", "-i", str(listing), "-vf", f"fps={FPS},format=yuv420p",
                 "-c:v", "libx264", "-t", f"{sum(durs):.3f}", str(out)])
            return
        if scene.mode == "comic" and not cfg.comic_font.is_file():
            raise VidflowError(f"Không thấy font bong bóng {cfg.comic_font}; đặt comic_font trong vidflow.toml.")
        transition = scene.transition
        extra = min(0.4, min(durs) / 2) if transition != "cut" and len(durs) > 1 else 0.0
        segs = []
        for i, ((frame, _), d) in enumerate(zip(picked, durs)):
            seg_len = d + (extra if i < len(durs) - 1 else 0.0)
            bubble = _bubble(frame.caption, script.aspect, w, h, cfg.comic_font, tmp, i) \
                if scene.mode == "comic" and frame.caption.strip() else None
            p = tmp / f"s{i}.mp4"
            _segment(norm[i], p, seg_len, frame.motion if scene.mode != "comic" or frame.motion else "static", w, h, bubble)
            segs.append(p)
        _join(segs, durs, transition, out)


def run_render(project: Project, cfg: Config, *, scene_ids: list[str] | None = None,
               now: Callable[[], str] = _now_iso) -> dict:
    if shutil.which("ffmpeg") is None:
        raise VidflowError("Cần cài ffmpeg (brew install ffmpeg).")
    script, state = project.load_script(), project.load_state()
    selected = script.scenes if not scene_ids else [script.scene(i) for i in scene_ids]
    created, skipped = [], {}
    for scene in selected:
        if scene.mode == "veo" or scene.status != "approved":
            continue
        if scene.assemble == "capcut":
            skipped[scene.id] = "ghép từng ảnh trong CapCut (không render)"
            continue
        picked, missing = _picked(state, scene)
        if missing or not picked:
            skipped[scene.id] = f"thiếu ảnh khung {', '.join(missing)}" if missing else "chưa có khung đã duyệt"
            continue
        h = render_hash(project, script, state, scene)
        st = state.scene(scene.id)
        if st.picked is not None and st.takes[st.picked].input_hash == h:
            continue
        out = project.clips_dir / f"{scene.id}_r{sum(t.source == 'render' for t in st.takes) + 1}.mp4"
        render_scene(project, cfg, script, state, scene, out)
        st.takes.append(Take(file=project.rel(out), input_hash=h, cost_usd=0.0, created_at=now(), source="render"))
        st.picked = len(st.takes) - 1
        project.save_state(state)
        created.append(project.rel(out))
    return {"created": created, "skipped": skipped}
