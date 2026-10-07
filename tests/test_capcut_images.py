import json
import shutil
import subprocess

import pytest

from conftest import make_mp4, write_wav
from vidflow.capcut_draft import build_draft, draft_name
from vidflow.schema import Frame, Scene
from vidflow.state import FrameState, ImageTake, Take, TtsResult
from vidflow.timeline import plan_timeline

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")

COLORS = ["red", "green", "blue", "yellow"]


def make_png(path, color="red", size="400x300"):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s={size}",
                    "-frames:v", "1", str(path)], check=True)
    return path


def image_scene(mode, n, *, sid="s01", narration="Ủa, chua thế!", seconds=1.0, motion="zoom_in", captions=None,
                transition="fade", fps=8):
    frames = [Frame(id=f"f{i + 1:02d}", seconds=seconds, motion=motion, status="approved",
                    caption=captions[i] if captions else "") for i in range(n)]
    return Scene(id=sid, narration=narration, status="approved", mode=mode, frames=frames, assemble="capcut",
                 transition=transition, fps=fps)


def prepare(project, scenes, voice_s=2.0, veo_clip=False):
    script = project.load_script()
    veo = [s for s in script.scenes if s.id == "s02"]
    script.scenes = (veo if veo_clip else []) + scenes
    state = project.load_state()
    if veo_clip:
        make_mp4(project.clips_dir / "s02_t1.mp4", 2)
        s2 = state.scene("s02")
        s2.takes = [Take(file="clips/s02_t1.mp4", input_hash="h", cost_usd=0, created_at="t")]
        s2.picked = 0
    for sc in scenes:
        st = state.scene(sc.id)
        for i, f in enumerate(sc.frames):
            rel = f"frames/{sc.id}/{f.id}.png"
            make_png(project.path(rel), COLORS[i % len(COLORS)])
            st.frames[f.id] = FrameState(images=[ImageTake(file=rel, input_hash="h", created_at="t")], picked=0)
        if sc.narration:
            write_wav(project.audio_dir / f"{sc.id}.wav", voice_s)
            st.tts = TtsResult(file=f"audio/{sc.id}.wav", duration_s=voice_s, input_hash="h")
    project.save_state(state)
    return script, state


def build(project, cfg, script, state):
    clips = {"clips/s02_t1.mp4": 2.0} if "s02" in state.scenes and state.scenes["s02"].picked is not None else {}
    tl = plan_timeline(script, state, clips)
    build_draft(project, cfg, script, tl, is_running=lambda: False, stamp=lambda: "S1")
    return tl, json.loads((cfg.draft_folder / draft_name(project) / "draft_info.json").read_text(encoding="utf-8"))


def video_segs(content):
    (track,) = [t for t in content["tracks"] if t["type"] == "video"]
    return sorted(track["segments"], key=lambda s: s["target_timerange"]["start"])


def videos_by_id(content):
    return {m["id"]: m for m in content["materials"]["videos"]}


def assert_no_overlap(content):
    for tr in content["tracks"]:
        segs = sorted(tr["segments"], key=lambda s: s["target_timerange"]["start"])
        for a, b in zip(segs, segs[1:]):
            assert a["target_timerange"]["start"] + a["target_timerange"]["duration"] <= b["target_timerange"]["start"]


def keyframes(seg):
    return {k["property_type"]: [kf["values"][0] for kf in k["keyframe_list"]] for k in seg["common_keyframes"]}


def texts(content):
    return [json.loads(m["content"])["text"] for m in content["materials"]["texts"]]


def test_slideshow_three_images_contiguous(project, cfg):
    script, state = prepare(project, [image_scene("slideshow", 3, seconds=0.5)], voice_s=2.0)
    tl, content = build(project, cfg, script, state)
    segs = video_segs(content)
    assert len(segs) == 3
    assert segs[0]["target_timerange"]["start"] == 0
    for a, b in zip(segs, segs[1:]):
        assert a["target_timerange"]["start"] + a["target_timerange"]["duration"] == b["target_timerange"]["start"]
    total = sum(s["target_timerange"]["duration"] for s in segs)
    assert abs(total - 2_300_000) <= 1
    vids = videos_by_id(content)
    paths = [vids[s["material_id"]]["path"] for s in segs]
    media_root = cfg.media_folder / draft_name(project)
    assert paths == [str(media_root / "frames" / "s01" / f"f0{i}.png") for i in (1, 2, 3)]
    assert all(vids[s["material_id"]]["type"] == "photo" for s in segs)
    assert_no_overlap(content)


def test_slideshow_fade_transition_except_last(project, cfg):
    script, state = prepare(project, [image_scene("slideshow", 3, transition="fade")])
    _, content = build(project, cfg, script, state)
    trans = {t["id"]: t for t in content["materials"]["transitions"]}
    segs = video_segs(content)
    used = [[trans[r]["name"] for r in s["extra_material_refs"] if r in trans] for s in segs]
    assert used == [["叠化"], ["叠化"], []]
    for s in segs[:-1]:
        t = trans[[r for r in s["extra_material_refs"] if r in trans][0]]
        assert t["duration"] <= s["target_timerange"]["duration"] // 2


def test_slide_and_cut_transitions(project, cfg):
    a = image_scene("slideshow", 2, sid="s05", transition="slide", narration="")
    b = image_scene("slideshow", 2, sid="s06", transition="cut", narration="")
    script, state = prepare(project, [a, b])
    _, content = build(project, cfg, script, state)
    names = [t["name"] for t in content["materials"]["transitions"]]
    assert names == ["滑动"]


