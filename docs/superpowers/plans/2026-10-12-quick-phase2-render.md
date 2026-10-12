# Quick pipeline — Xuất MP4 bằng Remotion + draft CapCut nhận clip (Giai đoạn 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `vidflow quick render` xuất `projects/<tên>/out/<tên>-vN.mp4` bằng Remotion (clip động, chuyển cảnh theo `cont`, zoom, phụ đề, logo, nhạc nền), và `quick build` (draft CapCut) dùng clip `ok` thay cho ảnh ở mốc có clip.

**Architecture:** Python chia hai lớp trong module mới `src/vidflow/quick/render.py`: (1) `build_render_props` thuần — đọc `quick.yaml` + `beats.json` + file trên đĩa, trả `RenderPlan(props, assets, warnings)` (test đầy đủ, không cần Node); (2) runner mỏng — ghi `tmp/render-props.json`, dựng public dir bằng symlink, gọi `npx remotion render` (test bằng `run` giả, KHÔNG chạy Remotion trong pytest). `remotion/src/DoodleVideo.tsx` đọc props mới (mốc `image|video|blank`, `fade`, `rate`, `clipLen`, logo, nhạc). CapCut: `assemble(..., clips={n: path})` thay segment ảnh bằng segment video; `build_quick` lấy clip qua `clips.ready_clips` (dùng chung với render).

**Tech Stack:** Python 3.11, pydantic v2, typer, pytest (`uv run pytest`), pyCapCut; Remotion 4.0.534 (`remotion`, `@remotion/cli`), React 19, TypeScript, Node v25 (`npx`); ffmpeg/ffprobe.

**Spec:** `docs/superpowers/specs/2026-10-12-quick-refs-clips-ui-design.md` (Giai đoạn 2 — Xuất video).

## Global Constraints

- Không chạy `vidflow gen`, `vidflow estimate`, `vidflow refimg`; xuất video không gọi API trả phí nào.
- Không sửa tay `quick.yaml`, `beats.json`, `state.json`. `quick render` chỉ ĐỌC hai file đó; chỉ ghi vào `projects/<tên>/tmp/` và `projects/<tên>/out/`.
- Lệnh: `vidflow quick render -p <project> [--resolution 1080p|720p] [--transition scene|cut|fade] [--clip-fit trim|speed] [--zoom/--no-zoom] [--subtitles/--no-subtitles] [--clip-audio/--no-clip-audio] [--logo/--no-logo] [--music/--no-music]`.
- Props: `projects/<tên>/tmp/render-props.json`; video ra: `projects/<tên>/out/<tên>-vN.mp4` (N tăng dần, không ghi đè).
- FPS 30; `1080p` → 1920×1080, `720p` → 1280×720 cho 16:9; 9:16 đảo chiều (1080×1920, 720×1280).
- `transition=scene` (mặc định): mốc `cont` cắt thẳng, mốc mở cảnh mới mờ chéo 0.3 giây.
- Nhạc: `audio/music.(mp3|wav)` nếu có, âm lượng thấp dưới giọng. Logo: trường `logo` của `presets/<id>.yaml` (đã có trong `Preset`).
- `remotion` và `@remotion/cli` khóa đúng phiên bản `4.0.534` (không `latest`, không `^`).
- Remotion chạy trong `remotion/` (`cwd`), mọi đường dẫn truyền cho nó là tuyệt đối.
- Draft CapCut: ràng buộc sandbox `~/Movies` (copy media vào `media_folder/<draft>/`) và "CapCut phải đóng" giữ nguyên; `vidflow quick build` giữ nguyên tùy chọn CLI.
- Thông báo lỗi tiếng Việt, ném `VidflowError` (CLI in đỏ, exit 1, không traceback).
- Test không ghi vào `presets/` thật — dùng fixture `quick_presets`; test cần ffmpeg đánh dấu `needs_ffmpeg`.

Quyết định / lệch nhỏ so với spec (đã cân nhắc, ghi rõ để người duyệt biết):
- `--public-dir` trỏ vào `projects/<tên>/tmp/render/public/` — thư mục chỉ chứa symlink tới đúng các file cần (cùng đường dẫn tương đối như trong project: `images/…`, `clips/…`, `audio/…`, `logo/…`), KHÔNG phải gốc project: Remotion copy toàn bộ public dir vào bundle mỗi lần render (`@remotion/bundler` `copyDir`, symlink được giữ nguyên), trỏ vào gốc project sẽ copy cả `out/` chứa các bản MP4 cũ.
- Mỗi mốc trong props: `{n, src, kind, start, end, cont, fade, rate, clipLen}`; `kind` thêm giá trị `blank` (`src: null`) cho mốc chưa có ảnh.
- `end` hiển thị của mốc = `start` của mốc sau (khoảng lặng 0.15 s giữa các câu không thành khung trống); mốc cuối kéo tới hết video. Độ dài video = max(độ dài `voice.wav`, `end` của mốc cuối). Phụ đề dùng `start/end` thật của câu.
- `--resolution` mặc định = `flow.resolution` của `quick.yaml` (mặc định 720p).
- Clip được dùng khi `clip.enabled` + `clip.status == "ok"` + file còn trên đĩa (tắt clip bằng `clip off` → quay về ảnh). Ảnh được dùng khi file ảnh còn trên đĩa, kể cả mốc đang `redo` (ảnh cũ tốt hơn khung trống).
- `clip-fit=speed`: tốc độ = độ dài clip / độ dài mốc, kẹp trong [0.5, 2.0] kèm cảnh báo; ngoài khoảng đó phần thừa bị cắt / phần thiếu giữ khung cuối. Clip không đọc được (ffprobe lỗi) → dùng ảnh + cảnh báo.
- Âm lượng: clip 0.5 khi `--clip-audio` (0 khi tắt), nhạc 0.12 lặp lại tới hết video. Logo góc trên phải, cao 9% cạnh ngắn, mờ 0.9; file logo không có → cảnh báo, xuất không logo.
- Zoom 1.0↔1.08 xen kẽ chỉ áp cho ảnh, không áp cho clip.
- `quick render` không đổi `stage` trong `quick.yaml`.
- Draft CapCut: pyCapCut không có "giữ khung cuối" → clip ngắn hơn mốc được làm chậm cho vừa mốc; clip dài hơn bị cắt. Âm lượng clip trong draft cố định 0.5 (chỉnh trong CapCut).

## Review Focus

- `-p projects/<tên>` (đường dẫn tương đối) trong khi Remotion chạy với `cwd=remotion/` → props, public dir, file ra phải là đường dẫn tuyệt đối, không thì Remotion không tìm thấy file — test ở Task 3.
- Remotion lỗi giữa chừng → không để lại `out/<tên>-vN.mp4` dở dang (lần sau dùng nhầm); lần chạy lại vẫn lấy đúng số phiên bản — test ở Task 3.
- Xuất lại nhiều lần → public dir dựng lại sạch, không chứa `out/` (bản cũ) — test ở Task 3.
- Clip hỏng/không đọc được, hoặc clip đã `clip off` dù status `ok` → dùng ảnh, không crash — test ở Task 2 (render) và Task 1 (`ready_clips`).
- `voice.wav` thiếu hoặc dài hơn mốc cuối; mốc chưa có ảnh xen giữa → video vẫn liền mạch, cảnh báo nêu đúng số mốc — test ở Task 2.

---

### Task 1: `ready_clips` + draft CapCut nhận clip (Model: haiku)

**Files:**
- Modify: `src/vidflow/quick/clips.py` (thêm `ready_clips`)
- Modify: `src/vidflow/assemble.py` (`Placement.n`, `AssembleReport.clips`, tham số `clips`)
- Modify: `src/vidflow/quick/build.py` (truyền `clips`)
- Test: `tests/test_quick_clips.py`, `tests/test_assemble.py`, `tests/test_quick_build.py`

**Interfaces:**
- Consumes: `Beats`, `Clip` (`vidflow.quick.model`); `_MediaStage`, `cover_scale`, `_us` (`vidflow.capcut_draft`).
- Produces:
  - `vidflow.quick.clips.ready_clips(root: Path, beats: Beats) -> dict[int, Path]` — clip dùng được khi dựng/xuất: `clip.enabled`, `clip.status == "ok"`, `clip.file` tồn tại; giá trị = `root / clip.file`.
  - `vidflow.assemble.Placement(file: Path, start: float, end: float, n: int = 0)`.
  - `vidflow.assemble.AssembleReport.clips: int` (số mốc dùng clip).
  - `vidflow.assemble.assemble(..., clips: dict[int, Path] | None = None, ...)`; hằng `CLIP_VOLUME = 0.5`.
  - `build_quick` gọi `assemble(..., clips=ready_clips(root, beats))` (`{}` khi chưa có beats).

- [ ] **Step 1: Write the failing tests**

Thêm vào cuối `tests/test_quick_clips.py`:

