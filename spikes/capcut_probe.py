"""Tạo draft thử 'vidflow_probe' (9:16) với video, voice, nhạc, text để mở trong CapCut 9.5."""
import subprocess
import sys
from pathlib import Path

import pycapcut as cc
from pycapcut import trange_seconds

DRAFTS = Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
# CapCut bị sandbox: chỉ đọc được ~/Movies → media phải nằm dưới ~/Movies
OUT = Path.home() / "Movies" / "vidflow_media" / "probe"
OUT.mkdir(parents=True, exist_ok=True)

video = OUT / "probe.mp4"
tone = OUT / "probe.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30",
                "-t", "4", "-pix_fmt", "yuv420p", str(video)], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=24000",
                "-t", "3", "-ac", "1", str(tone)], check=True)

if subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
    sys.exit("Thoát CapCut trước khi chạy probe.")

folder = cc.DraftFolder(str(DRAFTS))
draft = folder.create_draft("vidflow_probe", 1080, 1920, allow_replace=True)
draft.add_track(cc.TrackType.video)
draft.add_track(cc.TrackType.audio, "voice")
draft.add_track(cc.TrackType.audio, "music")
draft.add_track(cc.TrackType.text, "subs")
draft.add_segment(cc.VideoSegment(str(video), trange_seconds(0, duration=3.5),
                                  source_timerange=trange_seconds(0, duration=3.0), speed=3.0 / 3.5, volume=0.0))
draft.add_segment(cc.AudioSegment(str(tone), trange_seconds(0, duration=3.0)), "voice")
music = cc.AudioMaterial(str(tone))
print("AudioMaterial.duration (µs):", music.duration)
draft.add_segment(cc.AudioSegment(music, trange_seconds(0, duration=3.0), volume=0.15), "music")
draft.add_segment(cc.TextSegment("Xin chào vidflow — tiếng Việt có dấu", trange_seconds(0, duration=3.5),
                                 style=cc.TextStyle(size=8.0, align=1, auto_wrapping=True),
                                 clip_settings=cc.ClipSettings(transform_y=-0.7)), "subs")
draft.save()
print("Đã tạo draft:", DRAFTS / "vidflow_probe")

# CapCut 9.5 macOS đọc draft_info.json (không phải draft_content.json) — ghi thêm bản sao
import shutil
probe_dir = DRAFTS / "vidflow_probe"
shutil.copy(probe_dir / "draft_content.json", probe_dir / "draft_info.json")
print("files:", sorted(p.name for p in probe_dir.iterdir()))
