import pytest

from vidflow.schema import Frame, Scene
from vidflow.state import FrameState, ImageTake, Take, TtsResult
from vidflow.timeline import plan_timeline


def image_scene(mode, n=3, *, sid="s01", narration="Ủa, chua thế!", assemble="capcut", seconds=1.0,
                approved=None, captions=None, motion="zoom_in", fps=8):
    frames = [Frame(id=f"f{i + 1:02d}", seconds=seconds, motion=motion,
                    caption=(captions[i] if captions else ""),
                    status="approved" if (approved is None or approved[i]) else "draft")
              for i in range(n)]
    return Scene(id=sid, narration=narration, status="approved", mode=mode, frames=frames, assemble=assemble,
                 fps=fps)


def pick_images(state, scene, *, missing=()):
    st = state.scene(scene.id)
    for f in scene.frames:
        if f.id in missing:
            continue
        st.frames[f.id] = FrameState(images=[ImageTake(file=f"frames/{scene.id}/{f.id}.png", input_hash="h",
                                                       created_at="t")], picked=0)
    return st


def setup(project, scene, voice_s=2.0, **kw):
    script = project.load_script()
    script.scenes = [scene]
    state = project.load_state()
    st = pick_images(state, scene, **kw)
    if voice_s is not None:
        st.tts = TtsResult(file="audio/s01.wav", duration_s=voice_s, input_hash="h")
    return script, state


def us(x):
    return round(x * 1_000_000)


def test_slideshow_voice_longer_stretches_frames(project):
    scene = image_scene("slideshow", 3, seconds=0.5)  # tổng 1.5s < 2.3s
    script, state = setup(project, scene, voice_s=2.0)
    tl = plan_timeline(script, state, {})
    assert tl.skipped == {}
    (p,) = tl.scenes
    assert (p.start, p.end) == (0.0, pytest.approx(2.3))
    assert [i.file for i in p.images] == ["frames/s01/f01.png", "frames/s01/f02.png", "frames/s01/f03.png"]
    assert p.images[0].start == 0.0 and us(p.images[-1].end) == us(p.end)
    assert all(us(a.end) == us(b.start) for a, b in zip(p.images, p.images[1:]))
    durs = [us(i.end) - us(i.start) for i in p.images]
    assert max(durs) - min(durs) <= 1
    assert p.voice == "audio/s01.wav" and p.subtitles
    assert tl.total == pytest.approx(2.3)


def test_slideshow_frames_longer_than_voice_keep_seconds(project):
    scene = image_scene("slideshow", 3, seconds=2.0)
    script, state = setup(project, scene, voice_s=2.0)
    (p,) = plan_timeline(script, state, {}).scenes
    assert p.end == pytest.approx(6.0)
    assert [round(i.end - i.start, 6) for i in p.images] == [2.0, 2.0, 2.0]
    assert [i.motion for i in p.images] == ["zoom_in"] * 3


def test_slideshow_without_narration(project):
    scene = image_scene("slideshow", 2, seconds=1.5, narration="")
    script, state = setup(project, scene, voice_s=None)
    (p,) = plan_timeline(script, state, {}).scenes
    assert p.end == pytest.approx(3.0) and p.voice is None and p.subtitles == ()


def test_stopmotion_loops_frames_at_fps(project):
    scene = image_scene("stopmotion", 4, fps=8, seconds=0.5)
    script, state = setup(project, scene, voice_s=2.0)
    (p,) = plan_timeline(script, state, {}).scenes
    assert p.end == pytest.approx(2.3)
    assert len(p.images) >= 18
    durs = [us(i.end) - us(i.start) for i in p.images]
    assert all(d == 125_000 for d in durs[:-1]) and 0 < durs[-1] <= 125_000
    assert sum(durs) == us(2.3)
    assert [i.file[-7:] for i in p.images[:6]] == ["f01.png", "f02.png", "f03.png", "f04.png", "f01.png", "f02.png"]
    assert all(i.motion == "static" for i in p.images)


def test_stopmotion_no_voice_plays_sequence_once(project):
    scene = image_scene("stopmotion", 4, fps=8, seconds=0.5, narration="")
    script, state = setup(project, scene, voice_s=None)
    (p,) = plan_timeline(script, state, {}).scenes
    # không lời dẫn: độ dài = tổng seconds (4×0.5s), chuỗi 4 ảnh lặp ở 8fps
    assert p.end == pytest.approx(2.0) and len(p.images) == 16


def test_comic_carries_captions(project):
    scene = image_scene("comic", 2, seconds=1.0, captions=["Ủa, chua thế!", "Ngon ghê!"])
    script, state = setup(project, scene, voice_s=2.0)
    (p,) = plan_timeline(script, state, {}).scenes
    assert [i.caption for i in p.images] == ["Ủa, chua thế!", "Ngon ghê!"]
    assert p.mode == "comic"


def test_missing_picked_image_skips_scene(project):
    scene = image_scene("slideshow", 4)
    script, state = setup(project, scene, missing=("f02", "f03"))
    state.scenes["s01"].frames["f03"] = FrameState(images=[], picked=None)
    tl = plan_timeline(script, state, {})
    assert tl.scenes == ()
    assert tl.skipped["s01"] == "thiếu ảnh khung f02, f03"


def test_unapproved_frame_without_image_ignored(project):
    scene = image_scene("slideshow", 3, approved=[True, False, True])
    script, state = setup(project, scene, missing=("f02",))
    (p,) = plan_timeline(script, state, {}).scenes
    assert [i.file[-7:] for i in p.images] == ["f01.png", "f03.png"]


def test_no_approved_frames_skips(project):
    scene = image_scene("slideshow", 2, approved=[False, False])
    script, state = setup(project, scene)
    tl = plan_timeline(script, state, {})
    assert "khung" in tl.skipped["s01"]


def test_capcut_image_scene_needs_voice_when_narrated(project):
    scene = image_scene("slideshow", 2)
    script, state = setup(project, scene, voice_s=None)
    assert plan_timeline(script, state, {}).skipped["s01"] == "chưa có voice-over"


def test_ffmpeg_image_scene_still_needs_picked_take(project):
    scene = image_scene("slideshow", 2, assemble="ffmpeg")
    script, state = setup(project, scene)
    assert plan_timeline(script, state, {}).skipped["s01"] == "chưa có clip"
    st = state.scenes["s01"]
    st.takes = [Take(file="clips/s01_render.mp4", input_hash="h", cost_usd=0, created_at="t", source="render")]
    st.picked = 0
    (p,) = plan_timeline(script, state, {"clips/s01_render.mp4": 4.0}).scenes
    assert p.clip == "clips/s01_render.mp4" and p.images == ()


def test_mixed_veo_and_capcut_image_scene_in_order(project):
    script = project.load_script()
    veo = script.scenes[1]  # s02, không lời dẫn, 4s
    img = image_scene("slideshow", 2, sid="s09", seconds=1.0, narration="")
    script.scenes = [veo, img]
    state = project.load_state()
    s2 = state.scene("s02")
    s2.takes = [Take(file="clips/s02_t1.mp4", input_hash="h", cost_usd=0, created_at="t")]
    s2.picked = 0
    pick_images(state, img)
    tl = plan_timeline(script, state, {"clips/s02_t1.mp4": 4.0})
    a, b = tl.scenes
    assert (a.scene_id, a.images) == ("s02", ())
    assert b.scene_id == "s09" and b.start == pytest.approx(4.0) and b.images[0].start == pytest.approx(4.0)
    assert tl.total == pytest.approx(6.0)