```python
def test_ready_clips_only_enabled_ok_and_on_disk(qroot, P, img):
    _ready(qroot, P, img, 1)
    _ready(qroot, P, img, 2)
    _ready(qroot, P, img, 3)
    clips.set_clip_prompts(qroot, [{"n": n, "prompt": CP, "verdict": "pass", "score": 8} for n in (1, 2, 3)])
    for n in (1, 2, 3):
        clips.set_clip(qroot, n, img(f"v{n}.mp4", b"mp4"))
    clips.set_clip_enabled(qroot, [2], False)          # người dùng tắt clip → dùng ảnh
    (qroot / "clips" / "003_00-08.mp4").unlink()         # file mất → bỏ qua
    assert clips.ready_clips(qroot, load_beats(qroot)) == {1: qroot / "clips" / "001_00-00.mp4"}
```

Thêm vào `tests/test_assemble.py` — phần `plan_images` (sau `test_plan_no_images_errors`):

```python
def test_plan_keeps_beat_number(tmp_path):
    d = touch(tmp_path / "imgs", "001_00-00.jpg", "007_00-03.jpg")
    assert [p.n for p in plan_images(d)] == [1, 7]
```

và phần `assemble` (sau `test_assemble_audio_and_subtitles`):

```python
@needs_ffmpeg
def test_assemble_with_clips(small_images, acfg, tmp_path):
    from conftest import make_mp4
    from vidflow.capcut_draft import cover_scale

    long_clip = make_mp4(tmp_path / "dl" / "002_00-02.mp4", 3.0)   # mốc 2 dài 1 s → cắt
    short_clip = make_mp4(tmp_path / "dl" / "004_00-05.mp4", 1.0)  # mốc 4 dài 4 s → làm chậm
    rep = run(small_images, acfg, clips={2: long_clip, 4: short_clip})
    assert rep.count == 4 and rep.clips == 2
    content = load(rep.draft_dir)
    segs = track_segs(content, "video")
    assert len(segs) == 4
    t = 0
    for s in segs:  # vẫn liền mạch
        assert s["target_timerange"]["start"] == t
        t += s["target_timerange"]["duration"]
    assert t == 9_000_000
    vids = {m["id"]: m for m in content["materials"]["videos"]}
    s1, s2, s4 = segs[0], segs[1], segs[3]
    assert str(acfg.media_folder / "vidflow_proj" / "clips") in vids[s2["material_id"]]["path"]
    assert s2["source_timerange"] == {"start": 0, "duration": 1_000_000} and s2["speed"] == 1.0
    assert s2["volume"] == 0.5 and not s2["common_keyframes"]
    assert s2["clip"]["scale"]["x"] == pytest.approx(cover_scale(216, 384, 1920, 1080), rel=1e-4)
    assert s4["target_timerange"]["duration"] == 4_000_000
    assert s4["speed"] == pytest.approx(0.25, rel=0.05)
    assert s1["volume"] == 0.0 and "images" in vids[s1["material_id"]]["path"]
```

Trong `tests/test_quick_build.py`: thêm `assert kw["clips"] == {}` vào cuối `test_build_passes_args` (sau `assert kw["cfg"] is cfg`), và thêm test:

```python
def test_build_passes_ready_clips(tmp_path, fake_assemble):
    from vidflow.quick.model import Clip

    root = tmp_path / "v"
    create_quick(root, preset="doodle-giai-ma", title="T")
    save_beats(root, Beats(aspect="16:9", beats=[
        Beat(n=1, start=0.0, end=1.0, text="A.", image="images/001_00-00.jpg", status="ok",
             clip=Clip(enabled=True, status="ok", file="clips/001_00-00.mp4")),
        Beat(n=2, start=1.0, end=2.0, text="B.", image="images/002_00-01.jpg", status="ok",
             clip=Clip(enabled=True, status="redo", file="clips/002_00-01.mp4"))]))
    for rel in ("images/001_00-00.jpg", "images/002_00-01.jpg", "clips/001_00-00.mp4", "clips/002_00-01.mp4"):
        (root / rel).write_bytes(b"x")
    build_quick(root, Config())
    _, kw = fake_assemble[0]
    assert kw["clips"] == {1: root / "clips" / "001_00-00.mp4"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_quick_clips.py tests/test_assemble.py tests/test_quick_build.py -v`
Expected: FAIL — `AttributeError: module 'vidflow.quick.clips' has no attribute 'ready_clips'`, `AttributeError: 'Placement' object has no attribute 'n'`, `TypeError: assemble() got an unexpected keyword argument 'clips'`, `KeyError: 'clips'`.

- [ ] **Step 3: Implement `ready_clips`** — thêm vào cuối `src/vidflow/quick/clips.py`:

```python
def ready_clips(root: Path, beats: Beats) -> dict[int, Path]:
    """Clip dùng được khi dựng draft/xuất MP4: đã bật, status ok, file còn trên đĩa. {n: đường dẫn}."""
    root = Path(root)
    out: dict[int, Path] = {}
    for b in beats.beats:
        c = b.clip
        if c.enabled and c.status == "ok" and c.file and (root / c.file).is_file():
            out[b.n] = root / c.file
    return out
```

- [ ] **Step 4: Implement `assemble` nhận clip** — `src/vidflow/assemble.py`:

Thêm hằng sau `SUB_Y = -0.8`:

```python
CLIP_VOLUME = 0.5     # tiếng clip Veo, nhỏ dưới giọng đọc
```

Thay `Placement` và `AssembleReport`:

```python
@dataclass(frozen=True)
class Placement:
    file: Path
    start: float
    end: float
    n: int = 0  # số mốc NNN


@dataclass
class AssembleReport:
    draft_dir: Path
    count: int
    total_s: float
    skipped_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    clips: int = 0
```

Dòng cuối `plan_images` đổi thành:

```python
    return [Placement(f, float(t), float(e), n) for (n, t, f), e in zip(found, ends)]
```

Chữ ký `assemble` thêm `clips` (sau `subtitles`):

```python
def assemble(images_dir: Path, *, audio: Path | None = None, beats: Path | None = None, name: str | None = None,
             aspect: str = "auto", zoom: bool = True, subtitles: bool = True, clips: dict[int, Path] | None = None,
             cfg: Config, is_running: Callable[[], bool] | None = None, stamp: Callable[[], str] = _stamp) -> AssembleReport:
```

Thay vòng `for i, p in enumerate(plan):` (từ `stage = _MediaStage(_Dir(images_dir), ...)` tới `draft.add_segment(seg)`) bằng:

```python
        stage = _MediaStage(_Dir(images_dir), stage_root / "images")
        materials: dict[str, cc.VideoMaterial] = {}
        kp = cc.KeyframeProperty
        clips = clips or {}
        n_clips = 0
        for i, p in enumerate(plan):
            a, b = _us(p.start), _us(p.end)
            clip_path = clips.get(p.n)
            if clip_path is not None:
                # clip thay ảnh: cắt theo độ dài mốc; clip ngắn hơn mốc → làm chậm cho vừa (pyCapCut không giữ khung cuối)
                clip_path = Path(clip_path)
                path = _MediaStage(_Dir(clip_path.parent), stage_root / "clips")(clip_path.name)
                mat = materials.get(path) or materials.setdefault(path, cc.VideoMaterial(path))
                base = cover_scale(mat.width, mat.height, w, h)
                draft.add_segment(cc.VideoSegment(mat, cc.Timerange(a, b - a),
                                                  source_timerange=cc.Timerange(0, min(mat.duration, b - a)),
                                                  clip_settings=cc.ClipSettings(scale_x=base, scale_y=base),
                                                  volume=CLIP_VOLUME))
                n_clips += 1
                continue
            path = stage(p.file.name)
            mat = materials.get(path) or materials.setdefault(path, cc.VideoMaterial(path))
            base = cover_scale(mat.width, mat.height, w, h)
            seg = cc.VideoSegment(mat, cc.Timerange(a, b - a), clip_settings=cc.ClipSettings(scale_x=base, scale_y=base),
                                  volume=0.0)
            if zoom:
                lo, hi = (base, base * ZOOM) if i % 2 == 0 else (base * ZOOM, base)
                seg.add_keyframe(kp.uniform_scale, 0, lo)
                seg.add_keyframe(kp.uniform_scale, b - a, hi)
            draft.add_segment(seg)
```

Dòng `return AssembleReport(...)` cuối hàm đổi thành:

```python
    return AssembleReport(draft_dir=draft_dir, count=len(plan), total_s=plan[-1].end,
                          skipped_files=skipped, warnings=warnings, clips=n_clips)
```

- [ ] **Step 5: `build_quick` truyền clip** — thay toàn bộ `src/vidflow/quick/build.py`:

