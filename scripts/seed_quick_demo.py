"""Tạo project nhanh GIẢ LẬP để kiểm tra giao diện bằng tay — không gọi Flow, Gemini hay Claude.

    uv run python scripts/seed_quick_demo.py [tên]     → projects/<tên> (mặc định ui-demo; ghi đè nếu đã có)

Dùng bộ kênh thật `doodle-giai-ma` (chỉ đọc, không ghi vào presets/). Mọi ghi đi qua vidflow.quick.*.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
import wave
from array import array
from pathlib import Path

from PIL import Image, ImageDraw

from vidflow.quick import chars, clips, ops
from vidflow.quick.model import create_quick, load_beats, save_beats
from vidflow.quick.preset import load_preset

REPO = Path(__file__).resolve().parents[1]
RATE = 24000
TEXTS = [
    "Sáng thứ Hai. Chuông báo thức réo lần thứ ba.",
    "Bạn vùi dưới chăn, một mắt hé ra, tay mò tìm cái đồng hồ.",
    "Một đám mây xám nhỏ bắt đầu hình thành trên đầu bạn.",
    "Nhưng năm mươi nghìn năm trước, một buổi sáng trông rất khác.",
    "Tổ tiên của bạn thức dậy cạnh đống lửa đã tàn.",
    "Không chuông báo, không email, chỉ có tiếng chim.",
    "Rồi nông nghiệp ra đời, và mọi thứ thay đổi.",
    "Người nông dân còng lưng trên cánh đồng lúa mì.",
    "Bữa sáng? Một bát cháo lúa mì, ngày nào cũng vậy.",
    "Vậy ai mới là người có buổi sáng tệ hơn?",
]
CHARS = [
    {"id": "ANCESTOR", "name": "Tổ tiên", "desc": "upright hunter-gatherer in an animal-hide tunic, barefoot", "color": "#E09A2D"},
    {"id": "FARMER", "name": "Nông dân", "desc": "hunched neolithic farmer, rough tunic, wooden hoe", "color": "#8B5E3C"},
]


def png(path: Path, color: str, label: str, size: tuple[int, int] = (640, 360)) -> Path:
    img = Image.new("RGB", size, color)
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, size[0] - 20, size[1] - 20], outline="#111111", width=6)
    d.text((40, 40), label, fill="#111111")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def main(name: str = "ui-demo") -> None:
    root = REPO / "projects" / name
    if root.exists():
        shutil.rmtree(root)
    pr = load_preset("doodle-giai-ma")

    def P(s: str) -> str:
        return f"{pr.style_anchor_start} {s}, {pr.style_anchor_end}"

    create_quick(root, preset=pr.id, title="Ngày thường 50.000 năm trước")
    ops.set_ideas(root, [{"title": "Ngày thường 50.000 năm trước", "hook": "Buổi sáng của bạn và của tổ tiên",
                          "why_viral": "so sánh bất ngờ"},
                         {"title": "Vì sao ta sợ thứ Hai", "hook": "Não bộ và lịch làm việc", "why_viral": "ai cũng gặp"}])
    ops.pick_idea(root, 1)
    ops.set_beat_texts(root, TEXTS)
    chars.set_chars(root, CHARS)
    # giọng đọc giả: sóng sin theo mốc, điền start/end giống `quick voice` (chỉ cho project thử)
    beats = load_beats(root)
    pcm, t = array("h"), 0.0
    for i, b in enumerate(beats.beats):
        dur = 3.0 + (i % 3)
        n = int(dur * RATE)
        amp = 6000 + 2500 * (i % 4)
        pcm.extend(int(amp * math.sin(2 * math.pi * 180 * k / RATE) * (0.5 + 0.5 * math.sin(math.pi * k / n)))
                   for k in range(n))
        b.start, b.end = round(t, 3), round(t + dur, 3)
        t += dur
    save_beats(root, beats)
    with wave.open(str(root / "audio" / "voice.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    ops.advance(root, "voiced")
    ops.set_prompts(root, [
        {"n": 1, "prompt": P("a messy bedroom at dawn, alarm clock ringing"), "verdict": "pass", "score": 8.5},
        {"n": 2, "prompt": P("a person buried under a blanket, one eye open"), "verdict": "pass", "score": 8, "cont": True},
        {"n": 3, "prompt": P("a small grey cloud above the sleepy person"), "verdict": "pass", "score": 7.5, "cont": True},
        {"n": 4, "prompt": P("a sunrise over a prehistoric valley"), "verdict": "pass", "score": 8},
        {"n": 5, "prompt": P("@ANCESTOR waking beside a dying campfire"), "verdict": "pass", "score": 9},
        {"n": 6, "prompt": P("@ANCESTOR listening to birds"), "verdict": "fail", "score": 5, "cont": True,
         "issues": ["Thiếu bối cảnh — thêm cây và bầu trời sáng sớm"]},
        {"n": 7, "prompt": P("@FARMER looking at a wheat field"), "verdict": "pass", "score": 8},
        {"n": 8, "prompt": P("@FARMER bent over in the wheat field"), "verdict": "pass", "score": 8, "cont": True},
        {"n": 9, "prompt": P("a bowl of plain wheat porridge"), "verdict": "pass", "score": 7},
        {"n": 10, "prompt": P("@ANCESTOR and @FARMER side by side, question mark above"), "verdict": "pass", "score": 8},
    ])
    tmp = root / "tmp" / "seed"
    chars.set_char_image(root, "ANCESTOR", png(tmp / "ancestor.png", "#FBEBD3", "@ANCESTOR sheet"))
    for n, color in enumerate(["#4A6BE0", "#4A6BE0", "#4A6BE0", "#F0B65A", "#F0B65A"], 1):
        ops.set_image(root, n, png(tmp / f"b{n}.png", color, f"Moc {n:03d}"))
    ops.record_fail(root, 9, "Flow: prompt vi phạm chính sách nội dung (giả lập)")
    ops.update_settings(root, video_model="Veo 3.1 Lite", max_clips=3)
    clips.set_clip_prompts(root, [{"n": 2, "prompt": "frame-by-frame doodle motion: one eye cracks open. Sound: muffled alarm.",
                                   "verdict": "pass", "score": 8}])
    if shutil.which("ffmpeg"):
        mp4 = tmp / "clip.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24",
                        "-t", "4", "-pix_fmt", "yuv420p", str(mp4)], check=True)
        clips.set_clip(root, 2, mp4)
        shutil.copyfile(mp4, root / "out" / f"{name}-v1.mp4")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Đã tạo {root}")
    print(ops.format_status(ops.status_summary(root)))


if __name__ == "__main__":
    main(*sys.argv[1:2])
