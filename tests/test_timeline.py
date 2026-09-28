import pytest

from vidflow.state import Take, TtsResult
from vidflow.timeline import plan_timeline, split_subtitle


def test_split_by_words():
    assert split_subtitle("Mỗi sáng, An bắt đầu ngày mới.", 12) == ["Mỗi sáng, An", "bắt đầu ngày", "mới."]


def test_split_hard_wraps_long_word():
    assert split_subtitle("ab supercalifragilistic cd", 8) == ["ab", "supercal", "ifragili", "stic cd"]


def test_split_empty():
    assert split_subtitle("   ", 10) == []


def setup_state(project, voice_s=None, clip="clips/s01_t1.mp4"):
    state = project.load_state()
    st = state.scene("s01")
    st.takes = [Take(file=clip, input_hash="h", cost_usd=0, created_at="t")]
    st.picked = 0
    if voice_s is not None:
        st.tts = TtsResult(file="audio/s01.wav", duration_s=voice_s, input_hash="h")
    s2 = state.scene("s02")
    s2.takes = [Take(file="clips/s02_t1.mp4", input_hash="h", cost_usd=0, created_at="t")]
    s2.picked = 0
    return state


def test_clip_longer_than_voice_is_trimmed(project):
    script = project.load_script()
    tl = plan_timeline(script, setup_state(project, voice_s=5.0), {"clips/s01_t1.mp4": 8.0, "clips/s02_t1.mp4": 4.0})
    s1, s2 = tl.scenes
    assert (s1.start, s1.end, s1.clip_speed, s1.clip_len) == (0.0, 5.3, 1.0, 5.3)
    assert s1.voice == "audio/s01.wav" and s1.voice_len == 5.0
    assert s1.clip_volume == 0.0
    assert s1.subtitles[0].start == 0.0
    assert s1.subtitles[-1].end == pytest.approx(5.0)
    assert all(a.end == b.start for a, b in zip(s1.subtitles, s1.subtitles[1:]))
    assert tl.skipped == {"s03": "chưa approved"}
    assert tl.total == pytest.approx(9.3)


def test_scene_without_narration_uses_clip_length(project):
    script = project.load_script()
    tl = plan_timeline(script, setup_state(project, voice_s=5.0), {"clips/s01_t1.mp4": 8.0, "clips/s02_t1.mp4": 3.999})
    s2 = tl.scenes[1]
    assert (s2.start, s2.end) == (5.3, pytest.approx(9.299))
    assert s2.voice is None and s2.subtitles == ()


def test_slow_down_within_limit(project):
    script = project.load_script()
    tl = plan_timeline(script, setup_state(project, voice_s=8.5), {"clips/s01_t1.mp4": 8.0, "clips/s02_t1.mp4": 4.0})
    s1 = tl.scenes[0]
    assert s1.end == pytest.approx(8.8)
    assert s1.clip_len == 8.0
    assert s1.clip_speed == pytest.approx(8.0 / 8.8)


def test_too_long_voice_skips_scene(project):
    script = project.load_script()
    tl = plan_timeline(script, setup_state(project, voice_s=11.0), {"clips/s01_t1.mp4": 8.0, "clips/s02_t1.mp4": 4.0})
    assert "s01" in tl.skipped and "dài hơn clip" in tl.skipped["s01"]
    assert tl.scenes[0].scene_id == "s02" and tl.scenes[0].start == 0.0


def test_missing_voice_or_clip(project):
    script = project.load_script()
    state = setup_state(project, voice_s=None)
    state.scenes["s02"].picked = None
    tl = plan_timeline(script, state, {"clips/s01_t1.mp4": 8.0})
    assert tl.skipped["s01"] == "chưa có voice-over"
    assert tl.skipped["s02"] == "chưa có clip"
    assert tl.scenes == ()


def test_voice_speed_and_subtitles_disabled(project):
    script = project.load_script()
    script.voice.speed = 1.25
    script.subtitles.enabled = False
    tl = plan_timeline(script, setup_state(project, voice_s=5.0), {"clips/s01_t1.mp4": 8.0, "clips/s02_t1.mp4": 4.0})
    s1 = tl.scenes[0]
    assert s1.voice_len == 4.0 and s1.voice_speed == 1.25
    assert s1.end == pytest.approx(4.3)
    assert s1.subtitles == ()


def test_veo_audio_keeps_clip_volume(project):
    script = project.load_script()
    script.scenes[1].veo_audio = True
    tl = plan_timeline(script, setup_state(project, voice_s=5.0), {"clips/s01_t1.mp4": 8.0, "clips/s02_t1.mp4": 4.0})
    assert tl.scenes[1].clip_volume == 1.0