```python
"""Bước cuối quy trình nhanh: gọi `vidflow.assemble.assemble` (bước 6) với images/, voice.wav, beats.json, clip ok."""
from __future__ import annotations

from pathlib import Path

from vidflow.config import Config
from vidflow.errors import VidflowError
from vidflow.quick.clips import ready_clips
from vidflow.quick.model import BEATS_FILE, load_beats, load_quick
from vidflow.quick.ops import IMAGE_EXTS, VOICE_FILE, advance


def build_quick(root: Path, cfg: Config, *, name: str | None = None, zoom: bool = True, subtitles: bool = True):
    from vidflow.assemble import assemble  # bước 6, viết song song

    root = Path(root)
    q = load_quick(root)
    images = root / "images"
    if not images.is_dir() or not any(f.suffix.lower() in IMAGE_EXTS for f in images.iterdir()):
        raise VidflowError(f"Chưa có ảnh trong {images} — chạy `vidflow quick flow` hoặc thả ảnh NNN_MM-SS.jpg vào.")
    beats = load_beats(root)
    voice = root / VOICE_FILE
    res = assemble(images, audio=voice if voice.is_file() else None,
                   beats=root / BEATS_FILE if beats and beats.timed else None,
                   name=name or root.name, aspect=beats.aspect if beats else "auto",
                   zoom=zoom, subtitles=subtitles, clips=ready_clips(root, beats) if beats else {}, cfg=cfg)
    advance(root, "built", q)
    return res
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_quick_clips.py tests/test_assemble.py tests/test_quick_build.py -v`
Expected: PASS (các test `needs_ffmpeg` chạy vì máy có ffmpeg).

- [ ] **Step 7: Commit**

```bash
git add src/vidflow/quick/clips.py src/vidflow/assemble.py src/vidflow/quick/build.py \
        tests/test_quick_clips.py tests/test_assemble.py tests/test_quick_build.py
git commit -m "feat(quick): CapCut draft uses ready clips instead of images"
```

---

### Task 2: Bộ sinh render-props (`quick/render.py`, phần thuần) (Model: haiku)

**Files:**
- Create: `src/vidflow/quick/render.py`
- Test: `tests/test_quick_render.py`

**Interfaces:**
- Consumes: `ready_clips(root, beats) -> dict[int, Path]` (Task 1); `load_quick`, `require_beats`; `VOICE_FILE` (`ops`); `REPO`, `load_preset` (`preset`); `probe_duration(path) -> float`, `wav_duration(path) -> float` (`vidflow.media`).
- Produces (Task 3 và UI giai đoạn 3 dùng):
  - Hằng: `FPS = 30`, `FADE_S = 0.3`, `SPEED_RANGE = (0.5, 2.0)`, `CLIP_VOLUME = 0.5`, `MUSIC_VOLUME = 0.12`, `SIZES`, `TRANSITIONS`, `CLIP_FITS`, `MUSIC_FILES`, `PROPS_FILE = "tmp/render-props.json"`, `PUBLIC_DIR = "tmp/render/public"`, `REMOTION_DIR = REPO / "remotion"`, `COMPOSITION = "DoodleVideo"`.
  - `RenderOptions(resolution: str | None = None, transition="scene", clip_fit="trim", zoom=True, subtitles=True, clip_audio=True, logo=True, music=True)` (dataclass).
  - `RenderPlan(props: dict, assets: dict[str, Path], warnings: list[str])` — `assets`: đường dẫn trong public dir (= giá trị trong props) → file thật.
  - `canvas(resolution: str, aspect: str) -> tuple[int, int]`.
  - `build_render_props(root: Path, opts: RenderOptions | None = None, *, probe: Callable[[Path], float] | None = None) -> RenderPlan`.
  - Dạng props (hợp đồng với `DoodleVideo.tsx`, Task 4):
    `{"fps", "width", "height", "duration", "beats": [{"n", "src", "kind": "image"|"video"|"blank", "start", "end", "cont", "fade", "rate", "clipLen"}], "audio", "subtitles": [{"start", "end", "text"}], "zoom", "clipVolume", "logo", "music", "musicVolume"}`.

- [ ] **Step 1: Write the failing tests** — tạo `tests/test_quick_render.py`:

```python
import pytest

from conftest import write_wav
from vidflow.errors import VidflowError
from vidflow.quick import clips, ops
from vidflow.quick import render as rq
from vidflow.quick.model import load_beats, save_beats
from vidflow.quick.preset import load_preset, save_preset


def edit(root, fn):
    """Sửa beats.json trong test (fixture qroot cũng làm vậy) — code thật luôn đi qua ops/clips."""
    b = load_beats(root)
    fn(b.beats)
    save_beats(root, b)


def with_images(root, img, ns=(1, 2, 3, 4)):
    for n in ns:
        ops.set_image(root, n, img(f"{n}.png"))


def with_clip(root, img, n):
    clips.set_clip_enabled(root, [n], True)
    clips.set_clip(root, n, img(f"c{n}.mp4", b"mp4"))


def test_canvas_sizes():
    assert rq.canvas("1080p", "16:9") == (1920, 1080)
    assert rq.canvas("720p", "16:9") == (1280, 720)
    assert rq.canvas("1080p", "9:16") == (1080, 1920)
    assert rq.canvas("720p", "9:16") == (720, 1280)
    with pytest.raises(VidflowError, match="1080p"):
        rq.canvas("4k", "16:9")


def test_props_images_only(qroot, img):
    with_images(qroot, img)
    plan = rq.build_render_props(qroot)
    p = plan.props
    assert (p["fps"], p["width"], p["height"]) == (30, 1280, 720)  # flow.resolution mặc định 720p
    assert p["duration"] == 16.0 and p["audio"] is None
    assert [b["kind"] for b in p["beats"]] == ["image"] * 4
    assert p["beats"][1] == {"n": 2, "src": "images/002_00-04.png", "kind": "image", "start": 4.0, "end": 8.0,
                             "cont": False, "fade": 0.3, "rate": 1.0, "clipLen": None}
    assert p["beats"][0]["fade"] == 0.0
    assert [s["text"] for s in p["subtitles"]] == ["A.", "B.", "C.", "D."]
    assert p["zoom"] is True and p["clipVolume"] == 0.5
    assert p["logo"] is None and p["music"] is None and p["musicVolume"] == 0.12
    assert plan.assets["images/002_00-04.png"] == qroot / "images" / "002_00-04.png"
    assert any("voice.wav" in w for w in plan.warnings)


def test_resolution_option_overrides_flow(qroot, img):
    with_images(qroot, img)
    p = rq.build_render_props(qroot, rq.RenderOptions(resolution="1080p")).props
    assert (p["width"], p["height"]) == (1920, 1080)


def test_blank_beats_voice_length_and_gaps(qroot, img):
    with_images(qroot, img, ns=(1, 3))

    def gaps(bs):
        for i, b in enumerate(bs):
            b.start, b.end = i * 4.0, i * 4.0 + 3.85  # khoảng lặng 0.15 s giữa câu như voice.py

    edit(qroot, gaps)
    write_wav(qroot / "audio" / "voice.wav", 20.0)
    plan = rq.build_render_props(qroot)
    p = plan.props
    assert p["duration"] == 20.0 and p["audio"] == "audio/voice.wav"
    assert plan.assets["audio/voice.wav"] == qroot / "audio" / "voice.wav"
    assert [(b["start"], b["end"]) for b in p["beats"]] == [(0.0, 4.0), (4.0, 8.0), (8.0, 12.0), (12.0, 20.0)]
    assert [b["kind"] for b in p["beats"]] == ["image", "blank", "image", "blank"]
    assert p["beats"][1]["src"] is None
    assert p["subtitles"][0] == {"start": 0.0, "end": 3.85, "text": "A."}
    assert any("2 mốc chưa có ảnh" in w and "2, 4" in w for w in plan.warnings)
    assert not any("voice.wav" in w for w in plan.warnings)


def test_duration_is_max_of_voice_and_last_beat(qroot, img):
    with_images(qroot, img)
    write_wav(qroot / "audio" / "voice.wav", 10.0)
    assert rq.build_render_props(qroot).props["duration"] == 16.0


def test_requires_some_image_and_timing(qroot):
    with pytest.raises(VidflowError, match="Chưa có ảnh"):
        rq.build_render_props(qroot)
    edit(qroot, lambda bs: setattr(bs[2], "start", None))
    with pytest.raises(VidflowError, match="quick voice"):
        rq.build_render_props(qroot)


def test_clip_trim_and_speed(qroot, img):
    with_images(qroot, img)
    with_clip(qroot, img, 2)
    with_clip(qroot, img, 3)
    lengths = {"002_00-04.mp4": 2.5, "003_00-08.mp4": 6.0}
    probe = lambda path: lengths[path.name]  # noqa: E731
    plan = rq.build_render_props(qroot, probe=probe)
    b2, b3 = plan.props["beats"][1], plan.props["beats"][2]
    assert (b2["kind"], b2["src"], b2["rate"], b2["clipLen"]) == ("video", "clips/002_00-04.mp4", 1.0, 2.5)
    assert (b3["kind"], b3["rate"], b3["clipLen"]) == ("video", 1.0, 6.0)
    assert plan.assets["clips/002_00-04.mp4"] == qroot / "clips" / "002_00-04.mp4"
    p = rq.build_render_props(qroot, rq.RenderOptions(clip_fit="speed"), probe=probe).props
    assert p["beats"][1]["rate"] == 0.625 and p["beats"][2]["rate"] == 1.5


def test_speed_is_clamped_with_warning(qroot, img):
    with_images(qroot, img)
    with_clip(qroot, img, 1)
    plan = rq.build_render_props(qroot, rq.RenderOptions(clip_fit="speed"), probe=lambda _: 1.0)
    assert plan.props["beats"][0]["rate"] == 0.5
    assert any("Mốc 1" in w and "x0.25" in w for w in plan.warnings)


def test_clip_fallbacks_to_image(qroot, img):
    with_images(qroot, img)
    with_clip(qroot, img, 1)
    with_clip(qroot, img, 2)
    clips.set_clip_enabled(qroot, [1], False)

    def broken(path):
        raise VidflowError("ffprobe không đọc được")

    plan = rq.build_render_props(qroot, probe=broken)
    assert [b["kind"] for b in plan.props["beats"][:2]] == ["image", "image"]
    assert any("Mốc 2" in w and "dùng ảnh" in w for w in plan.warnings)


def test_transitions(qroot, img):
    with_images(qroot, img)
    edit(qroot, lambda bs: setattr(bs[2], "cont", True))

    def fades(t):
        return [b["fade"] for b in rq.build_render_props(qroot, rq.RenderOptions(transition=t)).props["beats"]]

    assert rq.build_render_props(qroot).props["beats"][2]["cont"] is True
    assert fades("scene") == [0.0, 0.3, 0.0, 0.3]
    assert fades("cut") == [0.0, 0.0, 0.0, 0.0]
    assert fades("fade") == [0.0, 0.3, 0.3, 0.3]
    edit(qroot, lambda bs: setattr(bs[1], "start", 7.6))  # mốc 2 chỉ còn 0.4 s → mờ tối đa nửa mốc
    assert fades("fade")[1] == 0.2
    with pytest.raises(VidflowError, match="scene, cut hoặc fade"):
        rq.build_render_props(qroot, rq.RenderOptions(transition="wipe"))
    with pytest.raises(VidflowError, match="trim hoặc speed"):
        rq.build_render_props(qroot, rq.RenderOptions(clip_fit="stretch"))


def test_logo_music_and_switches(qroot, img, quick_presets, tmp_path):
    with_images(qroot, img)
    logo = tmp_path / "brand" / "Logo.PNG"
    logo.parent.mkdir()
    logo.write_bytes(b"png")
    pr = load_preset("doodle-giai-ma")
    pr.logo = str(logo)
    save_preset(pr, presets_dir=quick_presets)
    write_wav(qroot / "audio" / "music.wav", 2.0)
    plan = rq.build_render_props(qroot)
    assert plan.props["logo"] == "logo/logo.png" and plan.assets["logo/logo.png"] == logo
    assert plan.props["music"] == "audio/music.wav"
    assert plan.assets["audio/music.wav"] == qroot / "audio" / "music.wav"
    off = rq.build_render_props(qroot, rq.RenderOptions(zoom=False, subtitles=False, clip_audio=False,
                                                        logo=False, music=False)).props
    assert off["zoom"] is False and off["subtitles"] == [] and off["clipVolume"] == 0.0
    assert off["logo"] is None and off["music"] is None
    logo.unlink()
    plan = rq.build_render_props(qroot)
    assert plan.props["logo"] is None and any("logo" in w for w in plan.warnings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_quick_render.py -v`
