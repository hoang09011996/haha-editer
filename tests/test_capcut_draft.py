import dataclasses
import json
import shutil

import pytest

from conftest import make_mp4, write_wav
from vidflow.capcut_draft import build_draft, canvas_size, draft_name
from vidflow.errors import CapCutRunningError, ConfigError, ScriptError, VidflowError
from vidflow.media import probe_duration
from vidflow.state import Take, TtsResult
from vidflow.timeline import plan_timeline

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")


def prepare(project, voice_s=2.0, clip_s=3.0):
    make_mp4(project.clips_dir / "s01_t1.mp4", clip_s)
    make_mp4(project.clips_dir / "s02_t1.mp4", 2)
    write_wav(project.audio_dir / "s01.wav", voice_s)
    state = project.load_state()
    s1 = state.scene("s01")
    s1.takes = [Take(file="clips/s01_t1.mp4", input_hash="h", cost_usd=0, created_at="t")]
    s1.picked = 0
    s1.tts = TtsResult(file="audio/s01.wav", duration_s=voice_s, input_hash="h")
    s2 = state.scene("s02")
    s2.takes = [Take(file="clips/s02_t1.mp4", input_hash="h", cost_usd=0, created_at="t")]
    s2.picked = 0
    project.save_state(state)
    return state


def durations(project, state):
    return {t.file: probe_duration(project.path(t.file)) for st in state.scenes.values() for t in st.takes}


def load_info(cfg, project):
    return json.loads((cfg.draft_folder / draft_name(project) / "draft_info.json").read_text(encoding="utf-8"))


def material_paths(content):
    return [m["path"] for kind in ("videos", "audios") for m in content["materials"][kind]]


def build(project, cfg, script, state, stamp="S1"):
    tl = plan_timeline(script, state, durations(project, state))
    return tl, build_draft(project, cfg, script, tl, is_running=lambda: False, stamp=lambda: stamp)


def test_canvas_size():
    assert canvas_size("9:16") == (1080, 1920)
    assert canvas_size("16:9") == (1920, 1080)


def test_build_creates_draft(project, cfg):
    state = prepare(project)
    script = project.load_script()
    _, path = build(project, cfg, script, state)
    assert path == cfg.draft_folder / "vidflow_demo"
    content = load_info(cfg, project)
    assert content == json.loads((path / "draft_content.json").read_text(encoding="utf-8"))
    assert content["canvas_config"]["width"] == 1080 and content["canvas_config"]["height"] == 1920
    by_type = {}
    for tr in content["tracks"]:
        by_type.setdefault(tr["type"], []).append(len(tr["segments"]))
    assert by_type["video"] == [2]
    assert by_type["audio"] == [1]
    assert sum(by_type["text"]) >= 1
    st = project.load_state()
    assert st.draft_path == str(path) and st.last_build_at


def test_media_copied_under_media_folder(project, cfg):
    state = prepare(project)
    build(project, cfg, project.load_script(), state)
    media_root = cfg.media_folder / "vidflow_demo"
    paths = material_paths(load_info(cfg, project))
    assert paths and all(p.startswith(str(media_root)) for p in paths)
    assert (media_root / "clips" / "s01_t1.mp4").is_file()
    assert (media_root / "audio" / "s01.wav").is_file()


def test_build_slowed_scenes_and_subtitles_no_overlap(project, cfg):
    state = prepare(project, voice_s=2.9, clip_s=3.0)  # cảnh 3.2s, clip 3.0s → tốc độ 0.9375
    script = project.load_script()
    script.subtitles.max_chars_per_line = 8
    tl, _ = build(project, cfg, script, state)
    assert tl.scenes[0].clip_speed < 1.0
    for tr in load_info(cfg, project)["tracks"]:
        segs = sorted(tr["segments"], key=lambda s: s["target_timerange"]["start"])
        for a, b in zip(segs, segs[1:]):
            assert a["target_timerange"]["start"] + a["target_timerange"]["duration"] <= b["target_timerange"]["start"]


def test_music_loops_to_total(project, cfg):
    state = prepare(project)
    write_wav(project.root / "music" / "bg.wav", 1.5)
    text = project.script_path.read_text(encoding="utf-8").replace("music: null", 'music: { file: music/bg.wav, volume: 0.2 }')
    project.script_path.write_text(text, encoding="utf-8")
    script = project.load_script()
    tl, _ = build(project, cfg, script, state)
    audio_tracks = [t for t in load_info(cfg, project)["tracks"] if t["type"] == "audio"]
    music = max(audio_tracks, key=lambda t: len(t["segments"]))
    total_us = sum(s["target_timerange"]["duration"] for s in music["segments"])
    assert len(music["segments"]) == 3
    assert total_us == round(tl.total * 1_000_000)


def test_missing_music_file(project, cfg):
    state = prepare(project)
    text = project.script_path.read_text(encoding="utf-8").replace("music: null", "music: { file: music/none.mp3 }")
    project.script_path.write_text(text, encoding="utf-8")
    script = project.load_script()
    tl = plan_timeline(script, state, durations(project, state))
    with pytest.raises(ScriptError, match="none.mp3"):
        build_draft(project, cfg, script, tl, is_running=lambda: False)


def test_refuses_when_capcut_running(project, cfg):
    state = prepare(project)
    script = project.load_script()
    tl = plan_timeline(script, state, durations(project, state))
    with pytest.raises(CapCutRunningError, match="Thoát CapCut"):
        build_draft(project, cfg, script, tl, is_running=lambda: True)


def test_backs_up_existing_draft(project, cfg):
    state = prepare(project)
    script = project.load_script()
    build(project, cfg, script, state, stamp="S1")
    build(project, cfg, script, state, stamp="S2")
    assert (project.backups_dir / "S2" / "vidflow_demo" / "draft_info.json").is_file()


def test_empty_timeline(project, cfg):
    script = project.load_script()
    tl = plan_timeline(script, project.load_state(), {})
    with pytest.raises(VidflowError, match="Không có cảnh"):
        build_draft(project, cfg, script, tl, is_running=lambda: False)


def test_missing_draft_folder(project, cfg, tmp_path):
    state = prepare(project)
    script = project.load_script()
    tl = plan_timeline(script, state, durations(project, state))
    with pytest.raises(ConfigError, match="draft_folder"):
        build_draft(project, dataclasses.replace(cfg, draft_folder=tmp_path / "nope"), script, tl,
                    is_running=lambda: False)


def test_clip_with_longer_audio_track_builds(project, cfg):
    """Veo MP4 có thể có track audio dài hơn video; phải đo theo track video."""
    import subprocess
    state = prepare(project)
    clip = project.clips_dir / "s02_t1.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=216x384:rate=30",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "2", "-map", "0:v", "-t", "2",
                    "-map", "1:a", "-t", "2.3", "-pix_fmt", "yuv420p", str(clip)], check=True)
    from vidflow.media import video_duration
    script = project.load_script()
    clips = {t.file: video_duration(project.path(t.file)) for st in state.scenes.values() for t in st.takes}
    tl = plan_timeline(script, state, clips)
    build_draft(project, cfg, script, tl, is_running=lambda: False, stamp=lambda: "S1")
