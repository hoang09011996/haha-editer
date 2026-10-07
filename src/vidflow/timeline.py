from __future__ import annotations

from dataclasses import dataclass

from vidflow.inputs import MIN_CLIP_SPEED, SCENE_PAD_S
from vidflow.media import floor_ms
from vidflow.schema import Script
from vidflow.state import ProjectState


@dataclass(frozen=True)
class Subtitle:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class ImagePlan:
    """Một ảnh đặt trực tiếp trên track video của draft (cảnh ảnh assemble=capcut)."""
    file: str
    start: float          # giây, làm tròn µs; ảnh kế tiếp bắt đầu đúng tại end của ảnh trước
    end: float
    motion: str = "static"
    caption: str = ""


@dataclass(frozen=True)
class ScenePlan:
    scene_id: str
    start: float
    end: float
    clip: str
    clip_len: float      # độ dài lấy từ clip nguồn (giây)
    clip_speed: float
    clip_volume: float
    voice: str | None
    voice_len: float     # độ dài voice trên timeline (giây, đã tính speed)
    voice_speed: float
    subtitles: tuple[Subtitle, ...]
    mode: str = "veo"
    transition: str = "cut"
    images: tuple[ImagePlan, ...] = ()  # khác rỗng → dựng từng ảnh thay cho clip


@dataclass(frozen=True)
class Timeline:
    scenes: tuple[ScenePlan, ...]
    skipped: dict[str, str]
    total: float


def split_subtitle(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for w in text.split():
        while len(w) > max_chars:
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(w[:max_chars])
            w = w[max_chars:]
        if not w:
            continue
        cand = f"{cur} {w}" if cur else w
        if len(cand) <= max_chars:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _subtitles(text: str, max_chars: int, start: float, voice_len: float) -> tuple[Subtitle, ...]:
    lines = split_subtitle(text, max_chars)
    total = sum(len(l) for l in lines)
    out, acc = [], 0
    for line in lines:
        s = round(start + voice_len * acc / total, 3)
        acc += len(line)
        e = round(start + voice_len * acc / total, 3)
        out.append(Subtitle(s, e, line))
    return tuple(out)


IMAGE_MODES = ("slideshow", "stopmotion", "comic")


def _boundaries(start: float, durations: list[float]) -> list[float]:
    """Mốc thời gian chung (làm tròn µs) để các ảnh liền nhau không chồng lấn."""
    out, acc = [round(start, 6)], start
    for d in durations:
        acc += d
        out.append(round(acc, 6))
    return out


def _plan_images(scene, frames, files: list[str], start: float, length: float) -> tuple[ImagePlan, ...]:
    end = round(start + length, 3)
    if scene.mode == "stopmotion":
        step = 1 / scene.fps
        bounds, k = [], 0
        while start + k * step < end - 0.001:
            bounds.append(round(start + k * step, 6))
            k += 1
        bounds.append(end)
        return tuple(ImagePlan(files[i % len(files)], a, b) for i, (a, b) in enumerate(zip(bounds, bounds[1:])))
    total = sum(f.seconds for f in frames)
    bounds = _boundaries(start, [length * f.seconds / total for f in frames])
    bounds[-1] = end
    return tuple(ImagePlan(file, a, b, motion=f.motion, caption=f.caption)
                 for f, file, a, b in zip(frames, files, bounds, bounds[1:]))


def _picked_images(scene, st) -> tuple[list, list[str], list[str]]:
    frames, files, missing = [], [], []
    for f in scene.frames:
        if f.status != "approved":
            continue
        fs = st.frames.get(f.id) if st else None
        if fs is None or fs.picked is None or not (0 <= fs.picked < len(fs.images)):
            missing.append(f.id)
            continue
        frames.append(f)
        files.append(fs.images[fs.picked].file)
    return frames, files, missing


def plan_timeline(script: Script, state: ProjectState, clip_durations: dict[str, float], *,
                  pad: float = SCENE_PAD_S, min_speed: float = MIN_CLIP_SPEED) -> Timeline:
    t = 0.0
    plans: list[ScenePlan] = []
    skipped: dict[str, str] = {}
    for scene in script.scenes:
        if scene.status != "approved":
            skipped[scene.id] = "chưa approved"
            continue
        st = state.scenes.get(scene.id)
        if scene.mode in IMAGE_MODES and scene.assemble == "capcut":
            frames, files, missing = _picked_images(scene, st)
            if missing:
                skipped[scene.id] = f"thiếu ảnh khung {', '.join(missing)}"
                continue
            if not frames:
                skipped[scene.id] = "chưa có khung đã duyệt"
                continue
            has_voice = bool(scene.narration.strip())
            if has_voice and st.tts is None:
                skipped[scene.id] = "chưa có voice-over"
                continue
            voice_len = floor_ms(st.tts.duration_s / script.voice.speed) if has_voice else 0.0
            base = len(frames) / scene.fps if scene.mode == "stopmotion" else sum(f.seconds for f in frames)
            length = round(max(base, voice_len + pad if has_voice else 0.0), 3)
            start, end = round(t, 3), round(t + length, 3)
            subs = _subtitles(scene.narration, script.subtitles.max_chars_per_line, start, voice_len) \
                if has_voice and script.subtitles.enabled else ()
            plans.append(ScenePlan(
                scene_id=scene.id, start=start, end=end, clip="", clip_len=round(end - start, 3), clip_speed=1.0,
                clip_volume=0.0, voice=st.tts.file if has_voice else None, voice_len=voice_len,
                voice_speed=script.voice.speed, subtitles=subs, mode=scene.mode,
                transition=scene.transition if scene.mode == "slideshow" else "cut",
                images=_plan_images(scene, frames, files, start, end - start),
            ))
            t = end
            continue
        if st is None or st.picked is None:
            skipped[scene.id] = "chưa có clip"
            continue
        clip = st.takes[st.picked].file
        clip_len = floor_ms(clip_durations[clip])
        has_voice = bool(scene.narration.strip())
        if has_voice and st.tts is None:
            skipped[scene.id] = "chưa có voice-over"
            continue
        voice_len = floor_ms(st.tts.duration_s / script.voice.speed) if has_voice else 0.0
        length = round(voice_len + pad, 3) if has_voice else clip_len
        if clip_len >= length:
            speed, src = 1.0, length
        else:
            speed = clip_len / length
            if speed < min_speed:
                skipped[scene.id] = (f"lời dẫn {length:.1f}s dài hơn clip {clip_len:.1f}s "
                                     f"(cần tốc độ {speed:.2f} < {min_speed})")
                continue
            src = clip_len
        start, end = round(t, 3), round(t + length, 3)
        subs = _subtitles(scene.narration, script.subtitles.max_chars_per_line, start, voice_len) \
            if has_voice and script.subtitles.enabled else ()
        plans.append(ScenePlan(
            scene_id=scene.id, start=start, end=end, clip=clip, clip_len=src, clip_speed=speed,
            clip_volume=1.0 if scene.veo_audio else 0.0,
            voice=st.tts.file if has_voice else None, voice_len=voice_len, voice_speed=script.voice.speed,
            subtitles=subs, mode=scene.mode,
        ))
        t = end
    return Timeline(scenes=tuple(plans), skipped=skipped, total=round(t, 3))