Expected: FAIL — `ImportError: cannot import name 'render' from 'vidflow.quick'`.

- [ ] **Step 3: Implement** — tạo `src/vidflow/quick/render.py`:

```python
"""Xuất MP4 bằng Remotion (spec 2026-10-12, giai đoạn 2).

`build_render_props` (thuần) đọc quick.yaml + beats.json → props cho remotion/src/DoodleVideo.tsx.
Đường dẫn trong props tương đối với public dir của Remotion, cùng cấu trúc với project (images/…, clips/…, audio/…).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from vidflow.errors import VidflowError
from vidflow.media import probe_duration, wav_duration
from vidflow.quick.clips import ready_clips
from vidflow.quick.model import load_quick, require_beats
from vidflow.quick.ops import VOICE_FILE
from vidflow.quick.preset import REPO, load_preset

FPS = 30
FADE_S = 0.3              # mờ chéo khi mở cảnh mới
SPEED_RANGE = (0.5, 2.0)  # clip-fit=speed: giới hạn tốc độ; ngoài khoảng → cắt / giữ khung cuối
CLIP_VOLUME = 0.5         # tiếng clip, nhỏ dưới giọng đọc
MUSIC_VOLUME = 0.12       # nhạc nền rất nhỏ
SIZES = {"1080p": (1920, 1080), "720p": (1280, 720)}
TRANSITIONS = ("scene", "cut", "fade")
CLIP_FITS = ("trim", "speed")
MUSIC_FILES = ("audio/music.mp3", "audio/music.wav")
PROPS_FILE = "tmp/render-props.json"
PUBLIC_DIR = "tmp/render/public"
REMOTION_DIR = REPO / "remotion"
COMPOSITION = "DoodleVideo"


@dataclass
class RenderOptions:
    resolution: str | None = None  # None = flow.resolution của quick.yaml
    transition: str = "scene"
    clip_fit: str = "trim"
    zoom: bool = True
    subtitles: bool = True
    clip_audio: bool = True
    logo: bool = True
    music: bool = True


@dataclass
class RenderPlan:
    props: dict
    assets: dict[str, Path]  # đường dẫn trong public dir (= giá trị trong props) → file thật
    warnings: list[str] = field(default_factory=list)


def canvas(resolution: str, aspect: str) -> tuple[int, int]:
    if resolution not in SIZES:
        raise VidflowError(f"Độ phân giải phải là 1080p hoặc 720p, nhận {resolution!r}.")
    w, h = SIZES[resolution]
    return (h, w) if aspect == "9:16" else (w, h)


def _check(opts: RenderOptions) -> None:
    if opts.transition not in TRANSITIONS:
        raise VidflowError(f"--transition phải là scene, cut hoặc fade (nhận {opts.transition!r}).")
    if opts.clip_fit not in CLIP_FITS:
        raise VidflowError(f"--clip-fit phải là trim hoặc speed (nhận {opts.clip_fit!r}).")


def _fade(i: int, cont: bool, span: float, transition: str) -> float:
    """Giây mờ chéo khi vào mốc i. scene: nối cảnh (cont) cắt thẳng, cảnh mới mờ chéo."""
    if i == 0 or transition == "cut" or (transition == "scene" and cont):
        return 0.0
    return round(min(FADE_S, span / 2), 3)


def _logo_path(logo: str) -> Path:
    p = Path(logo).expanduser()
    return p if p.is_absolute() else REPO / p


def build_render_props(root: Path, opts: RenderOptions | None = None, *,
                       probe: Callable[[Path], float] | None = None) -> RenderPlan:
    root = Path(root)
    opts = opts or RenderOptions()
    probe = probe or probe_duration
    _check(opts)
    q = load_quick(root)
    beats = require_beats(root)
    if not beats.timed:
        raise VidflowError("Mốc chưa có thời gian — chạy `vidflow quick voice` trước khi xuất video.")
    width, height = canvas(opts.resolution or q.flow.resolution, beats.aspect)
    warnings: list[str] = []
    assets: dict[str, Path] = {}

    voice = root / VOICE_FILE
    audio = None
    voice_s = 0.0
    if voice.is_file():
        audio, voice_s = VOICE_FILE, wav_duration(voice)
        assets[VOICE_FILE] = voice
    else:
        warnings.append("Chưa có audio/voice.wav — video không có giọng đọc.")
    bl = beats.beats
    duration = round(max(voice_s, bl[-1].end), 3)

    ready = ready_clips(root, beats)
    rows: list[dict] = []
    blank: list[int] = []
    for i, b in enumerate(bl):
        start = round(b.start, 3)
        end = round(bl[i + 1].start, 3) if i + 1 < len(bl) else duration
        if end <= start:
            raise VidflowError(f"Mốc {b.n}: thời gian không tăng ({start:g}s → {end:g}s).")
        span = end - start
        row = {"n": b.n, "src": None, "kind": "blank", "start": start, "end": end, "cont": b.cont,
               "fade": _fade(i, b.cont, span, opts.transition), "rate": 1.0, "clipLen": None}
        clip = ready.get(b.n)
        clip_len = 0.0
        if clip is not None:
            try:
                clip_len = round(probe(clip), 3)
            except VidflowError as e:
                warnings.append(f"Mốc {b.n}: không đọc được clip ({e}) — dùng ảnh.")
                clip = None
        if clip is not None:
            rate = 1.0
            if opts.clip_fit == "speed":
                lo, hi = SPEED_RANGE
                want = clip_len / span
                rate = round(min(hi, max(lo, want)), 4)
                if want < lo or want > hi:
                    warnings.append(f"Mốc {b.n}: clip cần tốc độ x{want:.2f}, giới hạn x{rate:g} "
                                    "— phần thừa bị cắt, phần thiếu giữ khung cuối.")
            row.update(src=b.clip.file, kind="video", rate=rate, clipLen=clip_len)
            assets[b.clip.file] = clip
        elif b.image and (root / b.image).is_file():
            row.update(src=b.image, kind="image")
            assets[b.image] = root / b.image
        else:
            blank.append(b.n)
        rows.append(row)
    if len(blank) == len(rows):
        raise VidflowError("Chưa có ảnh mốc nào — gen ảnh (`vidflow quick flow`) trước khi xuất video.")
    if blank:
        warnings.append(f"{len(blank)} mốc chưa có ảnh (khung trống): {', '.join(map(str, blank))}")

    subs = [{"start": round(b.start, 3), "end": round(b.end, 3), "text": b.text.strip()}
            for b in bl if opts.subtitles and b.text.strip()]

    logo = None
    preset = load_preset(q.preset)
    if opts.logo and preset.logo:
        src = _logo_path(preset.logo)
        if src.is_file():
            logo = f"logo/logo{src.suffix.lower()}"
            assets[logo] = src
        else:
            warnings.append(f"Không thấy logo {src} (presets/{preset.id}.yaml) — xuất không có logo.")

    music = None
    if opts.music:
        for rel in MUSIC_FILES:
            if (root / rel).is_file():
                music = rel
                assets[rel] = root / rel
                break

    props = {"fps": FPS, "width": width, "height": height, "duration": duration, "beats": rows, "audio": audio,
             "subtitles": subs, "zoom": opts.zoom, "clipVolume": CLIP_VOLUME if opts.clip_audio else 0.0,
             "logo": logo, "music": music, "musicVolume": MUSIC_VOLUME}
    return RenderPlan(props=props, assets=assets, warnings=warnings)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_quick_render.py -v`