def test_stopmotion_loops_eighth_second_frames(project, cfg):
    script, state = prepare(project, [image_scene("stopmotion", 4, fps=8)], voice_s=2.0)
    _, content = build(project, cfg, script, state)
    segs = video_segs(content)
    assert len(segs) >= 18
    durs = [s["target_timerange"]["duration"] for s in segs]
    assert all(d == 125_000 for d in durs[:-1])
    assert sum(durs) == 2_300_000
    assert all(not s["common_keyframes"] for s in segs)
    assert content["materials"]["transitions"] == []
    assert len(content["materials"]["videos"]) == 4  # mỗi ảnh một material, dùng lại khi lặp
    assert_no_overlap(content)


def test_comic_captions_on_bubble_track(project, cfg):
    caps = ["Ủa, chua thế!", "Ngon ghê!"]
    script, state = prepare(project, [image_scene("comic", 2, captions=caps, narration="")])
    _, content = build(project, cfg, script, state)
    assert texts(content) == caps
    text_tracks = [t for t in content["tracks"] if t["type"] == "text"]
    assert [t["name"] for t in text_tracks] == ["bubbles"]
    (bubbles,) = text_tracks
    segs = video_segs(content)
    for img, cap in zip(segs, sorted(bubbles["segments"], key=lambda s: s["target_timerange"]["start"])):
        assert cap["target_timerange"] == img["target_timerange"]
        assert cap["clip"]["transform"]["y"] == pytest.approx(0.7)
    mats = content["materials"]["texts"]
    assert all(m["background_alpha"] == 1.0 and m["background_color"].lower() == "#ffffff" for m in mats)
    styles = [json.loads(m["content"])["styles"][0] for m in mats]
    assert all(st["fill"]["content"]["solid"]["color"] == [0.0, 0.0, 0.0] for st in styles)
    assert all(m["check_flag"] & 0 == 0 for m in mats)
    assert_no_overlap(content)


def test_comic_with_narration_keeps_subtitles(project, cfg):
    script, state = prepare(project, [image_scene("comic", 2, captions=["Ủa, chua thế!", ""])], voice_s=2.0)
    _, content = build(project, cfg, script, state)
    names = sorted(t["name"] for t in content["tracks"] if t["type"] == "text")
    assert names == ["bubbles", "subs"]
    assert "Ủa, chua thế!" in texts(content)
    assert_no_overlap(content)


def test_zoom_in_keyframes_and_cover_scale(project, cfg):
    script, state = prepare(project, [image_scene("slideshow", 1, motion="zoom_in", narration="", seconds=2.0)])
    _, content = build(project, cfg, script, state)
    (seg,) = video_segs(content)
    cover = (1920 / 300) / (1080 / 400)  # ảnh 400x300 phủ kín canvas 1080x1920
    kf = keyframes(seg)
    assert kf["KFTypeScaleX"] == pytest.approx([cover, cover * 1.15])
    offsets = [k["time_offset"] for k in seg["common_keyframes"][0]["keyframe_list"]]
    assert offsets == [0, seg["target_timerange"]["duration"]]


def test_static_has_no_keyframes_but_covers(project, cfg):
    script, state = prepare(project, [image_scene("slideshow", 1, motion="static", narration="", seconds=2.0)])
    _, content = build(project, cfg, script, state)
    (seg,) = video_segs(content)
    assert seg["common_keyframes"] == []
    cover = (1920 / 300) / (1080 / 400)
    assert seg["clip"]["scale"]["x"] == pytest.approx(cover) and seg["clip"]["scale"]["y"] == pytest.approx(cover)


@pytest.mark.parametrize("motion,prop,values", [
    ("pan_left", "KFTypePositionX", [0.1, -0.1]),
    ("pan_right", "KFTypePositionX", [-0.1, 0.1]),
    ("pan_up", "KFTypePositionY", [-0.1, 0.1]),
    ("pan_down", "KFTypePositionY", [0.1, -0.1]),
])
def test_pan_keyframes(project, cfg, motion, prop, values):
    script, state = prepare(project, [image_scene("slideshow", 1, motion=motion, narration="", seconds=2.0)])
    _, content = build(project, cfg, script, state)
    (seg,) = video_segs(content)
    kf = keyframes(seg)
    assert kf[prop] == pytest.approx(values)
    assert seg["clip"]["scale"]["x"] == pytest.approx((1920 / 300) / (1080 / 400) * 1.15)


def test_zoom_out_keyframes(project, cfg):
    script, state = prepare(project, [image_scene("slideshow", 1, motion="zoom_out", narration="", seconds=2.0)])
    _, content = build(project, cfg, script, state)
    cover = (1920 / 300) / (1080 / 400)
    assert keyframes(video_segs(content)[0])["KFTypeScaleX"] == pytest.approx([cover * 1.15, cover])


def test_mixed_veo_and_slideshow_in_order(project, cfg):
    img = image_scene("slideshow", 2, sid="s09", seconds=1.0, narration="")
    script, state = prepare(project, [img], veo_clip=True)
    tl, content = build(project, cfg, script, state)
    assert [p.scene_id for p in tl.scenes] == ["s02", "s09"]
    segs = video_segs(content)
    vids = videos_by_id(content)
    assert [vids[s["material_id"]]["path"].rsplit("/", 1)[-1] for s in segs] == ["s02_t1.mp4", "f01.png", "f02.png"]
    assert segs[1]["target_timerange"]["start"] == segs[0]["target_timerange"]["duration"] == 2_000_000
    assert sum(s["target_timerange"]["duration"] for s in segs) == 4_000_000
    assert_no_overlap(content)
