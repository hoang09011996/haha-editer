"""Thử 3 kiểu làm ảnh doodle 'sống' hơn trong CapCut (40s đầu của samples/doodle-112).
A: rung nét (hiệu ứng 轻微抖动) + chuyển mờ nhanh 0.15s
B: A + nhún nhẹ khi ảnh xuất hiện
C: A + tiếng whoosh mỗi lần chuyển ảnh
Không phải code sản phẩm — dùng để người dùng so sánh."""
import shutil
import subprocess
import sys
from pathlib import Path

import pycapcut as cc

from vidflow.assemble import plan_images
from vidflow.capcut_draft import capcut_running, cover_scale
from vidflow.config import load_config

SECONDS = 40.0
W, H = 1920, 1080
cfg = load_config()
src = Path("samples/doodle-112")
plan = [p for p in plan_images(src) if p.start < SECONDS]
us = lambda s: round(s * 1_000_000)

if capcut_running():
    sys.exit("Thoát CapCut trước.")

media = cfg.media_folder / "vidflow_motion_test"
(media / "images").mkdir(parents=True, exist_ok=True)
for p in plan:
    shutil.copy2(p.file, media / "images" / p.file.name)
whoosh = media / "whoosh.wav"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anoisesrc=color=pink:duration=0.35:amplitude=0.6",
                "-af", "bandpass=f=1800:width_type=h:w=2500,afade=t=in:d=0.12,afade=t=out:st=0.15:d=0.2,volume=0.8",
                "-ar", "44100", str(whoosh)], check=True)

folder = cc.DraftFolder(str(cfg.draft_folder))
kp = cc.KeyframeProperty


def build(name: str, bounce: bool, sfx: bool) -> None:
    d = folder.create_draft(name, W, H, allow_replace=True)
    d.add_track(cc.TrackType.video)
    d.add_track(cc.TrackType.effect, "boil")
    if sfx:
        d.add_track(cc.TrackType.audio, "sfx")
    mats = {}
    for i, p in enumerate(plan):
        path = str(media / "images" / p.file.name)
        mat = mats.setdefault(path, cc.VideoMaterial(path))
        a, b = us(p.start), us(min(p.end, SECONDS))
        base = cover_scale(mat.width, mat.height, W, H)
        seg = cc.VideoSegment(mat, cc.Timerange(a, b - a), clip_settings=cc.ClipSettings(scale_x=base, scale_y=base), volume=0)
        if bounce:
            seg.add_keyframe(kp.uniform_scale, 0, base * 0.96)
            seg.add_keyframe(kp.uniform_scale, 120_000, base * 1.04)
            seg.add_keyframe(kp.uniform_scale, 260_000, base)
        if i < len(plan) - 1:
            seg.add_transition(cc.TransitionType["叠化"], duration=150_000)
        d.add_segment(seg)
        if sfx and i > 0:
            t = max(0, a - 100_000)
            d.add_segment(cc.AudioSegment(str(whoosh), cc.Timerange(t, 350_000), volume=0.45), "sfx")
    d.add_effect(cc.VideoSceneEffectType["轻微抖动"], cc.Timerange(0, us(SECONDS)), "boil", params=[18, 70])
    d.save()
    dd = cfg.draft_folder / name
    shutil.copy(dd / "draft_content.json", dd / "draft_info.json")
    print("✓", name)


build("vidflow_thu_A_rung_net", bounce=False, sfx=False)
build("vidflow_thu_B_rung_nhun", bounce=True, sfx=False)
build("vidflow_thu_C_rung_tiengdong", bounce=False, sfx=True)
print(len(plan), "ảnh, 40 giây đầu")