Expected: PASS (11 test).

- [ ] **Step 5: Commit**

```bash
git add src/vidflow/quick/render.py tests/test_quick_render.py
git commit -m "feat(quick): build Remotion render props from beats, clips, voice, logo, music"
```

---

### Task 3: Chạy Remotion + lệnh `vidflow quick render` (Model: haiku)

**Files:**
- Modify: `src/vidflow/quick/render.py` (runner)
- Modify: `src/vidflow/quick/cli.py` (lệnh `render`)
- Test: `tests/test_quick_render.py`

**Interfaces:**
- Consumes: `RenderOptions`, `RenderPlan`, `build_render_props`, `PROPS_FILE`, `PUBLIC_DIR`, `REMOTION_DIR`, `COMPOSITION` (Task 2).
- Produces:
  - `RenderResult(output: Path, props_path: Path, duration: float, warnings: list[str])` (dataclass).
  - `stage_public(root: Path, assets: dict[str, Path]) -> Path` — dựng lại `root/PUBLIC_DIR` chỉ gồm symlink tuyệt đối.
  - `next_output(root: Path) -> Path` — `root.resolve()/out/<tên>-v<N+1>.mp4`.
  - `write_render_props(root: Path, opts: RenderOptions | None = None, *, probe=None) -> tuple[Path, RenderPlan]` — ghi `tmp/render-props.json` + public dir; đường dẫn trả về tuyệt đối.
  - `render_cmd(npx: str, out: Path, props_path: Path, public: Path) -> list[str]` = `[npx, "remotion", "render", "src/index.ts", "DoodleVideo", str(out), "--props=<abs>", "--public-dir=<abs>"]`.
  - `render_quick(root: Path, opts: RenderOptions | None = None, *, run=None, probe=None, remotion_dir: Path | None = None, npx: str | None = None) -> RenderResult` — `run` mặc định `subprocess.run`, `remotion_dir` mặc định `REMOTION_DIR`, `npx` mặc định `shutil.which("npx")` (đều đọc lúc gọi để monkeypatch được).
  - CLI: `vidflow quick render -p <project> [tùy chọn spec] [--props-only]`.

- [ ] **Step 1: Write the failing tests** — thêm vào `tests/test_quick_render.py` (thêm import ở đầu file: `import json`, `import subprocess`, `from pathlib import Path`, `from typer.testing import CliRunner`, `from vidflow.cli import app`; và `runner = CliRunner()` dưới các import):

```python
@pytest.fixture
def remotion(tmp_path):
    """Thư mục remotion/ giả đã 'npm ci' (chỉ cần node_modules/@remotion/cli)."""
    d = tmp_path / "remotion"
    (d / "node_modules" / "@remotion" / "cli").mkdir(parents=True)
    return d


def fake_run(calls, rc=0):
    def run(cmd, **kw):
        calls.append((cmd, kw))
        if rc == 0:
            Path(cmd[5]).write_bytes(b"mp4")
        return subprocess.CompletedProcess(cmd, rc)
    return run


def test_write_props_and_public_dir(qroot, img):
    with_images(qroot, img, ns=(1,))
    (qroot / "out" / "vid-v1.mp4").write_bytes(b"old")
    path, plan = rq.write_render_props(qroot)
    assert path == (qroot / "tmp" / "render-props.json").resolve()
    assert json.loads(path.read_text(encoding="utf-8")) == plan.props
    public = qroot / "tmp" / "render" / "public"
    link = public / "images" / "001_00-00.png"
    assert link.is_symlink() and link.resolve() == (qroot / "images" / "001_00-00.png").resolve()
    assert not (public / "out").exists() and not (public / "images" / "002_00-04.png").exists()
    (public / "stray.txt").write_text("x")
    rq.write_render_props(qroot)
    assert not (public / "stray.txt").exists()                     # dựng lại sạch
    assert (qroot / "images" / "001_00-00.png").read_bytes()       # file thật còn nguyên


def test_next_output_versions(qroot):
    out = (qroot / "out").resolve()
    assert rq.next_output(qroot) == out / "vid-v1.mp4"
    for name in ("vid-v1.mp4", "vid-v3.mp4", "other-v9.mp4", "vid-v2-test.mp4"):
        (out / name).write_bytes(b"x")
    assert rq.next_output(qroot) == out / "vid-v4.mp4"


def test_render_runs_remotion_with_absolute_paths(qroot, img, remotion, monkeypatch):
    with_images(qroot, img)
    monkeypatch.chdir(qroot.parent)
    calls = []
    res = rq.render_quick(Path("vid"), run=fake_run(calls), remotion_dir=remotion, npx="npx")
    cmd, kw = calls[0]
    root = qroot.resolve()
    assert cmd[:5] == ["npx", "remotion", "render", "src/index.ts", "DoodleVideo"]
    assert cmd[5] == str(root / "out" / "vid-v1.mp4")
    assert cmd[6] == f"--props={root / 'tmp' / 'render-props.json'}"
    assert cmd[7] == f"--public-dir={root / 'tmp' / 'render' / 'public'}"
    assert kw["cwd"] == remotion
    assert res.output == root / "out" / "vid-v1.mp4" and res.output.is_file()
    assert res.props_path == root / "tmp" / "render-props.json" and res.duration == 16.0
    rq.render_quick(qroot, run=fake_run(calls), remotion_dir=remotion, npx="npx")
    assert calls[1][0][5] == str(root / "out" / "vid-v2.mp4")


def test_render_failure_leaves_no_output(qroot, img, remotion):
    with_images(qroot, img)

    def run(cmd, **kw):
        Path(cmd[5]).write_bytes(b"half")  # Remotion chết giữa chừng
        return subprocess.CompletedProcess(cmd, 1)

    with pytest.raises(VidflowError, match="mã 1"):
        rq.render_quick(qroot, run=run, remotion_dir=remotion, npx="npx")
    assert list((qroot / "out").glob("*.mp4")) == []
    assert rq.next_output(qroot).name == "vid-v1.mp4"


def test_render_requires_remotion_install_and_npx(qroot, img, remotion, tmp_path, monkeypatch):
    with_images(qroot, img)
    with pytest.raises(VidflowError, match="npm ci"):
        rq.render_quick(qroot, run=fake_run([]), remotion_dir=tmp_path / "nope", npx="npx")
    monkeypatch.setattr(rq.shutil, "which", lambda name: None)
    with pytest.raises(VidflowError, match="npx"):
        rq.render_quick(qroot, run=fake_run([]), remotion_dir=remotion)


def test_cli_render(qroot, img, remotion, monkeypatch):
    with_images(qroot, img)
    calls = []
    monkeypatch.setattr(rq, "REMOTION_DIR", remotion)
    monkeypatch.setattr(rq.subprocess, "run", fake_run(calls))
    monkeypatch.setattr(rq.shutil, "which", lambda name: "/usr/local/bin/npx")
    r = runner.invoke(app, ["quick", "render", "-p", str(qroot), "--resolution", "1080p", "--transition", "cut",
                            "--clip-fit", "speed", "--no-zoom", "--no-subtitles", "--no-clip-audio", "--no-logo",
                            "--no-music"])
    assert r.exit_code == 0, r.output
    assert "vid-v1.mp4" in r.output and calls[0][0][0] == "/usr/local/bin/npx"
    props = json.loads((qroot / "tmp" / "render-props.json").read_text(encoding="utf-8"))
    assert (props["width"], props["zoom"], props["subtitles"], props["clipVolume"]) == (1920, False, [], 0.0)
    assert all(b["fade"] == 0.0 for b in props["beats"])
    r = runner.invoke(app, ["quick", "render", "-p", str(qroot), "--props-only"])
    assert r.exit_code == 0, r.output
    assert "render-props.json" in r.output and len(calls) == 1
    r = runner.invoke(app, ["quick", "render", "-p", str(qroot), "--transition", "wipe"])
    assert r.exit_code == 1 and "Traceback" not in r.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_quick_render.py -v`
