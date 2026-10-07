"""3 phiên bản dựng CapCut cho toàn bộ video doodle 112 ảnh, hiệu ứng chọn theo nội dung prompt từng ảnh.
A: rung nét + chuyển cảnh theo prompt + giật rung khi cảm xúc mạnh + đẩy máy chậm ảnh ≥5s + nảy ảnh có chữ
B: A + nảy nhẹ mọi ảnh
C: A + whoosh khi đổi cảnh, pop khi ảnh có chữ
Không phải code sản phẩm — để người dùng so sánh."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pycapcut as cc

from vidflow.assemble import plan_images
from vidflow.capcut_draft import capcut_running, cover_scale
from vidflow.config import load_config

W, H = 1920, 1080
ANCHOR = "slightly wobbly imperfect marker lines,"
EMO = re.compile(r"shock|panic|terrif|scream|startl|alarm|explod|horrif|furious|angry|frantic|sweat|tremb|scared|gasp", re.I)
us = lambda s: round(s * 1_000_000)
cfg = load_config()

if capcut_running():
    sys.exit("Thoát CapCut trước (Cmd+Q).")

plan = plan_images(Path("samples/doodle-112"))
prompts = re.findall(r"^\[(\d+):(\d+)\]\s*(.+)$", Path("samples/doodle-112-prompts.txt").read_text(encoding="utf-8"), re.M)
assert len(prompts) == len(plan), (len(prompts), len(plan))


def bg_key(p: str) -> str:
    m = re.search(r"((?:\w+[- ]){1,2}\w+) background", p.split(ANCHOR, 1)[-1])
    return m.group(1).split()[-1] if m else "?"


info = []
for (mm, ss, p), pl in zip(prompts, plan):
    assert int(mm) * 60 + int(ss) == int(pl.start), (mm, ss, pl.file.name)
    body = p.split(ANCHOR, 1)[-1][:220].lower()
    info.append({"same": "the same" in body, "text": bool(re.search(r'text "[^"]+"', p)) and "no on-screen text" not in p,
                 "emo": bool(EMO.search(p)), "bg": bg_key(p)})
for i, x in enumerate(info):
    x["new_scene"] = i > 0 and x["bg"] != info[i - 1]["bg"] and not x["same"]

media = cfg.media_folder / "vidflow_motion_test"
(media / "images").mkdir(parents=True, exist_ok=True)
for pl in plan:
    shutil.copy2(pl.file, media / "images" / pl.file.name)
sfx = {
    "whoosh": ("anoisesrc=color=pink:duration=0.35:amplitude=0.6",
               "bandpass=f=1800:width_type=h:w=2500,afade=t=in:d=0.12,afade=t=out:st=0.15:d=0.2,volume=0.8"),
    "pop": ("sine=frequency=880:duration=0.12", "afade=t=out:st=0.03:d=0.09,volume=0.6"),
}
for k, (src, af) in sfx.items():
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", src, "-af", af, "-ar", "44100", str(media / f"{k}.wav")], check=True)

folder = cc.DraftFolder(str(cfg.draft_folder))
kp, TT = cc.KeyframeProperty, cc.TransitionType
total = us(plan[-1].end)


def build(name: str, bounce_all: bool, with_sfx: bool) -> None:
    d = folder.create_draft(name, W, H, allow_replace=True)
    d.add_track(cc.TrackType.video)
    d.add_track(cc.TrackType.effect, "boil")
    d.add_track(cc.TrackType.effect, "shake")
    if with_sfx:
        d.add_track(cc.TrackType.audio, "sfx")
    mats = {}
    for i, (pl, x) in enumerate(zip(plan, info)):
        path = str(media / "images" / pl.file.name)
        mat = mats.setdefault(path, cc.VideoMaterial(path))
        a, b = us(pl.start), us(pl.end)
        dur = b - a
        base = cover_scale(mat.width, mat.height, W, H)
        seg = cc.VideoSegment(mat, cc.Timerange(a, dur), clip_settings=cc.ClipSettings(scale_x=base, scale_y=base), volume=0)
        if x["text"] or bounce_all:
            amp = 0.06 if x["text"] else 0.03
            seg.add_keyframe(kp.uniform_scale, 0, base * (1 - amp))
            seg.add_keyframe(kp.uniform_scale, 120_000, base * (1 + amp))
            seg.add_keyframe(kp.uniform_scale, 260_000, base)
            if dur >= 5_000_000:
                seg.add_keyframe(kp.uniform_scale, dur, base * 1.06)
        elif dur >= 5_000_000:
            seg.add_keyframe(kp.uniform_scale, 0, base)
            seg.add_keyframe(kp.uniform_scale, dur, base * 1.06)
        if i < len(plan) - 1:
            nxt = info[i + 1]
            if nxt["same"]:
                pass  # cắt thẳng: đổi tư thế như hoạt hình
            elif nxt["new_scene"]:
                seg.add_transition(TT["滑动"], duration=300_000)
            else:
                seg.add_transition(TT["叠化"], duration=120_000)
        d.add_segment(seg)
        if x["emo"]:
            d.add_effect(cc.VideoSceneEffectType["微震抖动"], cc.Timerange(a, min(500_000, dur)), "shake", params=[60, 30, 70])
        if with_sfx and i > 0:
            if x["new_scene"]:
                d.add_segment(cc.AudioSegment(str(media / "whoosh.wav"), cc.Timerange(max(0, a - 120_000), 350_000), volume=0.45), "sfx")
            elif x["text"]:
                d.add_segment(cc.AudioSegment(str(media / "pop.wav"), cc.Timerange(a, 120_000), volume=0.5), "sfx")
    d.add_effect(cc.VideoSceneEffectType["轻微抖动"], cc.Timerange(0, total), "boil", params=[18, 70])
    d.save()
    dd = cfg.draft_folder / name
    shutil.copy(dd / "draft_content.json", dd / "draft_info.json")
    print("✓", name)


build("vidflow_thu_A_rung_net", bounce_all=False, with_sfx=False)
build("vidflow_thu_B_rung_nhun", bounce_all=True, with_sfx=False)
build("vidflow_thu_C_rung_tiengdong", bounce_all=False, with_sfx=True)
print(f"{len(plan)} ảnh, {plan[-1].end:.0f}s · đổi cảnh {sum(x['new_scene'] for x in info)} · cùng cảnh {sum(x['same'] for x in info)} · có chữ {sum(x['text'] for x in info)} · cảm xúc mạnh {sum(x['emo'] for x in info)}")
