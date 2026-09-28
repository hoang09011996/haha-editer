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
            subtitles=subs,
        ))
        t = end
    return Timeline(scenes=tuple(plans), skipped=skipped, total=round(t, 3))