Expected: FAIL — `AttributeError: module 'vidflow.quick.render' has no attribute 'write_render_props'` (và `next_output`, `render_quick`); `test_cli_render` exit code 2 (`No such command 'render'`).

- [ ] **Step 3: Implement runner** — `src/vidflow/quick/render.py`:

Thêm import ở đầu file (cạnh các import hiện có):

```python
import json
import re
import shutil
import subprocess

from vidflow.state import atomic_write_text
```

Thêm sau `class RenderPlan`:

```python
@dataclass
class RenderResult:
    output: Path
    props_path: Path
    duration: float
    warnings: list[str]
```

Thêm cuối file:

```python
def stage_public(root: Path, assets: dict[str, Path]) -> Path:
    """Public dir cho Remotion: chỉ symlink tới đúng các file cần, cùng đường dẫn tương đối như trong project.
    (Remotion copy cả public dir vào bundle mỗi lần render — trỏ thẳng vào project sẽ copy cả out/.)"""
    public = Path(root) / PUBLIC_DIR
    shutil.rmtree(public, ignore_errors=True)  # chỉ xóa symlink, không đụng file thật
    public.mkdir(parents=True, exist_ok=True)
    for rel, src in assets.items():
        dest = public / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(Path(src).resolve())
    return public


def next_output(root: Path) -> Path:
    root = Path(root).resolve()
    pat = re.compile(rf"{re.escape(root.name)}-v(\d+)\.mp4")
    out = root / "out"
    nums = [int(m[1]) for f in (out.iterdir() if out.is_dir() else []) if (m := pat.fullmatch(f.name))]
    return out / f"{root.name}-v{max(nums, default=0) + 1}.mp4"


def write_render_props(root: Path, opts: RenderOptions | None = None, *,
                       probe: Callable[[Path], float] | None = None) -> tuple[Path, RenderPlan]:
    root = Path(root).resolve()
    plan = build_render_props(root, opts, probe=probe)
    path = root / PROPS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(plan.props, ensure_ascii=False, indent=1))
    stage_public(root, plan.assets)
    return path, plan


def render_cmd(npx: str, out: Path, props_path: Path, public: Path) -> list[str]:
    return [npx, "remotion", "render", "src/index.ts", COMPOSITION, str(out),
            f"--props={props_path}", f"--public-dir={public}"]


def render_quick(root: Path, opts: RenderOptions | None = None, *, run: Callable | None = None,
                 probe: Callable[[Path], float] | None = None, remotion_dir: Path | None = None,
                 npx: str | None = None) -> RenderResult:
    """Sinh props + public dir rồi `npx remotion render` (cwd=remotion/) → out/<tên>-vN.mp4."""
    root = Path(root).resolve()
    run = run or subprocess.run
    remotion_dir = Path(remotion_dir or REMOTION_DIR)
    if not (remotion_dir / "node_modules" / "@remotion" / "cli").is_dir():
        raise VidflowError(f"Chưa cài Remotion — chạy `npm ci` trong {remotion_dir}.")
    npx = npx or shutil.which("npx")
    if not npx:
        raise VidflowError("Không thấy `npx` — cài Node.js (`brew install node`).")
    props_path, plan = write_render_props(root, opts, probe=probe)
    out = next_output(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    rc = run(render_cmd(npx, out, props_path, root / PUBLIC_DIR), cwd=remotion_dir,
             stdin=subprocess.DEVNULL).returncode
    if rc or not out.is_file():
        out.unlink(missing_ok=True)  # không để lại file dở dang
        raise VidflowError(f"Remotion render lỗi (mã {rc}) — xem log phía trên; props: {props_path}")
    return RenderResult(output=out, props_path=props_path, duration=plan.props["duration"], warnings=plan.warnings)
```

- [ ] **Step 4: Lệnh CLI** — `src/vidflow/quick/cli.py`, thêm ngay sau lệnh `build`:

```python
def _warn(lines: list[str]) -> None:
    for w in lines:
        typer.secho(f"  ! {w}", fg=typer.colors.YELLOW)


@_cmd(quick_app, "render")
def render(project: ProjectOpt,
           resolution: Annotated[Optional[str], typer.Option(help="1080p | 720p (mặc định: độ phân giải Flow của video)")] = None,
           transition: Annotated[str, typer.Option(help="scene (nối cảnh cắt thẳng, cảnh mới mờ chéo) | cut | fade")] = "scene",
           clip_fit: Annotated[str, typer.Option(help="trim (cắt; clip ngắn giữ khung cuối) | speed (đổi tốc độ cho vừa)")] = "trim",
           zoom: Annotated[bool, typer.Option("--zoom/--no-zoom")] = True,
           subtitles: Annotated[bool, typer.Option("--subtitles/--no-subtitles")] = True,
           clip_audio: Annotated[bool, typer.Option("--clip-audio/--no-clip-audio", help="Giữ tiếng của clip (nhỏ dưới giọng)")] = True,
           logo: Annotated[bool, typer.Option("--logo/--no-logo", help="Logo kênh (trường logo của bộ kênh)")] = True,
           music: Annotated[bool, typer.Option("--music/--no-music", help="Nhạc nền audio/music.mp3|wav nếu có")] = True,
           props_only: Annotated[bool, typer.Option("--props-only", help="Chỉ ghi tmp/render-props.json, không render")] = False):
    """Xuất MP4 bằng Remotion → out/<tên>-vN.mp4."""
    from vidflow.quick import render as rq

    opts = rq.RenderOptions(resolution=resolution, transition=transition, clip_fit=clip_fit, zoom=zoom,
                            subtitles=subtitles, clip_audio=clip_audio, logo=logo, music=music)
    if props_only:
        path, plan = rq.write_render_props(project, opts)
        _warn(plan.warnings)
        typer.echo(f"Đã ghi {path}")
        return
    typer.echo("Đang render bằng Remotion (video dài có thể mất vài phút)…")
    res = rq.render_quick(project, opts)
    _warn(res.warnings)
    m, s = divmod(res.duration, 60)
    typer.echo(f"Đã xuất {res.output} ({int(m)}:{s:04.1f})")
```

Sửa help của `quick_app` cho đúng luồng mới:

```python
quick_app = typer.Typer(no_args_is_help=True, help="Quy trình nhanh: ý tưởng → mốc → giọng → ảnh Flow → MP4 (Remotion) / CapCut")
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_quick_render.py tests/test_quick_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/vidflow/quick/render.py src/vidflow/quick/cli.py tests/test_quick_render.py
git commit -m "feat(quick): render command runs Remotion into out/<name>-vN.mp4"
```

---

### Task 4: Composition Remotion — clip, chuyển cảnh, logo, nhạc; khóa phiên bản (Model: haiku)

**Files:**
- Modify: `remotion/package.json`, `remotion/package-lock.json` (qua `npm install`)
- Modify: `remotion/src/DoodleVideo.tsx` (viết lại)
- Modify: `remotion/src/Root.tsx`

**Interfaces:**
- Consumes: dạng props của `build_render_props` (Task 2) — `VideoProps` dưới đây phải khớp từng khóa.
- Produces: composition `DoodleVideo` (id giữ nguyên, Task 3 gọi bằng `COMPOSITION`), độ dài = `ceil(duration * fps)` khung.

Không có test pytest (Remotion không chạy trong pytest); kiểm tra bằng `tsc --noEmit` ở task này và render thật ở Task 5.

- [ ] **Step 1: Khóa phiên bản** — thay toàn bộ `remotion/package.json`:

```json
{
  "name": "vidflow-remotion",
  "private": true,
  "scripts": {
    "studio": "remotion studio src/index.ts",
    "render": "remotion render src/index.ts DoodleVideo",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@remotion/cli": "4.0.534",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "remotion": "4.0.534"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "typescript": "^5.6.0"
  }
}
```

Run: `cd remotion && npm install && npm ls remotion @remotion/cli`
Expected: `remotion@4.0.534` và `@remotion/cli@4.0.534` (không dòng `invalid`); `git diff remotion/package-lock.json` chỉ đổi `"latest"` → `"4.0.534"` ở mục gốc `packages[""]`.

- [ ] **Step 2: Viết lại `remotion/src/DoodleVideo.tsx`**

```tsx
import { AbsoluteFill, Audio, Freeze, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";

// Hợp đồng với src/vidflow/quick/render.py (projects/<tên>/tmp/render-props.json).
// Đường dẫn tương đối public dir (= cấu trúc project: images/…, clips/…, audio/…, logo/…).
export type Shot = {
  n: number;
  src: string | null;
  kind: "image" | "video" | "blank";
  start: number;          // giây
  end: number;            // giây — = start của mốc sau (liền mạch)
  cont: boolean;          // nối cảnh với mốc trước
  fade: number;           // giây mờ chéo khi vào mốc (0 = cắt thẳng)
  rate: number;           // tốc độ phát clip (1 = trim)
  clipLen: number | null; // độ dài clip nguồn (giây)
};
export type Caption = { start: number; end: number; text: string };
export type VideoProps = {
  fps: number; width: number; height: number; duration: number;
  beats: Shot[]; audio: string | null; subtitles: Caption[];
  zoom: boolean; clipVolume: number;
  logo: string | null; music: string | null; musicVolume: number;
};
export const defaultProps: VideoProps = {
  fps: 30, width: 1920, height: 1080, duration: 10, beats: [], audio: null, subtitles: [],
  zoom: true, clipVolume: 0, logo: null, music: null, musicVolume: 0.12,
};

const BG = "#f6f1e3";
const COVER = { width: "100%", height: "100%", objectFit: "cover" } as const;
const toFrames = (s: number, fps: number) => Math.round(s * fps);

// Ảnh: phủ kín khung, zoom vào/ra xen kẽ theo thứ tự mốc.
const StillView: React.FC<{ src: string; index: number; frames: number; zoom: boolean }> = ({ src, index, frames, zoom }) => {
  const f = useCurrentFrame();
  const t = Math.min(1, f / Math.max(1, frames));
  const [a, b] = index % 2 === 0 ? [1.0, 1.08] : [1.08, 1.0];
  const scale = zoom ? a + (b - a) * t : 1;
  return <Img src={staticFile(src)} style={{ ...COVER, transform: `scale(${scale})` }} />;
};

// Clip: phát `play` khung đầu với tốc độ `rate`; sau đó (clip ngắn hơn mốc, hoặc phần chồng lúc mốc sau mờ vào)
// giữ khung cuối đã phát.
const ClipView: React.FC<{ shot: Shot; frames: number; fps: number; volume: number }> = ({ shot, frames, fps, volume }) => {
  const src = staticFile(shot.src as string);
  const playable = shot.clipLen ? Math.floor((shot.clipLen / shot.rate) * fps) : frames;
  const play = Math.max(1, Math.min(frames, playable));
  return (
    <AbsoluteFill>
      <Sequence durationInFrames={play} name="clip">
        <OffthreadVideo src={src} playbackRate={shot.rate} volume={volume} muted={volume <= 0} style={COVER} />
      </Sequence>
      <Sequence from={play} name="giữ khung cuối">
        <Freeze frame={play - 1}>
          <OffthreadVideo src={src} playbackRate={shot.rate} muted style={COVER} />
        </Freeze>
      </Sequence>
    </AbsoluteFill>
  );
};

const BeatView: React.FC<{ shot: Shot; index: number; frames: number; fps: number; zoom: boolean; clipVolume: number }> = (
  { shot, index, frames, fps, zoom, clipVolume },
) => {
  const f = useCurrentFrame();
  const fadeFrames = toFrames(shot.fade, fps);
  const opacity = fadeFrames > 0 ? interpolate(f, [0, fadeFrames], [0, 1], { extrapolateRight: "clamp" }) : 1;
  return (
    <AbsoluteFill style={{ opacity, backgroundColor: BG, overflow: "hidden" }}>
      {shot.kind === "image" && shot.src ? <StillView src={shot.src} index={index} frames={frames} zoom={zoom} /> : null}
      {shot.kind === "video" && shot.src ? <ClipView shot={shot} frames={frames} fps={fps} volume={clipVolume} /> : null}
    </AbsoluteFill>
  );
};

const CaptionView: React.FC<{ text: string; size: number }> = ({ text, size }) => {
  const f = useCurrentFrame();
  const y = interpolate(f, [0, 6], [20, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: Math.round(size * 1.35) }}>
      <div style={{ transform: `translateY(${y}px)`, background: "rgba(0,0,0,0.62)", color: "white", fontFamily: "Arial, Helvetica, sans-serif",
        fontSize: size, fontWeight: 700, padding: `${Math.round(size * 0.23)}px ${Math.round(size * 0.5)}px`, borderRadius: Math.round(size * 0.35),
        maxWidth: "80%", textAlign: "center", lineHeight: 1.25 }}>
        {text}
      </div>
    </AbsoluteFill>
  );
};

const LogoView: React.FC<{ src: string; short: number }> = ({ src, short }) => (
  <AbsoluteFill style={{ alignItems: "flex-end", justifyContent: "flex-start", padding: Math.round(short * 0.04) }}>
    <Img src={staticFile(src)} style={{ height: Math.round(short * 0.09), opacity: 0.9 }} />
  </AbsoluteFill>
);

export const DoodleVideo: React.FC<VideoProps> = ({ fps, width, height, beats, audio, subtitles, zoom, clipVolume, logo, music, musicVolume }) => {
  const short = Math.min(width, height);
  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {beats.map((shot, i) => {
        const from = toFrames(shot.start, fps);
        const frames = Math.max(1, toFrames(shot.end, fps) - from);
        const next = beats[i + 1];
        const overlap = next ? toFrames(next.fade, fps) : 0; // mốc sau mờ dần đè lên mốc này → không lộ nền
        return (
          <Sequence key={shot.n} from={from} durationInFrames={frames + overlap} name={`${shot.n} ${shot.kind}`}>
            <BeatView shot={shot} index={i} frames={frames} fps={fps} zoom={zoom} clipVolume={clipVolume} />
          </Sequence>
        );
      })}
      {subtitles.map((c, i) => (
        <Sequence key={`c${i}`} from={toFrames(c.start, fps)} durationInFrames={Math.max(1, toFrames(c.end - c.start, fps))}>
          <CaptionView text={c.text} size={Math.round(short * 0.048)} />
        </Sequence>
      ))}
      {logo ? <LogoView src={logo} short={short} /> : null}
      {audio ? <Audio src={staticFile(audio)} /> : null}
      {music ? <Audio src={staticFile(music)} volume={musicVolume} loop /> : null}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 3: Sửa `remotion/src/Root.tsx`** — thay toàn bộ:

```tsx
import { Composition } from "remotion";
import { DoodleVideo, VideoProps, defaultProps } from "./DoodleVideo";

// Props do `vidflow quick render` sinh (tmp/render-props.json). Độ dài = max(giọng đọc, mốc cuối) — tính sẵn ở Python.
export const RemotionRoot: React.FC = () => (
  <Composition
    id="DoodleVideo"
    component={DoodleVideo}
    defaultProps={defaultProps}
    fps={30}
    width={1920}
    height={1080}
    durationInFrames={300}
    calculateMetadata={({ props }: { props: VideoProps }) => ({
      durationInFrames: Math.max(1, Math.ceil(props.duration * props.fps)),
      fps: props.fps,
      width: props.width,
      height: props.height,
    })}
  />
);
```

- [ ] **Step 4: Typecheck**

Run: `cd remotion && npx tsc --noEmit`
Expected: không in gì, exit 0.

- [ ] **Step 5: Commit**

```bash
git add remotion/package.json remotion/package-lock.json remotion/src/DoodleVideo.tsx remotion/src/Root.tsx
git commit -m "feat(remotion): clips with hold-last-frame, scene transitions, logo, music; pin remotion 4.0.534"
```

(`remotion/out/doodle112.json` — props thử nghiệm cũ dạng `images` — không còn khớp; nằm trong `out/` bị gitignore, không cần sửa.)

---

### Task 5: Render thật end-to-end + tài liệu (Model: sonnet)

**Files:**
- Modify: `src/vidflow/quick/__init__.py` (docstring)
- Modify: `CLAUDE.md`
- Project tạm `projects/vf-render-smoke` (gitignore, xóa cuối task)

**Interfaces:**
- Consumes: mọi thứ của Task 1–4; lệnh `quick new`, `set-image`, `clip on`, `set-clip`, `render`.
- Produces: bằng chứng render thật chạy (ffprobe + so khung hình), tài liệu.

- [ ] **Step 1: Chạy toàn bộ test + typecheck**

Run: `uv run pytest -q && (cd remotion && npx tsc --noEmit)`
Expected: tất cả PASS, tsc exit 0.

- [ ] **Step 2: Dựng project nhỏ** (3 mốc × 3 s; mốc 2 có clip 2 s → 1 s giữ khung cuối; mốc 3 `cont` → cắt thẳng; giọng câm 9 s; nhạc sine 2 s để kiểm tra lặp). Thời gian mốc đặt bằng code `vidflow.quick` vì không chạy TTS — chỉ cho project thử, xóa ở Step 6.

```bash
cd /Users/anhnh/orca/projects/haha-editer
P=projects/vf-render-smoke; rm -rf "$P"
D=$(mktemp -d)
uv run vidflow quick new vf-render-smoke --preset doodle-giai-ma --title "Thử render"
uv run python - <<'EOF'
from pathlib import Path
from vidflow.quick import ops
from vidflow.quick.model import load_beats, save_beats
root = Path("projects/vf-render-smoke")
ops.set_beat_texts(root, ["Mốc một màu đỏ.", "Mốc hai có clip.", "Mốc ba nối cảnh."])
b = load_beats(root)
for i, x in enumerate(b.beats):
    x.start, x.end = i * 3.0, i * 3.0 + 2.85
b.beats[2].cont = True
save_beats(root, b)
EOF
ffmpeg -loglevel error -f lavfi -i color=c=red:s=1280x720 -frames:v 1 "$D/1.png"
ffmpeg -loglevel error -f lavfi -i color=c=blue:s=1280x720 -frames:v 1 "$D/2.png"
ffmpeg -loglevel error -f lavfi -i color=c=green:s=1280x720 -frames:v 1 "$D/3.png"
ffmpeg -loglevel error -f lavfi -i testsrc=size=1280x720:rate=30 -t 2 -pix_fmt yuv420p "$D/clip2.mp4"
ffmpeg -loglevel error -f lavfi -i anullsrc=r=24000:cl=mono -t 9 -c:a pcm_s16le "$P/audio/voice.wav"
ffmpeg -loglevel error -f lavfi -i "sine=frequency=220:sample_rate=44100" -t 2 "$P/audio/music.wav"
for n in 1 2 3; do uv run vidflow quick set-image -p "$P" $n "$D/$n.png"; done
uv run vidflow quick clip -p "$P" on 2
uv run vidflow quick set-clip -p "$P" 2 "$D/clip2.mp4"
uv run vidflow quick render -p "$P" --props-only && cat "$P/tmp/render-props.json"
ls -l "$P/tmp/render/public"/*
```

Expected: props có 3 mốc `image`, `video` (`clipLen` ≈ 2.0, `rate` 1.0), `image` (`cont: true`, `fade: 0.0`); mốc 2 `fade: 0.3`; `duration: 9.0`; `music: "audio/music.wav"`; public dir chỉ có symlink `images/`, `clips/`, `audio/`.

- [ ] **Step 3: Render bản 1 và kiểm tra**

```bash
uv run vidflow quick render -p "$P"
ffprobe -v error -show_entries stream=codec_type,width,height:format=duration -of compact "$P/out/vf-render-smoke-v1.mp4"
for t in 1.5 4.0 4.5 5.3 5.8 7.5; do
  ffmpeg -loglevel error -y -ss $t -i "$P/out/vf-render-smoke-v1.mp4" -frames:v 1 "$D/f$t.png"; done
uv run python - "$D" <<'EOF'
import sys
from PIL import Image, ImageChops
d = sys.argv[1]
im = lambda t: Image.open(f"{d}/f{t}.png").convert("RGB")
def diff(a, b):
    x, y = im(a), im(b)
    return sum(ImageChops.difference(x, y).convert("L").getdata()) / (x.width * x.height)
print("tâm 1.5s (đỏ):", im("1.5").getpixel((640, 300)))
print("tâm 7.5s (xanh lá):", im("7.5").getpixel((640, 300)))
print("clip đang phát 4.0 vs 4.5:", round(diff("4.0", "4.5"), 2))
print("giữ khung cuối 5.3 vs 5.8:", round(diff("5.3", "5.8"), 2))
EOF
```

Expected: `out/vf-render-smoke-v1.mp4` có stream video 1280×720 + stream audio, `duration` 9.0 ± 0.1; tâm 1.5 s ≈ (255, 0, 0), tâm 7.5 s ≈ (0, 128, 0); "đang phát" > 1.0 (testsrc chuyển động); "giữ khung cuối" < 1.0 (khung đứng yên). Mở `$D/f4.0.png` và `$D/f5.8.png` bằng Read để xem: phụ đề trắng nền đen ở đáy, ảnh phủ kín khung. Lần render đầu Remotion có thể tải Chrome Headless Shell — chờ.

Nếu Remotion lỗi không đọc được file qua symlink, hoặc "giữ khung cuối" ≥ 1.0: DỪNG, báo lại kèm log (không tự đổi thiết kế public dir / Freeze).

- [ ] **Step 4: Render bản 2 với tùy chọn khác**

```bash
uv run vidflow quick render -p "$P" --resolution 1080p --transition fade --clip-fit speed --no-music --no-subtitles
ffprobe -v error -show_entries stream=codec_type,width,height:format=duration -of compact "$P/out/vf-render-smoke-v2.mp4"
ls "$P/out"
```

Expected: `vf-render-smoke-v2.mp4` 1920×1080, 9.0 ± 0.1 s; `v1` vẫn còn (không ghi đè); không in cảnh báo nào (tốc độ 2/3 ≈ 0.667 nằm trong khoảng cho phép).

- [ ] **Step 5: Tài liệu**

`src/vidflow/quick/__init__.py` — thay docstring:

```python
"""Quy trình nhanh "1 ý tưởng → 1 video" (spec 2026-10-07, mở rộng 2026-10-12).

Hàm cho UI:
- preset: `list_presets()`, `load_preset(id)`, `channel_refs_dir(preset)`
- project: `create_quick(root, preset, title)`, `load_quick(root)`, `load_beats(root)`
- thao tác: `ops.set_ideas / pick_idea / set_beat_texts / set_prompt(s) / edit_prompt / set_review / set_image /
  mark_redo / record_fail / clear_errors / update_settings / list_beats / status_summary`
- nhân vật: `chars.lookup / char_rows / set_chars / set_char_image / promote / parse_refs`
- clip: `clips.set_clip_enabled / set_clip_prompts / set_clip / clip_todo / ready_clips`
- xuất MP4: `render.RenderOptions`, `render.build_render_props(root, opts)` (props thuần),
  `render.write_render_props`, `render.render_quick(root, opts)` → out/<tên>-vN.mp4
- việc nền: `jobs.claude_cmd(kind, root, preset)` (kind ∈ jobs.QUICK_KINDS; jobs.CHROME_KINDS cần Chrome),
  `jobs.review_cmd(root, preset, n, clip=)`, `voice.run_voice`, `build.build_quick` (draft CapCut, nhận clip)
"""
```

`CLAUDE.md` — thêm sau dòng "Quy trình nhanh (`vidflow quick`): …":

```markdown
- Xuất MP4 quy trình nhanh: `vidflow quick render -p <project>` (Remotion trong `remotion/`, cần `npm ci` một lần; phiên bản `remotion`/`@remotion/cli` khóa 4.0.534) → `projects/<tên>/out/<tên>-vN.mp4`; `--props-only` chỉ sinh `tmp/render-props.json`. Draft CapCut (`quick build`) dùng clip `ok` thay ảnh ở mốc có clip.
```

- [ ] **Step 6: Dọn project thử, chạy lại test, commit**

```bash
rm -rf projects/vf-render-smoke "$D"
uv run pytest -q
git add src/vidflow/quick/__init__.py CLAUDE.md
git commit -m "docs(quick): document Remotion render and CapCut clips"
```

Expected: test PASS; `git status` sạch (project thử nằm trong `projects/` bị gitignore và đã xóa).

---

## Self-review (đã chạy)

- Spec coverage: lệnh + 8 tùy chọn (Task 3); `render-props.json` với mốc `{src, kind, start, end, cont}`, `audio`, `subtitles`, `logo`, `music`, `fps`, kích thước (Task 2); clip ok → clip, còn lại ảnh, chưa có ảnh → khung trống + cảnh báo số mốc (Task 2); `trim` giữ khung cuối / `speed` (Task 2 + Task 4); `scene` = cont cắt, cảnh mới mờ 0.3 s (Task 2 + Task 4); logo từ bộ kênh, nhạc `audio/music.(mp3|wav)` âm lượng thấp (Task 2 + Task 4); `npx remotion render` trong `remotion/` với `--public-dir` + `--props`, ra `out/<tên>-vN.mp4` (Task 3); `OffthreadVideo`, chuyển cảnh, logo, nhạc, khóa phiên bản (Task 4); `assemble`/`quick build` nhận clip, cắt theo mốc (Task 1); kiểm thử pytest props + assemble với clip (Task 1–3), render thủ công (Task 5).
- Placeholder: không có TBD/TODO; mọi bước code có code đầy đủ.
- Tên nhất quán: `ready_clips`, `RenderOptions`, `RenderPlan`, `RenderResult`, `build_render_props`, `write_render_props`, `stage_public`, `next_output`, `render_cmd`, `render_quick`, `PROPS_FILE`, `PUBLIC_DIR`, `REMOTION_DIR`, `COMPOSITION`; khóa props Python ↔ `VideoProps` TSX: `fps, width, height, duration, beats[n, src, kind, start, end, cont, fade, rate, clipLen], audio, subtitles[start, end, text], zoom, clipVolume, logo, music, musicVolume`.
- Review Focus: 5 mục đều có test ở task sở hữu (Task 1, 2, 3).
