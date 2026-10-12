# Quick pipeline — Nhân vật @TÊN, nối cảnh, clip (Giai đoạn 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm nhân vật `@TÊN` (bộ kênh + riêng video), đánh dấu nối cảnh, clip động Veo cho quy trình nhanh — mô hình dữ liệu, thao tác (`ops`/`chars`/`clips`), lệnh CLI, job Claude và hướng dẫn agent. Chưa đụng giao diện và xuất video.

**Architecture:** Dữ liệu nằm trong `quick.yaml` (nhân vật video, cài đặt Flow, giới hạn clip) và `beats.json` (mỗi mốc thêm `refs`, `cont`, `clip`, `error`). Ảnh nhân vật tìm theo quy ước tên file (`refs/<ID>.png|jpg|webp`), không lưu đường dẫn trong YAML. Module mới `quick/chars.py` (tra cứu + tách `@TÊN`) và `quick/clips.py` (clip); `quick/ops.py` thêm luật bị chặn và các thao tác kiểm duyệt/lỗi. CLI và (sau này) UI đều gọi cùng các hàm này.

**Tech Stack:** Python 3.11, pydantic v2, typer, pytest (`uv run pytest`).

**Spec:** `docs/superpowers/specs/2026-10-12-quick-refs-clips-ui-design.md` (Giai đoạn 1).

## Global Constraints

- Không chạy `vidflow gen`, `vidflow estimate`, `vidflow refimg`; chỉ dùng tín dụng gói Google Flow.
- Không sửa tay `quick.yaml`, `beats.json`, `state.json` — mọi ghi qua hàm trong `vidflow.quick.*` / CLI.
- Prompt ảnh phải mở đầu/kết thúc bằng câu neo bộ kênh (`check_anchors` giữ nguyên).
- Prompt phải đạt kiểm duyệt (`pass` hoặc `override`) mới được gen.
- id nhân vật: `^[A-Z][A-Z0-9_]{1,23}$` (IN HOA, 2–24 ký tự).
- Độ phân giải clip mặc định `720p`; `max_clips` mặc định `12`.
- Thông báo lỗi bằng tiếng Việt, ném `VidflowError` (CLI in đỏ, exit 1, không traceback).
- Test không được ghi vào `presets/` thật — dùng fixture `quick_presets` (monkeypatch `PRESETS_DIR`).

Lệch nhỏ so với spec (đã cân nhắc, ghi rõ để người duyệt biết):
- `Character` không có trường `image`; ảnh tìm theo quy ước tên file (tránh ghi lại YAML bộ kênh, giữ chú thích trong file).
- Job gen character sheet đặt tên `sheets` (không phải `chars`) để không trùng lệnh liệt kê `quick chars`.
- Mốc/clip bị lỗi Flow KHÔNG tự quay lại danh sách việc; phải `quick retry` (tránh vòng lặp gen lỗi mãi). `promote` ghi lại YAML bộ kênh nên mất chú thích trong file đó.

## Review Focus

- `@tên` viết thường trong prompt (ví dụ `@modernyou`) → phải báo lỗi "viết IN HOA", không im lặng bỏ qua — test ở Task 3.
- Xóa (qua `set-chars`) nhân vật video đang được prompt dùng → từ chối, nêu tên — test ở Task 3.
- `beats.json`/`quick.yaml` tạo trước bản này (thiếu trường mới) vẫn đọc được — test ở Task 1.
- Gen lại ảnh một mốc đã có clip `ok` → clip phải chuyển `redo` (clip cũ dựng từ ảnh cũ) — test ở Task 6.
- Mốc bị Flow từ chối không lặp lại vô hạn trong `--todo`; `retry` đưa lại — test ở Task 5.

---

### Task 1: Mô hình dữ liệu (Character, FlowSettings, Clip, trường mới của Beat/QuickProject)

**Files:**
- Modify: `src/vidflow/quick/model.py`
- Modify: `src/vidflow/quick/ops.py:13` (IMAGE_EXTS chuyển sang model, ops import lại)
- Test: `tests/test_quick_model.py`

**Interfaces:**
- Produces: `IMAGE_EXTS`, `VIDEO_EXTS`, `CHAR_ID`, `Character(id, name="", desc, color="")`, `FlowSettings(image_model="Nano Banana 2", video_model="", resolution="720p")`, `Clip(enabled=False, prompt="", review=None, file=None, status="pending", error="")`; `Beat.refs: list[str]`, `Beat.cont: bool`, `Beat.clip: Clip`, `Beat.error: str`; `QuickProject.characters: list[Character]`, `.channel_chars: list[str] | None`, `.flow: FlowSettings`, `.max_clips: int`, `.allow_cont: bool`; `SUBDIRS` thêm `clips`, `refs`, `out`.

- [ ] **Step 1: Write the failing tests** — thêm vào `tests/test_quick_model.py` (và sửa test roundtrip hiện có vì JSON giờ có trường mới):

```python
from vidflow.quick.model import Character, Clip, FlowSettings


def test_beats_roundtrip_matches_spec_shape(tmp_path):
    b = Beats(aspect="16:9", beats=[Beat(n=1, start=0.0, end=2.31, text="Bạn bước vào bếp.", prompt="P",
                                         image="images/001_00-00.jpg",
                                         review={"verdict": "pass", "score": 8, "issues": []}, status="ok")])
    save_beats(tmp_path, b)
    raw = json.loads((tmp_path / "beats.json").read_text(encoding="utf-8"))
    assert raw == {"aspect": "16:9", "beats": [
        {"n": 1, "start": 0.0, "end": 2.31, "text": "Bạn bước vào bếp.", "prompt": "P",
         "image": "images/001_00-00.jpg", "review": {"verdict": "pass", "score": 8, "issues": []}, "status": "ok",
         "refs": [], "cont": False,
         "clip": {"enabled": False, "prompt": "", "review": None, "file": None, "status": "pending", "error": ""},
         "error": ""}]}
    assert load_beats(tmp_path) == b


def test_old_files_without_new_fields_still_load(tmp_path):
    (tmp_path / "beats.json").write_text(json.dumps({"aspect": "16:9", "beats": [
        {"n": 1, "start": 0.0, "end": 1.0, "text": "A", "prompt": "", "image": None, "review": None,
         "status": "pending"}]}), encoding="utf-8")
    b = load_beats(tmp_path).beats[0]
    assert b.refs == [] and b.cont is False and b.clip == Clip() and b.error == ""
    (tmp_path / "quick.yaml").write_text("preset: x\ntitle: T\nideas: []\npicked: null\nstage: new\n", encoding="utf-8")
    q = load_quick(tmp_path)
    assert q.characters == [] and q.channel_chars is None
    assert q.flow == FlowSettings() and q.flow.resolution == "720p" and q.flow.video_model == ""
    assert q.max_clips == 12 and q.allow_cont is True


def test_character_id_must_be_upper(tmp_path):
    Character(id="MODERNYOU", desc="d")
    for bad in ("modernyou", "A", "1ABC", "MODERN-YOU", "X" * 25):
        with pytest.raises(Exception):
            Character(id=bad, desc="d")


def test_create_quick_makes_new_dirs(tmp_path):
    root = tmp_path / "q"
    create_quick(root, preset="x")
    for d in ("clips", "refs", "out"):
        assert (root / d).is_dir()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_quick_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'Character'`.

- [ ] **Step 3: Implement** — trong `src/vidflow/quick/model.py`:

Đổi import pydantic: `from pydantic import BaseModel, Field, ValidationError`.

Thay dòng `SUBDIRS = ...` và thêm hằng ngay sau `BEATS_FILE`:

```python
SUBDIRS = ("images", "clips", "refs", "out", "audio", "audio/beats", "logs", "tmp")
IMAGE_EXTS = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png", ".webp": ".webp"}
VIDEO_EXTS = {".mp4": ".mp4", ".mov": ".mov", ".webm": ".webm"}
CHAR_ID = r"^[A-Z][A-Z0-9_]{1,23}$"
```

Thêm trước `class QuickProject`:

```python
class Character(BaseModel):
    """Nhân vật @ID. Ảnh sheet tìm theo quy ước: refs/<ID>.png|jpg|webp (xem quick/chars.py)."""
    id: str = Field(pattern=CHAR_ID)
    name: str = ""
    desc: str
    color: str = ""


class FlowSettings(BaseModel):
    image_model: str = "Nano Banana 2"
    video_model: str = ""  # bắt buộc chọn trước khi gen clip
    resolution: Literal["720p", "1080p"] = "720p"
```

Thêm vào cuối `QuickProject` (trước `def picked_idea`):

```python
    characters: list[Character] = []
    channel_chars: list[str] | None = None  # None = dùng mọi nhân vật của bộ kênh
    flow: FlowSettings = Field(default_factory=FlowSettings)
    max_clips: int = Field(default=12, ge=0)
    allow_cont: bool = True
```

Thêm trước `class Beat` (sau `class Review`):

```python
class Clip(BaseModel):
    enabled: bool = False
    prompt: str = ""
    review: Review | None = None
    file: str | None = None  # clips/NNN_MM-SS.mp4
    status: Literal["pending", "ok", "redo", "error"] = "pending"
    error: str = ""
```

Thêm vào cuối `class Beat` (sau `status`):

```python
    refs: list[str] = []  # @ID trong prompt ảnh — CLI tự tách, agent không khai
    cont: bool = False    # nối cảnh: đính ảnh mốc liền trước khi gen
    clip: Clip = Field(default_factory=Clip)
    error: str = ""       # lý do Flow từ chối ảnh gần nhất (rỗng = không lỗi)
```

Trong `src/vidflow/quick/ops.py`: xóa dòng `IMAGE_EXTS = {...}` và thêm `IMAGE_EXTS` vào import từ `vidflow.quick.model` (giữ tên `ops.IMAGE_EXTS` cho `quick/build.py` đang import):

```python
from vidflow.quick.model import (IMAGE_EXTS, STAGES, Beat, Beats, Idea, QuickProject, Review, image_name,
                                 load_beats, load_quick, require_beats, save_beats, save_quick)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_quick_model.py tests/test_quick_cli.py tests/test_quick_build.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vidflow/quick/model.py src/vidflow/quick/ops.py tests/test_quick_model.py
git commit -m "feat(quick): data model for characters, flow settings, clips, cont"
```

---

### Task 2: Nhân vật và logo trong bộ kênh + fixture test

**Files:**
- Modify: `src/vidflow/quick/preset.py`
- Modify: `tests/conftest.py` (thêm fixture quick)
- Test: `tests/test_quick_preset.py`

**Interfaces:**
- Consumes: `Character` (Task 1).
- Produces: `Preset.characters: list[Character]`, `Preset.logo: str`, `channel_refs_dir(p: Preset) -> Path` (= `PRESETS_DIR/refs/<preset-id>`, đọc `PRESETS_DIR` lúc gọi). Fixtures `quick_presets` (thư mục presets tạm có `@MODERNYOU`), `qroot` (project nhanh 4 mốc A–D, thời gian 0/4/8/12 s), `P` (hàm bọc câu neo), `img` (hàm tạo file ảnh giả).

- [ ] **Step 1: Write the failing test** — thêm vào `tests/test_quick_preset.py`:

```python
def test_preset_characters_and_channel_refs_dir(quick_presets):
    from vidflow.quick.preset import channel_refs_dir, load_preset
    p = load_preset("doodle-giai-ma")
    assert [c.id for c in p.characters] == ["MODERNYOU"]
    assert p.logo == ""
    assert channel_refs_dir(p) == quick_presets / "refs" / "doodle-giai-ma"


def test_real_preset_without_characters_loads():
    from vidflow.quick.preset import load_preset
    assert load_preset("doodle-giai-ma").characters == []
```

Và thêm vào cuối `tests/conftest.py`:

```python
# ---- quy trình nhanh (spec 2026-10-12) ----

@pytest.fixture
def quick_presets(tmp_path, monkeypatch):
    """Bản sao bộ kênh doodle-giai-ma có @MODERNYOU, trong tmp — không ghi vào presets/ thật."""
    import vidflow.quick.preset as pm
    from vidflow.quick.model import Character

    d = tmp_path / "presets"
    p = pm.load_preset("doodle-giai-ma")
    p.characters = [Character(id="MODERNYOU", name="Người hiện đại",
                              desc="round-headed modern person in a cobalt t-shirt", color="#3557D6")]
    pm.save_preset(p, presets_dir=d)
    monkeypatch.setattr(pm, "PRESETS_DIR", d)
    return d


@pytest.fixture
def qroot(tmp_path, quick_presets):
    """Project nhanh 4 mốc A–D, mỗi mốc 4 giây (0, 4, 8, 12)."""
    from vidflow.quick import ops
    from vidflow.quick.model import create_quick, load_beats, save_beats

    root = tmp_path / "vid"
    create_quick(root, preset="doodle-giai-ma", title="T")
    ops.set_beat_texts(root, ["A.", "B.", "C.", "D."])
    b = load_beats(root)
    for i, beat in enumerate(b.beats):
        beat.start, beat.end = i * 4.0, i * 4.0 + 4.0
    save_beats(root, b)
    return root


@pytest.fixture
def P(quick_presets):
    """P("mô tả") → prompt ảnh có đủ câu neo của bộ kênh."""
    import vidflow.quick.preset as pm

    pr = pm.load_preset("doodle-giai-ma")
    return lambda s: f"{pr.style_anchor_start} {s}, {pr.style_anchor_end}"


@pytest.fixture
def img(tmp_path):
    def make(name="a.png", data=b"\x89PNGx"):
        f = tmp_path / "dl" / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        return f
    return make
```

(Nếu `tests/conftest.py` chưa `import pytest` ở đầu file thì thêm.)

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_quick_preset.py -v`
Expected: FAIL — `ImportError: cannot import name 'channel_refs_dir'` / `Preset` không có `characters`.

- [ ] **Step 3: Implement** — `src/vidflow/quick/preset.py`:

Thêm import: `from vidflow.quick.model import Character`.

Trong `class Preset` thêm cuối:

```python
    characters: list[Character] = []
    logo: str = ""  # đường dẫn logo kênh (tương đối repo), dùng khi xuất MP4
```

Thêm sau `brief_path`:

```python
def channel_refs_dir(p: Preset) -> Path:
    """Thư mục ảnh sheet nhân vật của bộ kênh: presets/refs/<preset-id>/<ID>.png|jpg|webp."""
    return _dir(None) / "refs" / p.id
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_quick_preset.py tests/test_quick_model.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vidflow/quick/preset.py tests/conftest.py tests/test_quick_preset.py
git commit -m "feat(quick): channel characters and logo in presets"
```

---

### Task 3: `quick/chars.py` — tra cứu, tách @TÊN, ảnh sheet, đưa vào bộ kênh + CLI

**Files:**
- Create: `src/vidflow/quick/chars.py`
- Modify: `src/vidflow/quick/cli.py` (lệnh `set-chars`, `char-image`, `chars`, `promote`)
- Test: `tests/test_quick_chars.py`

**Interfaces:**
- Consumes: `Character`, `IMAGE_EXTS`, `load_quick/save_quick/load_beats` (Task 1); `channel_refs_dir`, `load_preset`, `save_preset` (Task 2).
- Produces:
  - `CharRef(char: Character, scope: "channel"|"video", image: Path | None)`
  - `parse_refs(text: str) -> list[str]` (thứ tự xuất hiện, không trùng; `@tên` thường → `VidflowError`)
  - `lookup(root, q=None, preset=None) -> dict[str, CharRef]`
  - `check_known(names: list[str], known: dict[str, CharRef]) -> None`
  - `find_image(folder: Path, char_id: str) -> Path | None`
  - `set_chars(root, items: list[dict]) -> QuickProject`
  - `set_char_image(root, char_id, src, *, channel=False) -> Path`
  - `promote(root, char_id) -> Preset`
  - `char_rows(root) -> list[dict]` với khóa `id,name,desc,color,scope,image,uses,blocked`

- [ ] **Step 1: Write the failing tests** — `tests/test_quick_chars.py`:

```python
import json

import pytest
from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.errors import VidflowError
from vidflow.quick import chars, ops
from vidflow.quick.model import load_beats, load_quick
from vidflow.quick.preset import load_preset

runner = CliRunner()
FARMER = {"id": "FARMER", "name": "Nông dân", "desc": "hunched neolithic farmer, rough tunic", "color": "#8B5E3C"}


def test_parse_refs_order_unique_and_punctuation():
    assert chars.parse_refs("@FARMER's hoe, @MODERNYOU and @FARMER.") == ["FARMER", "MODERNYOU"]
    assert chars.parse_refs("") == []


def test_parse_refs_rejects_lowercase():
    with pytest.raises(VidflowError, match="IN HOA"):
        chars.parse_refs("a doodle of @modernyou waking up")


def test_lookup_merges_channel_and_video(qroot):
    chars.set_chars(qroot, [FARMER])
    known = chars.lookup(qroot)
    assert set(known) == {"MODERNYOU", "FARMER"}
    assert known["MODERNYOU"].scope == "channel" and known["FARMER"].scope == "video"
    assert known["FARMER"].image is None


def test_channel_chars_filter(qroot):
    ops.update_settings(qroot, channel_chars=[])
    assert "MODERNYOU" not in chars.lookup(qroot)


def test_set_chars_validation(qroot):
    with pytest.raises(VidflowError, match="Trùng id"):
        chars.set_chars(qroot, [FARMER, FARMER])
    with pytest.raises(VidflowError, match="bộ kênh"):
        chars.set_chars(qroot, [{"id": "MODERNYOU", "desc": "x"}])
    with pytest.raises(VidflowError, match="không hợp lệ"):
        chars.set_chars(qroot, [{"id": "farmer", "desc": "x"}])


def test_set_chars_refuses_removing_char_in_use(qroot, P):
    chars.set_chars(qroot, [FARMER])
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("@FARMER digging"), "verdict": "pass", "score": 8}])
    with pytest.raises(VidflowError, match="@FARMER"):
        chars.set_chars(qroot, [])
    assert [c.id for c in load_quick(qroot).characters] == ["FARMER"]


def test_set_char_image_video_and_channel(qroot, img, quick_presets):
    chars.set_chars(qroot, [FARMER])
    dest = chars.set_char_image(qroot, "FARMER", img("f.jpeg"))
    assert dest == qroot / "refs" / "FARMER.jpg" and dest.is_file()
    dest2 = chars.set_char_image(qroot, "FARMER", img("f.png"))
    assert dest2.name == "FARMER.png" and not dest.exists()  # thay ảnh cũ khác đuôi
    with pytest.raises(VidflowError, match="--channel"):
        chars.set_char_image(qroot, "MODERNYOU", img())
    ch = chars.set_char_image(qroot, "MODERNYOU", img(), channel=True)
    assert ch == quick_presets / "refs" / "doodle-giai-ma" / "MODERNYOU.png"
    assert chars.lookup(qroot)["MODERNYOU"].image == ch
    with pytest.raises(VidflowError, match="không hỗ trợ"):
        chars.set_char_image(qroot, "FARMER", img("x.gif"))


def test_promote_moves_char_and_image(qroot, img, quick_presets):
    chars.set_chars(qroot, [FARMER])
    chars.set_char_image(qroot, "FARMER", img())
    chars.promote(qroot, "FARMER")
    assert "FARMER" in [c.id for c in load_preset("doodle-giai-ma").characters]
    assert load_quick(qroot).characters == []
    assert (quick_presets / "refs" / "doodle-giai-ma" / "FARMER.png").is_file()
    assert chars.lookup(qroot)["FARMER"].scope == "channel"


def test_char_rows_counts_uses_and_blocked(qroot, P):
    chars.set_chars(qroot, [FARMER])
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("@FARMER digging"), "verdict": "pass", "score": 8},
                            {"n": 2, "prompt": P("@FARMER and @MODERNYOU"), "verdict": "pass", "score": 8}])
    rows = {r["id"]: r for r in chars.char_rows(qroot)}
    assert rows["FARMER"]["uses"] == 2 and rows["FARMER"]["blocked"] == 2
    assert rows["MODERNYOU"]["uses"] == 1 and rows["MODERNYOU"]["scope"] == "channel"


def test_cli_chars_commands(qroot, tmp_path, img):
    f = tmp_path / "chars.json"
    f.write_text(json.dumps([FARMER]), encoding="utf-8")
    r = runner.invoke(app, ["quick", "set-chars", "-p", str(qroot), "--json", str(f)])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quick", "char-image", "-p", str(qroot), "FARMER", str(img())])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quick", "chars", "-p", str(qroot), "--json"])
    data = json.loads(r.output)
    assert {d["id"] for d in data} == {"MODERNYOU", "FARMER"}
    r = runner.invoke(app, ["quick", "char-image", "-p", str(qroot), "NOBODY", str(img())])
    assert r.exit_code == 1 and "Traceback" not in r.output
```

(`ops.update_settings` dùng ở `test_channel_chars_filter` được viết ở Task 6; đánh dấu test đó `@pytest.mark.skip(reason="Task 6")` ở Task này và bỏ skip ở Task 6.)

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_quick_chars.py -v`
Expected: FAIL — `ImportError: cannot import name 'chars'`.

- [ ] **Step 3: Implement `src/vidflow/quick/chars.py`**

```python
"""Nhân vật @TÊN (spec 2026-10-12): bộ kênh + riêng video, ảnh sheet theo quy ước tên file, tách @TÊN từ prompt."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vidflow.errors import VidflowError
from vidflow.quick.model import IMAGE_EXTS, Character, QuickProject, load_beats, load_quick, save_quick
from vidflow.quick.preset import Preset, channel_refs_dir, load_preset, save_preset

REF_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_]*)")
VIDEO_REFS = "refs"


@dataclass
class CharRef:
    char: Character
    scope: Literal["channel", "video"]
    image: Path | None


def find_image(folder: Path, char_id: str) -> Path | None:
    for ext in (".png", ".jpg", ".webp"):
        f = Path(folder) / f"{char_id}{ext}"
        if f.is_file():
            return f
    return None


def parse_refs(text: str) -> list[str]:
    """Các @TÊN theo thứ tự xuất hiện, không trùng. @tên có chữ thường → lỗi (phải IN HOA)."""
    out: list[str] = []
    for m in REF_RE.finditer(text or ""):
        name = m.group(1)
        if name != name.upper():
            raise VidflowError(f"@{name}: tên nhân vật phải viết IN HOA (@{name.upper()}).")
        if name not in out:
            out.append(name)
    return out


def lookup(root: Path, q: QuickProject | None = None, preset: Preset | None = None) -> dict[str, CharRef]:
    root = Path(root)
    q = q or load_quick(root)
    preset = preset or load_preset(q.preset)
    out: dict[str, CharRef] = {}
    cdir = channel_refs_dir(preset)
    for c in preset.characters:
        if q.channel_chars is None or c.id in q.channel_chars:
            out[c.id] = CharRef(c, "channel", find_image(cdir, c.id))
    for c in q.characters:
        if c.id in out:
            raise VidflowError(f"@{c.id} trùng với nhân vật của bộ kênh — đổi tên nhân vật riêng của video.")
        out[c.id] = CharRef(c, "video", find_image(root / VIDEO_REFS, c.id))
    return out


def check_known(names: list[str], known: dict[str, CharRef]) -> None:
    unknown = [n for n in names if n not in known]
    if unknown:
        have = ", ".join("@" + k for k in known) or "(chưa có nhân vật nào)"
        raise VidflowError(f"Prompt nhắc nhân vật chưa khai báo: {', '.join('@' + u for u in unknown)}. Có: {have}")


def _used_ids(root: Path) -> set[str]:
    beats = load_beats(root)
    used: set[str] = set()
    for b in beats.beats if beats else []:
        used.update(b.refs)
        used.update(parse_refs(b.clip.prompt))
    return used


def set_chars(root: Path, items: list[dict]) -> QuickProject:
    """Ghi toàn bộ nhân vật riêng của video (quick-writer đề xuất, người dùng sửa)."""
    root = Path(root)
    q = load_quick(root)
    preset = load_preset(q.preset)
    try:
        new = [Character.model_validate(i) for i in items]
    except Exception as e:
        raise VidflowError(f"Nhân vật không hợp lệ (id IN HOA 2–24 ký tự A-Z0-9_, cần desc): {e}") from e
    ids = [c.id for c in new]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise VidflowError(f"Trùng id nhân vật: {', '.join(dup)}")
    clash = sorted(set(ids) & {c.id for c in preset.characters})
    if clash:
        raise VidflowError(f"Trùng nhân vật của bộ kênh: {', '.join(clash)}")
    in_use = sorted(({c.id for c in q.characters} - set(ids)) & _used_ids(root))
    if in_use:
        raise VidflowError(f"Không xóa được nhân vật đang dùng trong prompt: {', '.join('@' + i for i in in_use)}")
    q.characters = new
    save_quick(root, q)
    return q


def set_char_image(root: Path, char_id: str, src: Path, *, channel: bool = False) -> Path:
    """Gắn ảnh sheet: video → <project>/refs/<ID>.<ext>; channel → presets/refs/<preset>/<ID>.<ext>."""
    root, src = Path(root), Path(src)
    if not src.is_file():
        raise VidflowError(f"Không thấy file ảnh {src}")
    ext = IMAGE_EXTS.get(src.suffix.lower())
    if not ext:
        raise VidflowError(f"Định dạng ảnh không hỗ trợ: {src.suffix} (dùng jpg/png/webp)")
    q = load_quick(root)
    preset = load_preset(q.preset)
    channel_ids = {c.id for c in preset.characters}
    if channel:
        if char_id not in channel_ids:
            raise VidflowError(f"Bộ kênh {preset.id} không có nhân vật @{char_id}.")
        folder = channel_refs_dir(preset)
    else:
        if char_id not in {c.id for c in q.characters}:
            hint = " (là nhân vật bộ kênh — thêm --channel)" if char_id in channel_ids else ""
            raise VidflowError(f"Video không có nhân vật @{char_id}{hint}.")
        folder = root / VIDEO_REFS
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{char_id}{ext}"
    old = find_image(folder, char_id)
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    if old and old.resolve() != dest.resolve():
        old.unlink()
    return dest


def promote(root: Path, char_id: str) -> Preset:
    """Chuyển nhân vật riêng của video vào bộ kênh (kèm ảnh). Ghi lại YAML bộ kênh."""
    root = Path(root)
    q = load_quick(root)
    preset = load_preset(q.preset)
    c = next((x for x in q.characters if x.id == char_id), None)
    if c is None:
        raise VidflowError(f"Video không có nhân vật riêng @{char_id}.")
    preset.characters.append(c)
    save_preset(preset)
    img = find_image(root / VIDEO_REFS, char_id)
    if img:
        folder = channel_refs_dir(preset)
        folder.mkdir(parents=True, exist_ok=True)
        shutil.move(str(img), str(folder / img.name))
    q.characters = [x for x in q.characters if x.id != char_id]
    if q.channel_chars is not None and char_id not in q.channel_chars:
        q.channel_chars.append(char_id)
    save_quick(root, q)
    return preset


def char_rows(root: Path) -> list[dict]:
    """Cho `quick chars` và UI: mỗi nhân vật + ảnh + số mốc dùng + số mốc chờ ảnh bị chặn vì thiếu sheet."""
    root = Path(root)
    beats = load_beats(root)
    bl = beats.beats if beats else []
    rows = []
    for cid, ref in lookup(root).items():
        uses = [b for b in bl if cid in b.refs or cid in parse_refs(b.clip.prompt)]
        rows.append({**ref.char.model_dump(), "scope": ref.scope,
                     "image": str(ref.image) if ref.image else None,
                     "uses": len(uses),
                     "blocked": 0 if ref.image else sum(1 for b in uses if b.status in ("pending", "redo"))})
    return rows
```

- [ ] **Step 4: Implement CLI** — `src/vidflow/quick/cli.py`: thêm `chars` vào import `from vidflow.quick import chars, jobs, ops`, rồi thêm vào phần "helper cho job Claude":

```python
@_cmd(quick_app, "set-chars")
def set_chars(project: ProjectOpt, json_file: JsonFile):
    """Ghi nhân vật riêng của video [{id, name, desc, color}]."""
    q = chars.set_chars(project, _read_json(json_file))
    typer.echo(f"Đã ghi {len(q.characters)} nhân vật: {', '.join('@' + c.id for c in q.characters)}")


@_cmd(quick_app, "char-image")
def char_image(project: ProjectOpt, char_id: Annotated[str, typer.Argument(help="ID nhân vật (IN HOA)")],
               file: Annotated[Path, typer.Argument()],
               channel: Annotated[bool, typer.Option("--channel", help="Nhân vật của bộ kênh")] = False):
    """Gắn ảnh character sheet cho nhân vật."""
    dest = chars.set_char_image(project, char_id, file, channel=channel)
    typer.echo(f"@{char_id} → {dest}")


@_cmd(quick_app, "chars")
def chars_list(project: ProjectOpt, json_out: Annotated[bool, typer.Option("--json")] = False):
    """Liệt kê nhân vật (bộ kênh + video), ảnh, số mốc dùng, số mốc bị chặn."""
    rows = chars.char_rows(project)
    if json_out:
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    for r in rows:
        img = "có ảnh" if r["image"] else f"THIẾU ẢNH (chặn {r['blocked']})"
        typer.echo(f"@{r['id']:<14} {r['scope']:<7} {r['uses']:>3} mốc · {img} · {r['desc'][:50]}")


@_cmd(quick_app, "promote")
def promote(project: ProjectOpt, char_id: Annotated[str, typer.Argument()]):
    """Đưa nhân vật riêng của video vào bộ kênh."""
    p = chars.promote(project, char_id)
    typer.echo(f"@{char_id} đã thuộc bộ kênh {p.id}")
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_quick_chars.py -v`
Expected: PASS trừ các test dùng `ops.set_prompts` với `@TÊN` — chúng cần Task 4. Đánh dấu tạm `test_set_chars_refuses_removing_char_in_use` và `test_char_rows_counts_uses_and_blocked` bằng `@pytest.mark.skip(reason="Task 4")` nếu Task 4 chưa xong; bỏ skip ở Task 4.

- [ ] **Step 6: Commit**

```bash
git add src/vidflow/quick/chars.py src/vidflow/quick/cli.py tests/test_quick_chars.py
git commit -m "feat(quick): @character registry, sheet images, promote, CLI"
```

---

### Task 4: Prompt có @TÊN và nối cảnh, sửa prompt, kiểm duyệt lại, lỗi Flow

**Files:**
- Modify: `src/vidflow/quick/ops.py`
- Modify: `src/vidflow/quick/cli.py` (`set-prompt --cont`, `edit-prompt`, `set-review`, `fail`, `retry`, `redo --clip`)
- Test: `tests/test_quick_prompts.py`; bỏ skip 2 test ở `tests/test_quick_chars.py`

**Interfaces:**
- Consumes: `parse_refs`, `check_known`, `lookup` (Task 3).
- Produces:
  - `set_prompts(root, items)` — item nhận thêm `cont: bool` (tùy chọn); ghi `beat.refs` tự tách.
  - `set_prompt(root, n, prompt, *, verdict="pass", score=0, issues=None, cont: bool | None = None) -> Beat`
  - `edit_prompt(root, n, prompt, *, clip=False) -> Beat` (xóa review)
  - `set_review(root, n, verdict, *, score=0, issues=None, clip=False) -> Beat` (`verdict ∈ pass|fail|override`)
  - `record_fail(root, n, reason, *, clip=False) -> Beat`
  - `clear_errors(root, ns: list[int] | None = None, *, clip=False) -> int`
  - `mark_redo(root, ns, *, clip=False) -> Beats`
  - `set_image` xóa `beat.error`; nếu `beat.clip.status == "ok"` → `"redo"`.

- [ ] **Step 1: Write the failing tests** — `tests/test_quick_prompts.py`:

```python
import pytest
from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.errors import VidflowError
from vidflow.quick import chars, ops
from vidflow.quick.model import load_beats

runner = CliRunner()


def test_set_prompts_extracts_refs_and_rejects_unknown(qroot, P):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("@MODERNYOU wakes up"), "verdict": "pass", "score": 8}])
    assert load_beats(qroot).beats[0].refs == ["MODERNYOU"]
    with pytest.raises(VidflowError, match="@GHOST"):
        ops.set_prompts(qroot, [{"n": 2, "prompt": P("@GHOST"), "verdict": "pass", "score": 8}])


def test_set_prompts_batch_is_atomic(qroot, P):
    with pytest.raises(VidflowError):
        ops.set_prompts(qroot, [{"n": 1, "prompt": P("ok"), "verdict": "pass", "score": 8},
                                {"n": 2, "prompt": P("@GHOST"), "verdict": "pass", "score": 8}])
    assert load_beats(qroot).beats[0].prompt == ""


def test_cont_rules(qroot, P):
    ops.set_prompts(qroot, [{"n": 2, "prompt": P("x"), "verdict": "pass", "score": 8, "cont": True}])
    assert load_beats(qroot).beats[1].cont is True
    ops.set_prompts(qroot, [{"n": 2, "prompt": P("y"), "verdict": "pass", "score": 8}])
    assert load_beats(qroot).beats[1].cont is True  # không gửi cont → giữ nguyên
    with pytest.raises(VidflowError, match="Mốc 1"):
        ops.set_prompts(qroot, [{"n": 1, "prompt": P("x"), "verdict": "pass", "score": 8, "cont": True}])
    ops.update_settings(qroot, allow_cont=False)
    with pytest.raises(VidflowError, match="nối cảnh"):
        ops.set_prompts(qroot, [{"n": 3, "prompt": P("x"), "verdict": "pass", "score": 8, "cont": True}])


def test_edit_prompt_clears_review_then_set_review(qroot, P):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("a"), "verdict": "pass", "score": 8}])
    b = ops.edit_prompt(qroot, 1, P("@MODERNYOU b"))
    assert b.review is None and b.refs == ["MODERNYOU"]
    with pytest.raises(VidflowError, match="câu neo"):
        ops.edit_prompt(qroot, 1, "no anchors")
    b = ops.set_review(qroot, 1, "fail", score=5, issues=["mơ hồ"])
    assert b.review.verdict == "fail" and b.review.issues == ["mơ hồ"]
    b = ops.set_review(qroot, 1, "override")
    assert b.review.verdict == "override"
    with pytest.raises(VidflowError):
        ops.set_review(qroot, 1, "maybe")
    with pytest.raises(VidflowError, match="chưa có prompt"):
        ops.set_review(qroot, 2, "pass")


def test_edit_and_review_clip_prompt(qroot):
    b = ops.edit_prompt(qroot, 1, "doodle motion of @MODERNYOU stretching. Sound: a yawn.", clip=True)
    assert b.clip.prompt.startswith("doodle motion") and b.clip.review is None
    b = ops.set_review(qroot, 1, "pass", score=8, clip=True)
    assert b.clip.review.verdict == "pass" and b.review is None


def test_fail_retry_and_set_image_clears_error(qroot, img):
    ops.record_fail(qroot, 2, "Flow: vi phạm chính sách")
    assert load_beats(qroot).beats[1].error == "Flow: vi phạm chính sách"
    with pytest.raises(VidflowError):
        ops.record_fail(qroot, 2, "  ")
    assert ops.clear_errors(qroot) == 1
    assert load_beats(qroot).beats[1].error == ""
    ops.record_fail(qroot, 3, "lỗi")
    ops.set_image(qroot, 3, img())
    assert load_beats(qroot).beats[2].error == ""


def test_clip_fail_and_retry(qroot):
    ops.record_fail(qroot, 1, "Veo lỗi", clip=True)
    c = load_beats(qroot).beats[0].clip
    assert c.status == "error" and c.error == "Veo lỗi"
    assert ops.clear_errors(qroot, [1], clip=True) == 1
    c = load_beats(qroot).beats[0].clip
    assert c.status == "redo" and c.error == ""


def test_cli_review_fail_retry(qroot, P):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("a"), "verdict": "fail", "score": 4}])
    r = runner.invoke(app, ["quick", "set-review", "-p", str(qroot), "1", "--verdict", "pass", "--score", "8"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quick", "fail", "-p", str(qroot), "2", "--reason", "từ chối"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quick", "retry", "-p", str(qroot)])
    assert r.exit_code == 0 and "1" in r.output
    r = runner.invoke(app, ["quick", "set-prompt", "-p", str(qroot), "2", "--prompt", P("b"), "--cont"])
    assert r.exit_code == 0, r.output
    assert load_beats(qroot).beats[1].cont is True
```

(`ops.update_settings` dùng ở `test_cont_rules` — thuộc Task 6. Nếu làm Task 4 trước Task 6, thêm tạm `@pytest.mark.skip(reason="Task 6")` cho riêng test đó và bỏ ở Task 6.)

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_quick_prompts.py -v`
Expected: FAIL — `AttributeError: module 'vidflow.quick.ops' has no attribute 'edit_prompt'` và `refs` rỗng.

- [ ] **Step 3: Implement trong `src/vidflow/quick/ops.py`**

Thêm import: `from vidflow.quick.chars import check_known, lookup, parse_refs`.

Thay `set_prompts` và `set_prompt`:

```python
def _check_cont(beat: Beat, cont: bool, q: QuickProject) -> bool:
    if cont and beat.n == 1:
        raise VidflowError("Mốc 1 không nối cảnh được (không có mốc trước).")
    if cont and not q.allow_cont:
        raise VidflowError("Video này tắt nối cảnh (allow_cont=false) — bật bằng `vidflow quick settings --allow-cont`.")
    return cont


def set_prompts(root: Path, items: list[dict]) -> Beats:
    """items: [{n, prompt, verdict, score, issues?, cont?}] — ghi prompt + kết quả tự kiểm duyệt.
    `refs` tự tách từ @TÊN trong prompt; tên chưa khai báo → từ chối cả lô."""
    q = load_quick(root)
    preset = load_preset(q.preset)
    beats = require_beats(root)
    known = lookup(root, q, preset)
    for it in items:
        beat = beats.get(int(it["n"]))
        prompt = str(it.get("prompt", "")).strip()
        check_anchors(prompt, preset)
        refs = parse_refs(prompt)
        check_known(refs, known)
        verdict = it.get("verdict", "pass")
        if verdict not in ("pass", "fail"):
            raise VidflowError("verdict phải là pass hoặc fail")
        if "cont" in it:
            beat.cont = _check_cont(beat, bool(it["cont"]), q)
        beat.prompt, beat.refs = prompt, refs
        beat.review = Review(verdict=verdict, score=float(it.get("score", 0)), issues=list(it.get("issues") or []))
    save_beats(root, beats)
    if all(b.review and b.review.verdict in PASSING for b in beats.beats):
        advance(root, "prompted", q)
    return beats


def set_prompt(root: Path, n: int, prompt: str, *, verdict: str = "pass", score: float = 0,
               issues: list[str] | None = None, cont: bool | None = None) -> Beat:
    item = {"n": n, "prompt": prompt, "verdict": verdict, "score": score, "issues": issues or []}
    if cont is not None:
        item["cont"] = cont
    return set_prompts(root, [item]).get(n)


def edit_prompt(root: Path, n: int, prompt: str, *, clip: bool = False) -> Beat:
    """Người dùng sửa tay prompt ảnh/clip: lưu và xóa kết quả kiểm duyệt (phải kiểm duyệt lại mới gen)."""
    q = load_quick(root)
    preset = load_preset(q.preset)
    beats = require_beats(root)
    beat = beats.get(n)
    prompt = prompt.strip()
    if not prompt:
        raise VidflowError("Prompt rỗng.")
    refs = parse_refs(prompt)
    check_known(refs, lookup(root, q, preset))
    if clip:
        beat.clip.prompt, beat.clip.review = prompt, None
    else:
        check_anchors(prompt, preset)
        beat.prompt, beat.refs, beat.review = prompt, refs, None
    save_beats(root, beats)
    return beat


def set_review(root: Path, n: int, verdict: str, *, score: float = 0, issues: list[str] | None = None,
               clip: bool = False) -> Beat:
    """Ghi kết quả kiểm duyệt một mốc (prompt-reviewer, hoặc người dùng duyệt tay = override)."""
    if verdict not in ("pass", "fail", "override"):
        raise VidflowError("verdict phải là pass, fail hoặc override")
    beats = require_beats(root)
    beat = beats.get(n)
    if not (beat.clip.prompt if clip else beat.prompt):
        raise VidflowError(f"Mốc {n} chưa có prompt {'clip' if clip else 'ảnh'} để kiểm duyệt.")
    review = Review(verdict=verdict, score=float(score), issues=list(issues or []))
    if clip:
        beat.clip.review = review
    else:
        beat.review = review
    save_beats(root, beats)
    if not clip and all(b.review and b.review.verdict in PASSING for b in beats.beats):
        advance(root, "prompted")
    return beat


def record_fail(root: Path, n: int, reason: str, *, clip: bool = False) -> Beat:
    """Flow từ chối/lỗi: ghi lý do. Mốc lỗi bị loại khỏi danh sách việc tới khi `clear_errors`."""
    reason = reason.strip()
    if not reason:
        raise VidflowError("Cần ghi lý do lỗi (nguyên văn thông báo của Flow).")
    beats = require_beats(root)
    beat = beats.get(n)
    if clip:
        beat.clip.status, beat.clip.error = "error", reason
    else:
        beat.error = reason
    save_beats(root, beats)
    return beat


def clear_errors(root: Path, ns: list[int] | None = None, *, clip: bool = False) -> int:
    """Đưa mốc lỗi trở lại danh sách việc. ns rỗng/None = mọi mốc lỗi. Trả số mốc đã xóa lỗi."""
    beats = require_beats(root)
    targets = [beats.get(n) for n in ns] if ns else beats.beats
    count = 0
    for b in targets:
        if clip and b.clip.status == "error":
            b.clip.status, b.clip.error = "redo", ""
            count += 1
        elif not clip and b.error:
            b.error = ""
            count += 1
    save_beats(root, beats)
    return count
```

Thay `mark_redo`:

```python
def mark_redo(root: Path, ns: list[int], *, clip: bool = False) -> Beats:
    beats = require_beats(root)
    targets = [beats.get(n) for n in ns]  # báo lỗi trước khi ghi nếu có số sai
    for b in targets:
        if clip:
            if not b.clip.enabled:
                raise VidflowError(f"Mốc {b.n} chưa bật clip.")
            b.clip.status = "redo"
        else:
            b.status = "redo"
    save_beats(root, beats)
    return beats
```

Trong `set_image`, thay dòng `beat.image, beat.status = rel, "ok"` bằng:

```python
    beat.image, beat.status, beat.error = rel, "ok", ""
    if beat.clip.status == "ok":
        beat.clip.status = "redo"  # clip cũ dựng từ ảnh cũ
```

- [ ] **Step 4: Implement CLI** — `src/vidflow/quick/cli.py`:

Sửa `set_prompt` (thêm tham số cuối và truyền `cont`):

```python
@_cmd(quick_app, "set-prompt")
def set_prompt(project: ProjectOpt, n: Annotated[int, typer.Argument()],
               prompt: Annotated[str, typer.Option(help="Prompt đầy đủ (có câu neo)")],
               verdict: Annotated[str, typer.Option(help="pass | fail")] = "pass",
               score: Annotated[float, typer.Option(help="Điểm 0–10")] = 0,
               issue: Annotated[Optional[list[str]], typer.Option("--issue", help="Vấn đề (lặp được)")] = None,
               cont: Annotated[Optional[bool], typer.Option("--cont/--no-cont", help="Nối cảnh với mốc trước")] = None):
    """Ghi prompt + kết quả tự kiểm duyệt cho một mốc."""
    ops.set_prompt(project, n, prompt, verdict=verdict, score=score, issues=issue or [], cont=cont)
    typer.echo(f"Mốc {n}: {verdict} ({score:g}/10)")
```

Sửa `redo` thêm `--clip`:

```python
@_cmd(quick_app, "redo")
def redo(project: ProjectOpt, n: Annotated[list[int], typer.Argument(help="Các mốc cần gen lại")],
         clip: Annotated[bool, typer.Option("--clip", help="Gen lại clip thay vì ảnh")] = False):
    """Đánh dấu mốc cần gen lại ảnh (hoặc clip)."""
    ops.mark_redo(project, n, clip=clip)
    typer.echo(f"Đã đánh dấu gen lại {'clip' if clip else 'ảnh'}: {', '.join(map(str, n))}")
```

Thêm lệnh mới:

```python
ClipOpt = Annotated[bool, typer.Option("--clip", help="Áp dụng cho prompt/clip động thay vì ảnh")]


@_cmd(quick_app, "edit-prompt")
def edit_prompt(project: ProjectOpt, n: Annotated[int, typer.Argument()],
                prompt: Annotated[str, typer.Option(help="Prompt mới")], clip: ClipOpt = False):
    """Sửa tay prompt một mốc (xóa kết quả kiểm duyệt cũ)."""
    ops.edit_prompt(project, n, prompt, clip=clip)
    typer.echo(f"Mốc {n}: đã lưu prompt {'clip' if clip else 'ảnh'} — cần kiểm duyệt lại")


@_cmd(quick_app, "set-review")
def set_review(project: ProjectOpt, n: Annotated[int, typer.Argument()],
               verdict: Annotated[str, typer.Option(help="pass | fail | override")],
               score: Annotated[float, typer.Option(help="Điểm 0–10")] = 0,
               issue: Annotated[Optional[list[str]], typer.Option("--issue", help="Vấn đề/gợi ý (lặp được)")] = None,
               clip: ClipOpt = False):
    """Ghi kết quả kiểm duyệt một mốc."""
    ops.set_review(project, n, verdict, score=score, issues=issue or [], clip=clip)
    typer.echo(f"Mốc {n} ({'clip' if clip else 'ảnh'}): {verdict} ({score:g}/10)")


@_cmd(quick_app, "fail")
def fail_cmd(project: ProjectOpt, n: Annotated[int, typer.Argument()],
             reason: Annotated[str, typer.Option(help="Nguyên văn thông báo lỗi của Flow")], clip: ClipOpt = False):
    """Ghi lỗi Flow cho ảnh/clip của mốc (mốc rời danh sách việc tới khi retry)."""
    ops.record_fail(project, n, reason, clip=clip)
    typer.echo(f"Mốc {n}: ghi lỗi {'clip' if clip else 'ảnh'}")


@_cmd(quick_app, "retry")
def retry(project: ProjectOpt, n: Annotated[Optional[list[int]], typer.Argument(help="Mốc (trống = mọi mốc lỗi)")] = None,
          clip: ClipOpt = False):
    """Xóa lỗi để mốc được gen lại."""
    count = ops.clear_errors(project, n or None, clip=clip)
    typer.echo(f"Đã đưa lại {count} mốc lỗi vào danh sách gen")
```

- [ ] **Step 5: Run tests** (bỏ `skip(reason="Task 4")` trong `tests/test_quick_chars.py`)

Run: `uv run pytest tests/test_quick_prompts.py tests/test_quick_chars.py tests/test_quick_cli.py -v`
Expected: PASS (trừ test đang `skip(reason="Task 6")`).

- [ ] **Step 6: Commit**

```bash
git add src/vidflow/quick/ops.py src/vidflow/quick/cli.py tests/test_quick_prompts.py tests/test_quick_chars.py
git commit -m "feat(quick): @refs in prompts, cont, edit/review/fail/retry ops and CLI"
```

---

### Task 5: Luật được gen — `beats --todo` có `attach`/`blocked`, trạng thái tổng

**Files:**
- Modify: `src/vidflow/quick/ops.py` (`image_block`, `list_beats`, `status_summary`, `format_status`)
- Modify: `src/vidflow/quick/cli.py` (in `blocked` khi không `--json`)
- Test: `tests/test_quick_gen_rules.py`

**Interfaces:**
- Consumes: `lookup`, `CharRef` (Task 3); `Beat.refs/cont/error` (Task 1/4).
- Produces:
  - `image_block(beat: Beat, prev: Beat | None, known: dict[str, CharRef]) -> str | None`
  - `list_beats(root, *, todo=False) -> {"aspect", "beats": [row], "blocked"?: [{n, reason}]}`; mỗi row có thêm `"blocked": str | None`; khi `todo` row có `"attach": [đường dẫn tuyệt đối]` và kết quả có khóa `"blocked"`.
  - `status_summary` thêm `"blocked": int`, `"errors": int`, `"clips": {"max","enabled","ok","error"}`, `"chars_missing": [id]`.

- [ ] **Step 1: Write the failing tests** — `tests/test_quick_gen_rules.py`:

```python
import json

from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.quick import chars, ops
from vidflow.quick.model import load_beats

runner = CliRunner()
FARMER = {"id": "FARMER", "desc": "hunched farmer"}


def _prompt_all(qroot, P, texts, conts=()):
    ops.set_prompts(qroot, [{"n": i, "prompt": P(t), "verdict": "pass", "score": 8, "cont": i in conts}
                            for i, t in enumerate(texts, 1)])


def test_missing_char_image_blocks(qroot, P, img):
    chars.set_chars(qroot, [FARMER])
    _prompt_all(qroot, P, ["@FARMER a", "b", "@MODERNYOU c", "d"])
    data = ops.list_beats(qroot, todo=True)
    assert [b["n"] for b in data["beats"]] == [2, 4]
    reasons = {x["n"]: x["reason"] for x in data["blocked"]}
    assert "@FARMER" in reasons[1] and "@MODERNYOU" in reasons[3]
    sheet = chars.set_char_image(qroot, "FARMER", img())
    data = ops.list_beats(qroot, todo=True)
    row1 = next(b for b in data["beats"] if b["n"] == 1)
    assert row1["attach"] == [str(sheet.resolve())]


def test_cont_waits_for_previous_then_attaches_it(qroot, P, img):
    _prompt_all(qroot, P, ["a", "b", "c", "d"], conts=(2,))
    data = ops.list_beats(qroot, todo=True)
    assert 2 not in [b["n"] for b in data["beats"]]
    assert {"n": 2, "reason": "chờ ảnh mốc 1"} in data["blocked"]
    ops.set_image(qroot, 1, img())
    row2 = next(b for b in ops.list_beats(qroot, todo=True)["beats"] if b["n"] == 2)
    assert row2["attach"] == [str((qroot / "images" / "001_00-00.png").resolve())]


def test_cont_waits_when_previous_marked_redo(qroot, P, img):
    _prompt_all(qroot, P, ["a", "b", "c", "d"], conts=(2,))
    ops.set_image(qroot, 1, img())
    ops.mark_redo(qroot, [1])
    assert 2 not in [b["n"] for b in ops.list_beats(qroot, todo=True)["beats"]]


def test_errored_beats_leave_todo_until_retry(qroot, P):
    _prompt_all(qroot, P, ["a", "b", "c", "d"])
    ops.record_fail(qroot, 3, "Flow từ chối")
    assert 3 not in [b["n"] for b in ops.list_beats(qroot, todo=True)["beats"]]
    ops.clear_errors(qroot, [3])
    assert 3 in [b["n"] for b in ops.list_beats(qroot, todo=True)["beats"]]


def test_non_todo_rows_carry_blocked_reason(qroot, P):
    chars.set_chars(qroot, [FARMER])
    _prompt_all(qroot, P, ["@FARMER a", "b", "c", "d"])
    rows = ops.list_beats(qroot)["beats"]
    assert "@FARMER" in rows[0]["blocked"] and rows[1]["blocked"] is None
    assert "blocked" not in ops.list_beats(qroot)  # khóa tổng chỉ có khi --todo


def test_status_summary_counts(qroot, P):
    chars.set_chars(qroot, [FARMER])
    _prompt_all(qroot, P, ["@FARMER a", "b", "c", "d"])
    ops.record_fail(qroot, 2, "x")
    s = ops.status_summary(qroot)
    assert s["blocked"] == 1 and s["errors"] == 1
    assert s["chars_missing"] == ["FARMER"]
    assert s["clips"] == {"max": 12, "enabled": 0, "ok": 0, "error": 0}
    assert "Bị chặn: 1" in ops.format_status(s)


def test_cli_beats_todo_json_has_blocked(qroot, P):
    chars.set_chars(qroot, [FARMER])
    _prompt_all(qroot, P, ["@FARMER a", "b", "c", "d"])
    r = runner.invoke(app, ["quick", "beats", "-p", str(qroot), "--json", "--todo"])
    data = json.loads(r.output)
    assert data["blocked"][0]["n"] == 1 and [b["n"] for b in data["beats"]] == [2, 3, 4]
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_quick_gen_rules.py -v`
Expected: FAIL — `KeyError: 'blocked'`.

- [ ] **Step 3: Implement trong `src/vidflow/quick/ops.py`**

Thêm `CharRef` vào import từ `vidflow.quick.chars`. Thay `list_beats`:

```python
def image_block(beat: Beat, prev: Beat | None, known: dict[str, CharRef]) -> str | None:
    """Lý do mốc chưa gen ảnh được (None = được): thiếu ảnh nhân vật, hoặc nối cảnh mà mốc trước chưa có ảnh."""
    missing = [r for r in beat.refs if r not in known or known[r].image is None]
    if missing:
        return "thiếu ảnh " + ", ".join("@" + r for r in missing)
    if beat.cont and not (prev and prev.image and prev.status == "ok"):
        return f"chờ ảnh mốc {prev.n if prev else beat.n - 1}"
    return None


def _wants_image(b: Beat) -> bool:
    return (b.status in ("pending", "redo") and bool(b.prompt) and b.review is not None
            and b.review.verdict in PASSING and b.start is not None and not b.error)


def list_beats(root: Path, *, todo: bool = False) -> dict:
    """todo=True: chỉ mốc cần gen ảnh và gen được ngay; mốc bị chặn vào `blocked`; kèm `attach` (ảnh đính khi gen)."""
    root = Path(root)
    beats = require_beats(root)
    known = lookup(root)
    rows, blocked = [], []
    prev: Beat | None = None
    for b in beats.beats:
        reason = None if b.status == "ok" else image_block(b, prev, known)
        before, prev = prev, b
        if todo:
            if not _wants_image(b):
                continue
            if reason:
                blocked.append({"n": b.n, "reason": reason})
                continue
        row = {**b.model_dump(), "file": beat_file(b), "blocked": reason}
        if todo:
            row["attach"] = ([str(known[r].image.resolve()) for r in b.refs]
                             + ([str((root / before.image).resolve())] if b.cont else []))
        rows.append(row)
    out = {"aspect": beats.aspect, "beats": rows}
    if todo:
        out["blocked"] = blocked
    return out
```

Trong `status_summary`, sau dòng `bl = beats.beats if beats else []` thêm:

```python
    known = lookup(root, q) if bl else {}
    blocked, prev = 0, None
    for b in bl:
        if _wants_image(b) and image_block(b, prev, known):
            blocked += 1
        prev = b
    referenced = {r for b in bl for r in b.refs}
    chars_missing = sorted(r for r in referenced if r in known and known[r].image is None)
```

và thêm vào dict trả về (cùng cấp `"voice_s"`):

```python
        "blocked": blocked,
        "errors": sum(1 for b in bl if b.error),
        "chars_missing": chars_missing,
        "clips": {"max": q.max_clips, "enabled": sum(1 for b in bl if b.clip.enabled),
                  "ok": sum(1 for b in bl if b.clip.status == "ok"),
                  "error": sum(1 for b in bl if b.clip.status == "error")},
```

Trong `format_status`, trước `if s["voice_s"] is not None:` thêm:

```python
    if s["blocked"] or s["errors"]:
        miss = f" · thiếu ảnh nhân vật: {', '.join('@' + c for c in s['chars_missing'])}" if s["chars_missing"] else ""
        lines.append(f"Bị chặn: {s['blocked']} mốc · lỗi Flow: {s['errors']} mốc{miss}")
    c = s["clips"]
    if c["enabled"]:
        lines.append(f"Clip: {c['ok']}/{c['enabled']} xong (tối đa {c['max']}) · lỗi {c['error']}")
```

- [ ] **Step 4: CLI** — trong lệnh `beats` của `cli.py`, sau vòng `for b in data["beats"]` (nhánh không JSON) thêm:

```python
    for x in data.get("blocked", []):
        typer.echo(f"{x['n']:03d} BỊ CHẶN: {x['reason']}")
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_quick_gen_rules.py tests/test_quick_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/vidflow/quick/ops.py src/vidflow/quick/cli.py tests/test_quick_gen_rules.py
git commit -m "feat(quick): gen rules — blocked/attach in todo, status counts"
```

---

### Task 6: Cài đặt Flow và clip động (`quick/clips.py`)

**Files:**
- Create: `src/vidflow/quick/clips.py`
- Modify: `src/vidflow/quick/ops.py` (`update_settings`)
- Modify: `src/vidflow/quick/cli.py` (`settings`, `clip`, `set-clip-prompts`, `set-clip`, `beats --todo-clips`)
- Test: `tests/test_quick_clips.py`; bỏ các `skip(reason="Task 6")`

**Interfaces:**
- Consumes: `VIDEO_EXTS`, `Clip`, `image_name` (Task 1); `lookup`, `parse_refs`, `check_known` (Task 3); `PASSING` (ops).
- Produces:
  - `ops.update_settings(root, *, image_model=None, video_model=None, resolution=None, max_clips=None, allow_cont=None, channel_chars=None) -> QuickProject`
  - `clips.set_clip_enabled(root, ns: list[int], on: bool) -> Beats`
  - `clips.set_clip_prompts(root, items: list[dict]) -> Beats`
  - `clips.set_clip(root, n, src) -> Beat`
  - `clips.clip_todo(root) -> {"aspect","video_model","resolution","clips":[{n,duration,image,prompt,file}]}`

- [ ] **Step 1: Write the failing tests** — `tests/test_quick_clips.py`:

```python
import json

import pytest
from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.errors import VidflowError
from vidflow.quick import clips, ops
from vidflow.quick.model import load_beats, load_quick

runner = CliRunner()
CP = "doodle motion of @MODERNYOU stretching. Sound: a yawn."


def _ready(qroot, P, img, n=1):
    ops.set_prompts(qroot, [{"n": n, "prompt": P("a"), "verdict": "pass", "score": 8}])
    ops.set_image(qroot, n, img())


def test_settings(qroot):
    q = ops.update_settings(qroot, video_model="Veo 3.1 Lite", resolution="1080p", max_clips=3, allow_cont=False)
    assert q.flow.video_model == "Veo 3.1 Lite" and q.flow.resolution == "1080p"
    assert q.max_clips == 3 and q.allow_cont is False
    with pytest.raises(VidflowError):
        ops.update_settings(qroot, resolution="4k")
    with pytest.raises(VidflowError, match="@NOBODY"):
        ops.update_settings(qroot, channel_chars=["NOBODY"])


def test_max_clips_enforced_and_cannot_drop_below_enabled(qroot):
    ops.update_settings(qroot, max_clips=2)
    clips.set_clip_enabled(qroot, [1, 2], True)
    with pytest.raises(VidflowError, match="Tối đa 2"):
        clips.set_clip_enabled(qroot, [3], True)
    clips.set_clip_enabled(qroot, [1], True)  # đã bật thì không tính thêm
    with pytest.raises(VidflowError, match="Đang bật 2"):
        ops.update_settings(qroot, max_clips=1)
    clips.set_clip_enabled(qroot, [2], False)
    assert [b.clip.enabled for b in load_beats(qroot).beats] == [True, False, False, False]


def test_set_clip_prompts_enables_and_validates(qroot):
    ops.update_settings(qroot, max_clips=1)
    clips.set_clip_prompts(qroot, [{"n": 2, "prompt": CP, "verdict": "pass", "score": 8}])
    c = load_beats(qroot).beats[1].clip
    assert c.enabled and c.prompt == CP and c.review.verdict == "pass"
    with pytest.raises(VidflowError, match="Tối đa 1"):
        clips.set_clip_prompts(qroot, [{"n": 3, "prompt": CP, "verdict": "pass", "score": 8}])
    with pytest.raises(VidflowError, match="@GHOST"):
        clips.set_clip_prompts(qroot, [{"n": 2, "prompt": "@GHOST moves", "verdict": "pass", "score": 8}])


def test_clip_todo_requires_image_review_and_model(qroot, P, img):
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP, "verdict": "pass", "score": 8},
                                   {"n": 2, "prompt": CP, "verdict": "fail", "score": 4}])
    assert clips.clip_todo(qroot)["clips"] == []  # mốc 1 chưa có ảnh, mốc 2 trượt
    _ready(qroot, P, img, 1)
    with pytest.raises(VidflowError, match="model clip"):
        clips.clip_todo(qroot)
    ops.update_settings(qroot, video_model="Veo 3.1 Lite")
    data = clips.clip_todo(qroot)
    assert data["video_model"] == "Veo 3.1 Lite" and data["resolution"] == "720p"
    row = data["clips"][0]
    assert row["n"] == 1 and row["duration"] == 4.0 and row["file"] == "clips/001_00-00.mp4"
    assert row["image"] == str((qroot / "images" / "001_00-00.png").resolve())


def test_set_clip_and_image_regen_marks_clip_redo(qroot, P, img):
    _ready(qroot, P, img, 1)
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP, "verdict": "pass", "score": 8}])
    b = clips.set_clip(qroot, 1, img("v.MP4", b"mp4"))
    assert b.clip.file == "clips/001_00-00.mp4" and b.clip.status == "ok"
    assert (qroot / "clips" / "001_00-00.mp4").read_bytes() == b"mp4"
    ops.set_image(qroot, 1, img("new.png"))
    assert load_beats(qroot).beats[0].clip.status == "redo"
    with pytest.raises(VidflowError, match="chưa bật clip"):
        clips.set_clip(qroot, 2, img("v.mp4", b"x"))
    with pytest.raises(VidflowError, match="không hỗ trợ"):
        clips.set_clip(qroot, 1, img("v.avi", b"x"))


def test_errored_clip_leaves_todo_until_retry(qroot, P, img):
    ops.update_settings(qroot, video_model="Veo 3.1 Lite")
    _ready(qroot, P, img, 1)
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP, "verdict": "pass", "score": 8}])
    ops.record_fail(qroot, 1, "Veo từ chối", clip=True)
    assert clips.clip_todo(qroot)["clips"] == []
    ops.clear_errors(qroot, [1], clip=True)
    assert [c["n"] for c in clips.clip_todo(qroot)["clips"]] == [1]


def test_cli_clip_commands(qroot, P, img, tmp_path):
    r = runner.invoke(app, ["quick", "settings", "-p", str(qroot), "--video-model", "Veo 3.1 Lite", "--max-clips", "5"])
    assert r.exit_code == 0, r.output
    assert load_quick(qroot).max_clips == 5
    r = runner.invoke(app, ["quick", "clip", "-p", str(qroot), "on", "2", "3"])
    assert r.exit_code == 0, r.output
    f = tmp_path / "cp.json"
    f.write_text(json.dumps([{"n": 1, "prompt": CP, "verdict": "pass", "score": 8}]), encoding="utf-8")
    assert runner.invoke(app, ["quick", "set-clip-prompts", "-p", str(qroot), "--json", str(f)]).exit_code == 0
    _ready(qroot, P, img, 1)
    r = runner.invoke(app, ["quick", "beats", "-p", str(qroot), "--json", "--todo-clips"])
    assert json.loads(r.output)["clips"][0]["n"] == 1
    r = runner.invoke(app, ["quick", "set-clip", "-p", str(qroot), "1", str(img("v.mp4", b"x"))])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["quick", "clip", "-p", str(qroot), "maybe", "1"])
    assert r.exit_code == 1 and "Traceback" not in r.output
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_quick_clips.py -v`
Expected: FAIL — `ImportError: cannot import name 'clips'`.

- [ ] **Step 3: Implement `ops.update_settings`** — thêm vào `src/vidflow/quick/ops.py`:

```python
def update_settings(root: Path, *, image_model: str | None = None, video_model: str | None = None,
                    resolution: str | None = None, max_clips: int | None = None, allow_cont: bool | None = None,
                    channel_chars: list[str] | None = None) -> QuickProject:
    """Cài đặt Flow + giới hạn clip + nối cảnh + nhân vật bộ kênh dùng trong video."""
    q = load_quick(root)
    if max_clips is not None:
        if max_clips < 0:
            raise VidflowError("max_clips phải ≥ 0.")
        beats = load_beats(root)
        on = sum(1 for b in beats.beats if b.clip.enabled) if beats else 0
        if max_clips < on:
            raise VidflowError(f"Đang bật {on} clip — tắt bớt trước khi giảm tối đa xuống {max_clips}.")
        q.max_clips = max_clips
    if resolution is not None:
        if resolution not in ("720p", "1080p"):
            raise VidflowError("Độ phân giải chỉ 720p hoặc 1080p.")
        q.flow.resolution = resolution
    if video_model is not None:
        q.flow.video_model = video_model.strip()
    if image_model is not None:
        q.flow.image_model = image_model.strip()
    if allow_cont is not None:
        q.allow_cont = allow_cont
    if channel_chars is not None:
        have = {c.id for c in load_preset(q.preset).characters}
        unknown = [c for c in channel_chars if c not in have]
        if unknown:
            raise VidflowError(f"Bộ kênh không có: {', '.join('@' + u for u in unknown)}")
        q.channel_chars = list(channel_chars)
    save_quick(root, q)
    return q
```

- [ ] **Step 4: Implement `src/vidflow/quick/clips.py`**

```python
"""Clip động (Veo trong Google Flow) cho các mốc được chọn — spec 2026-10-12."""
from __future__ import annotations

import shutil
from pathlib import Path

from vidflow.errors import VidflowError
from vidflow.quick.chars import check_known, lookup, parse_refs
from vidflow.quick.model import VIDEO_EXTS, Beat, Beats, Review, image_name, load_quick, require_beats, save_beats
from vidflow.quick.ops import PASSING


def _enabled(beats: Beats) -> int:
    return sum(1 for b in beats.beats if b.clip.enabled)


def _check_limit(beats: Beats, new: int, max_clips: int) -> None:
    cur = _enabled(beats)
    if cur + new > max_clips:
        raise VidflowError(f"Tối đa {max_clips} clip (đang bật {cur}) — tăng bằng "
                           "`vidflow quick settings --max-clips <n>`.")


def set_clip_enabled(root: Path, ns: list[int], on: bool) -> Beats:
    q = load_quick(root)
    beats = require_beats(root)
    targets = [beats.get(n) for n in ns]
    if on:
        _check_limit(beats, len({b.n for b in targets if not b.clip.enabled}), q.max_clips)
    for b in targets:
        b.clip.enabled = on
    save_beats(root, beats)
    return beats


def set_clip_prompts(root: Path, items: list[dict]) -> Beats:
    """items: [{n, prompt, verdict, score, issues?}] — ghi prompt clip + tự kiểm duyệt, bật clip cho mốc."""
    q = load_quick(root)
    beats = require_beats(root)
    known = lookup(root, q)
    staged = []
    for it in items:
        b = beats.get(int(it["n"]))
        prompt = str(it.get("prompt", "")).strip()
        if not prompt:
            raise VidflowError(f"Mốc {b.n}: prompt clip rỗng.")
        check_known(parse_refs(prompt), known)
        verdict = it.get("verdict", "pass")
        if verdict not in ("pass", "fail"):
            raise VidflowError("verdict phải là pass hoặc fail")
        staged.append((b, prompt, Review(verdict=verdict, score=float(it.get("score", 0)),
                                         issues=list(it.get("issues") or []))))
    _check_limit(beats, len({b.n for b, _, _ in staged if not b.clip.enabled}), q.max_clips)
    for b, prompt, review in staged:
        b.clip.prompt, b.clip.review, b.clip.enabled = prompt, review, True
    save_beats(root, beats)
    return beats


def set_clip(root: Path, n: int, src: Path) -> Beat:
    """Nhập clip đã gen → clips/NNN_MM-SS.<ext>."""
    root, src = Path(root), Path(src)
    if not src.is_file():
        raise VidflowError(f"Không thấy file clip {src}")
    ext = VIDEO_EXTS.get(src.suffix.lower())
    if not ext:
        raise VidflowError(f"Định dạng clip không hỗ trợ: {src.suffix} (dùng mp4/mov/webm)")
    beats = require_beats(root)
    b = beats.get(n)
    if b.start is None:
        raise VidflowError("Mốc chưa có thời gian — chạy `vidflow quick voice` trước.")
    if not b.clip.enabled:
        raise VidflowError(f"Mốc {n} chưa bật clip.")
    rel = f"clips/{image_name(n, b.start)}{ext}"
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    if b.clip.file and b.clip.file != rel:
        (root / b.clip.file).unlink(missing_ok=True)
    b.clip.file, b.clip.status, b.clip.error = rel, "ok", ""
    save_beats(root, beats)
    return b


def clip_todo(root: Path) -> dict:
    """Clip cần gen: đã bật, prompt đạt, ảnh mốc ok, status pending/redo (lỗi phải `retry --clip`)."""
    root = Path(root)
    q = load_quick(root)
    beats = require_beats(root)
    rows = []
    for b in beats.beats:
        c = b.clip
        if not (c.enabled and c.status in ("pending", "redo") and c.prompt and c.review
                and c.review.verdict in PASSING and b.image and b.status == "ok"
                and b.start is not None and b.end is not None):
            continue
        rows.append({"n": b.n, "duration": round(b.end - b.start, 3), "image": str((root / b.image).resolve()),
                     "prompt": c.prompt, "file": f"clips/{image_name(b.n, b.start)}.mp4"})
    if rows and not q.flow.video_model:
        raise VidflowError("Chưa chọn model clip — `vidflow quick settings -p <project> --video-model \"Veo 3.1 Lite\"`.")
    return {"aspect": beats.aspect, "video_model": q.flow.video_model, "resolution": q.flow.resolution, "clips": rows}
```

- [ ] **Step 5: CLI** — `src/vidflow/quick/cli.py`: import `from vidflow.quick import chars, clips, jobs, ops`. Thêm lệnh:

```python
@_cmd(quick_app, "settings")
def settings(project: ProjectOpt,
             image_model: Annotated[Optional[str], typer.Option(help="Model ảnh Flow")] = None,
             video_model: Annotated[Optional[str], typer.Option(help="Model clip Flow, ví dụ \"Veo 3.1 Lite\"")] = None,
             resolution: Annotated[Optional[str], typer.Option(help="720p | 1080p")] = None,
             max_clips: Annotated[Optional[int], typer.Option(help="Số clip tối đa (0 = chỉ ảnh)")] = None,
             allow_cont: Annotated[Optional[bool], typer.Option("--allow-cont/--no-allow-cont")] = None,
             channel_char: Annotated[Optional[list[str]], typer.Option("--channel-char", help="Nhân vật bộ kênh dùng (lặp được)")] = None):
    """Cài đặt Flow, giới hạn clip, nối cảnh, nhân vật bộ kênh."""
    q = ops.update_settings(project, image_model=image_model, video_model=video_model, resolution=resolution,
                            max_clips=max_clips, allow_cont=allow_cont, channel_chars=channel_char)
    typer.echo(f"Ảnh: {q.flow.image_model} · clip: {q.flow.video_model or '(chưa chọn)'} {q.flow.resolution} · "
               f"tối đa {q.max_clips} clip · nối cảnh: {'bật' if q.allow_cont else 'tắt'}")


@_cmd(quick_app, "clip")
def clip_toggle(project: ProjectOpt, action: Annotated[str, typer.Argument(help="on | off")],
                n: Annotated[list[int], typer.Argument(help="Các mốc")]):
    """Bật/tắt clip động cho mốc."""
    if action not in ("on", "off"):
        raise VidflowError("Dùng `clip on <n...>` hoặc `clip off <n...>`.")
    clips.set_clip_enabled(project, n, action == "on")
    typer.echo(f"Clip {action}: {', '.join(map(str, n))}")


@_cmd(quick_app, "set-clip-prompts")
def set_clip_prompts(project: ProjectOpt, json_file: JsonFile):
    """Ghi prompt clip [{n, prompt, verdict, score, issues}] và bật clip các mốc đó."""
    items = _read_json(json_file)
    clips.set_clip_prompts(project, items)
    typer.echo(f"Đã ghi {len(items)} prompt clip")


@_cmd(quick_app, "set-clip")
def set_clip(project: ProjectOpt, n: Annotated[int, typer.Argument()], file: Annotated[Path, typer.Argument()]):
    """Nhập clip đã gen → clips/NNN_MM-SS.<ext>."""
    b = clips.set_clip(project, n, file)
    typer.echo(f"Mốc {n} → {b.clip.file}")
```

Sửa lệnh `beats` thêm `--todo-clips` (đặt nhánh này đầu hàm):

```python
@_cmd(quick_app, "beats")
def beats(project: ProjectOpt, json_out: Annotated[bool, typer.Option("--json")] = False,
          todo: Annotated[bool, typer.Option("--todo", help="Chỉ mốc cần gen ảnh")] = False,
          todo_clips: Annotated[bool, typer.Option("--todo-clips", help="Chỉ clip cần gen")] = False):
    """Liệt kê mốc (agent dùng --json)."""
    if todo_clips:
        data = clips.clip_todo(project)
        if json_out:
            typer.echo(json.dumps(data, ensure_ascii=False, indent=1))
        else:
            for c in data["clips"]:
                typer.echo(f"{c['n']:03d} {c['duration']:.1f}s {c['prompt'][:60]}")
        return
    data = ops.list_beats(project, todo=todo)
    if json_out:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=1))
        return
    for b in data["beats"]:
        t = "--:--" if b["start"] is None else f"{int(b['start'] // 60):02d}:{int(b['start'] % 60):02d}"
        v = b["review"]["verdict"] if b["review"] else "-"
        typer.echo(f"{b['n']:03d} [{t}] {b['status']:<7} {v:<5} {b['text'][:60]}")
    for x in data.get("blocked", []):
        typer.echo(f"{x['n']:03d} BỊ CHẶN: {x['reason']}")
```

- [ ] **Step 6: Run tests** (bỏ mọi `skip(reason="Task 6")` ở `tests/test_quick_chars.py`, `tests/test_quick_prompts.py`)

Run: `uv run pytest tests/test_quick_clips.py tests/test_quick_chars.py tests/test_quick_prompts.py tests/test_quick_gen_rules.py tests/test_quick_cli.py -v`
Expected: PASS, không còn test skip.

- [ ] **Step 7: Commit**

```bash
git add src/vidflow/quick/clips.py src/vidflow/quick/ops.py src/vidflow/quick/cli.py tests/
git commit -m "feat(quick): flow settings and motion clips (limit, prompts, import, todo)"
```

---

### Task 7: Job Claude (`sheets`, `clips`, kiểm duyệt một mốc) + hướng dẫn agent

**Files:**
- Modify: `src/vidflow/quick/jobs.py`
- Modify: `src/vidflow/quick/cli.py` (lệnh `sheets`, `clips`, `review`; `_claude` kiểm tra điều kiện)
- Modify: `.claude/agents/quick-writer.md`
- Test: `tests/test_quick_jobs.py`, `tests/test_quick_cli.py`

**Interfaces:**
- Consumes: lệnh CLI của Task 3–6 (tên phải khớp: `chars`, `set-chars`, `char-image`, `set-prompts` với `cont`, `set-clip-prompts`, `beats --todo`/`--todo-clips`, `set-image`, `set-clip`, `fail`, `set-review`).
- Produces: `QUICK_KINDS = ("ideas", "script", "prompts", "sheets", "flow", "clips")`, `CHROME_KINDS = ("sheets", "flow", "clips")`, `review_task(project_root, preset, n, *, clip=False) -> str`, `review_cmd(project_root, preset, n, *, clip=False) -> list[str]` (Giai đoạn 3 dùng cho nút "Lưu & kiểm duyệt").

- [ ] **Step 1: Write the failing tests** — sửa/thêm trong `tests/test_quick_jobs.py`:

```python
from vidflow.quick.jobs import CHROME_KINDS, QUICK_KINDS, claude_cmd, claude_task, review_cmd, review_task


def test_chrome_only_for_flow_kinds(preset):
    assert CHROME_KINDS == ("sheets", "flow", "clips")
    for kind in QUICK_KINDS:
        cmd = claude_cmd(kind, ROOT, preset)
        assert cmd[:4] == ["claude", "-p", "--permission-mode", "bypassPermissions"]
        assert ("--chrome" in cmd) == (kind in CHROME_KINDS)
        assert cmd[-1] == claude_task(kind, ROOT, preset)


def test_script_task_proposes_characters(preset):
    t = claude_task("script", ROOT, preset)
    assert "quick set-chars" in t and "quick chars" in t


def test_prompts_task_mentions_refs_cont_and_clips(preset):
    t = claude_task("prompts", ROOT, preset)
    assert "@TÊN" in t and "cont" in t
    assert "quick set-clip-prompts" in t and "max_clips" in t


def test_flow_task_uses_attach(preset):
    t = claude_task("flow", ROOT, preset)
    assert "attach" in t and "blocked" in t and "quick fail" in t


def test_sheets_task(preset):
    t = claude_task("sheets", ROOT, preset)
    assert "quick chars" in t and "quick char-image" in t and "--channel" in t
    assert "flow-operator.md" in t


def test_clips_task(preset):
    t = claude_task("clips", ROOT, preset)
    assert "--todo-clips" in t and "quick set-clip" in t and "quick fail" in t and "--clip" in t


def test_review_task_and_cmd(preset):
    t = review_task(ROOT, preset, 7)
    assert "mốc 7" in t and "quick set-review" in t and "--clip" not in t
    assert "--clip" in review_task(ROOT, preset, 7, clip=True)
    cmd = review_cmd(ROOT, preset, 7)
    assert "--chrome" not in cmd and cmd[-1] == t
```

Xóa test cũ `test_chrome_only_for_flow` (thay bằng `test_chrome_only_for_flow_kinds`). Trong `tests/test_quick_cli.py`, sửa `test_llm_commands_call_run_claude`: vòng `for kind in ("prompts", "flow")` thành `for kind in ("prompts", "sheets", "flow", "clips")` và assert cuối thành `["ideas", "script", "prompts", "sheets", "flow", "clips"]`.

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_quick_jobs.py -v`
Expected: FAIL — `ImportError: cannot import name 'CHROME_KINDS'`.

- [ ] **Step 3: Implement `src/vidflow/quick/jobs.py`**

Thay hằng và tách phần chung:

```python
QUICK_KINDS = ("ideas", "script", "prompts", "sheets", "flow", "clips")
CHROME_KINDS = ("sheets", "flow", "clips")
BATCH = 20
LABELS = {
    "ideas": "Claude đề xuất 5 ý tưởng",
    "script": "Claude viết kịch bản + tách mốc + đề xuất nhân vật",
    "prompts": "Claude viết prompt ảnh + clip từng mốc",
    "sheets": "Gen character sheet trong Google Flow",
    "flow": "Gen ảnh mốc trong Google Flow",
    "clips": "Gen clip động trong Google Flow",
}
CLI = "uv run vidflow quick"


def _common(root: Path, preset: Preset) -> str:
    brief = brief_path(preset)
    return (f"Thư mục làm việc: {REPO}. Project nhanh: {root} (quick.yaml, beats.json). "
            f"Bộ kênh: {preset.id} — brief gốc: {brief} (đọc TOÀN BỘ, tuân thủ nội dung/giọng/phong cách; "
            "BỎ QUA các chỉ dẫn tương tác trong brief như chờ người dùng trả lời, xuất code block, tạo file tải về). "
            f"Xem trạng thái: `{CLI} status -p {root}`. KHÔNG sửa tay quick.yaml, beats.json — mọi ghi đều qua CLI "
            f"`{CLI} ...`; file JSON tạm đặt trong {root}/tmp/. Người dùng chỉ dùng tín dụng gói Google Flow: KHÔNG chạy "
            "`vidflow gen`, `vidflow estimate`, `vidflow refimg`. Báo cáo bằng tiếng Việt, ngắn gọn.")
```

Trong `claude_task`: thay `cli = f"uv run vidflow quick"` bằng `cli = CLI`, thay khối `common = (...)` bằng `common = _common(root, preset)`, rồi:

Nhánh `script` — nối thêm vào cuối chuỗi trả về:

```python
                " Sau đó đề xuất nhân vật RIÊNG của video (ngoài nhân vật bộ kênh: "
                f"`{cli} chars -p {root} --json`) theo mục 'Nhân vật' trong quick-writer.md; ghi file JSON "
                f"`[{{\"id\", \"name\", \"desc\", \"color\"}}]` rồi chạy `{cli} set-chars -p {root} --json <file>` "
                "(không có nhân vật riêng thì ghi mảng rỗng).")
```

Nhánh `prompts` — thay toàn bộ bằng:

```python
    if kind == "prompts":
        return (f"Bạn là quick-writer (bước prompt ảnh + clip). Đọc và tuân thủ {writer}. {common} "
                f"Lấy mốc bằng `{cli} beats -p {root} --json`, nhân vật bằng `{cli} chars -p {root} --json`, "
                f"cài đặt (max_clips, allow_cont) bằng `{cli} status -p {root} --json`. Viết image prompt cho mọi mốc "
                "chưa có prompt đạt (review trống hoặc fail) theo Giai đoạn 3 của brief: mỗi prompt = câu neo đầu NGUYÊN VĂN "
                f"«{preset.style_anchor_start}» + mô tả cảnh bằng tiếng Anh + câu neo cuối NGUYÊN VĂN "
                f"«{preset.style_anchor_end}». Không thêm mốc [MM:SS] vào prompt. Mọi nhân vật đã khai báo phải nhắc "
                "bằng @TÊN (IN HOA, đúng id). Mốc tiếp nối cùng khoảnh khắc với mốc liền trước: thêm \"cont\": true "
                "(chỉ khi allow_cont). Sau mỗi prompt tự kiểm duyệt theo bảng kiểm trong quick-writer.md; trượt thì viết lại, "
                "tối đa 2 lần; ghi verdict/score/issues của lần cuối. "
                f"Làm theo lô {BATCH} mốc: mỗi lô ghi file JSON `[{{\"n\", \"prompt\", \"verdict\", \"score\", \"issues\", \"cont\"}}]` "
                f"rồi chạy `{cli} set-prompts -p {root} --json <file>`. Lặp tới hết mốc. "
                "Cuối cùng chọn tối đa max_clips mốc có hành động rõ nhất để làm clip động (bỏ qua nếu max_clips = 0 "
                "hoặc đã đủ clip bật), viết prompt clip theo mục 'Clip động' trong quick-writer.md, tự kiểm duyệt, "
                f"ghi `[{{\"n\", \"prompt\", \"verdict\", \"score\", \"issues\"}}]` bằng `{cli} set-clip-prompts -p {root} --json <file>`.")
```

Nhánh `flow` — thay toàn bộ bằng:

```python
    if kind == "flow":
        return (f"Bạn là flow-operator. Đọc và tuân thủ {AGENTS / 'flow-operator.md'} (kiến thức giao diện Flow, tải file, "
                f"điều kiện dừng) và phần 'Gen ảnh mốc' trong {writer}. {common} "
                f"Lấy việc bằng `{cli} beats -p {root} --json --todo` (mốc gen được ngay; trường `file` là tên đích "
                "NNN_MM-SS; `attach` là các ảnh phải đính kèm theo đúng thứ tự trước khi dán prompt; `blocked` là mốc "
                f"chưa gen được — KHÔNG gen, chỉ báo). Gen ẢNH (không phải video) trong Google Flow, tỉ lệ {preset.aspect}, "
                f"x1 mỗi mốc, prompt nguyên văn `prompt`, theo lô {BATCH} mốc. Tải từng ảnh (1K/2K) về rồi chạy ngay "
                f"`{cli} set-image -p {root} <n> \"<file tải về>\"` — lệnh tự lưu thành images/NNN_MM-SS.jpg và cập nhật "
                f"beats.json. Flow từ chối prompt → `{cli} fail -p {root} <n> --reason \"<nguyên văn>\"` rồi sang mốc sau. "
                f"Hết lô thì chạy lại `{cli} beats -p {root} --json --todo` và làm lô tiếp cho tới khi `beats` rỗng. "
                "Báo cáo: số ảnh đã gen, mốc lỗi kèm lý do, mốc bị chặn kèm lý do, tín dụng còn lại.")
```

Thêm hai nhánh mới trước `raise ValueError`:

```python
    if kind == "sheets":
        return (f"Bạn là flow-operator. Đọc và tuân thủ {AGENTS / 'flow-operator.md'} và mục 'Gen character sheet' "
                f"trong {writer}. {common} Lấy nhân vật bằng `{cli} chars -p {root} --json`; với mỗi nhân vật có "
                "`image` null và `uses` > 0: gen MỘT ảnh character sheet trong Flow (tỉ lệ 16:9, x1) theo mẫu prompt "
                f"trong mục đó, tải về rồi chạy `{cli} char-image -p {root} <ID> \"<file>\"` (thêm `--channel` khi "
                "`scope` là channel). Báo cáo: nhân vật đã gen, nhân vật lỗi kèm lý do, tín dụng còn lại.")
    if kind == "clips":
        return (f"Bạn là flow-operator. Đọc và tuân thủ {AGENTS / 'flow-operator.md'} và mục 'Gen clip động' trong "
                f"{writer}. {common} Lấy việc bằng `{cli} beats -p {root} --json --todo-clips` (model, độ phân giải, "
                "và từng clip: ảnh nguồn `image`, `prompt`, `duration`). Mỗi clip: tạo VIDEO từ ảnh trong Flow, đính `image` "
                "làm khung đầu, chọn đúng `video_model`, thời lượng ngắn nhất ≥ `duration`, dán `prompt` nguyên văn, "
                f"tải bản `resolution` về rồi chạy `{cli} set-clip -p {root} <n> \"<file>\"`. Từ chối/lỗi → "
                f"`{cli} fail -p {root} <n> --clip --reason \"<nguyên văn>\"`. Tuần tự từng clip. "
                "Báo cáo: số clip đã gen, clip lỗi kèm lý do, tín dụng còn lại.")
```

Sửa `claude_cmd`:

```python
def claude_cmd(kind: str, project_root: Path, preset: Preset) -> list[str]:
    cmd = ["claude", "-p", "--permission-mode", "bypassPermissions"]
    if kind in CHROME_KINDS:
        cmd.append("--chrome")
    return cmd + [claude_task(kind, project_root, preset)]
```

Thêm cuối file:

```python
def review_task(project_root: Path, preset: Preset, n: int, *, clip: bool = False) -> str:
    """Kiểm duyệt ĐỘC LẬP một mốc (nút "Lưu & kiểm duyệt" trên UI). Không dùng Chrome nên chạy song song job Flow."""
    root = project_root
    what = "clip" if clip else "ảnh"
    flag = " --clip" if clip else ""
    return (f"Bạn đóng vai prompt-reviewer ĐỘC LẬP (không phải người viết prompt). {_common(root, preset)} "
            f"Dùng bảng kiểm {'mục Clip động' if clip else 'mục Image prompt'} trong {AGENTS / 'quick-writer.md'}. "
            f"Kiểm duyệt prompt {what} của mốc {n}: lấy bằng `{CLI} beats -p {root} --json` (đọc cả mốc {n - 1} và "
            f"{n + 1} để xét nhất quán), nhân vật bằng `{CLI} chars -p {root} --json`. KHÔNG sửa prompt. Ghi kết quả: "
            f"`{CLI} set-review -p {root} {n}{flag} --verdict pass|fail --score <0-10> --issue \"<lỗi + gợi ý sửa>\"` "
            "(lặp --issue cho từng ý, tiếng Việt). In một dòng tóm tắt.")


def review_cmd(project_root: Path, preset: Preset, n: int, *, clip: bool = False) -> list[str]:
    return ["claude", "-p", "--permission-mode", "bypassPermissions", review_task(project_root, preset, n, clip=clip)]
```

- [ ] **Step 4: CLI** — `src/vidflow/quick/cli.py`: trong `_claude` đổi `if kind in ("prompts", "flow"):` thành `if kind in ("prompts", "flow", "clips"):`; thêm lệnh:

```python
@_cmd(quick_app, "sheets")
def sheets(project: ProjectOpt, print_only: PrintOpt = False):
    """Gen character sheet còn thiếu trong Google Flow (claude --chrome)."""
    _claude("sheets", project, print_only)


@_cmd(quick_app, "clips")
def clips_flow(project: ProjectOpt, print_only: PrintOpt = False):
    """Gen clip động trong Google Flow (claude --chrome)."""
    _claude("clips", project, print_only)


@_cmd(quick_app, "review")
def review(project: ProjectOpt, n: Annotated[int, typer.Argument()], clip: ClipOpt = False,
           print_only: PrintOpt = False):
    """Kiểm duyệt độc lập prompt ảnh/clip của một mốc."""
    import subprocess

    from vidflow.quick.preset import REPO

    preset = load_preset(load_quick(project).preset)
    if print_only:
        typer.echo(jobs.review_task(project, preset, n, clip=clip))
        return
    rc = subprocess.run(jobs.review_cmd(project, preset, n, clip=clip), cwd=REPO, stdin=subprocess.DEVNULL).returncode
    if rc:
        raise VidflowError(f"Kiểm duyệt mốc {n} lỗi (mã {rc}).")
```

(`ClipOpt` đã định nghĩa ở Task 4 — đặt định nghĩa đó phía trên mọi lệnh dùng nó.)

- [ ] **Step 5: Cập nhật `.claude/agents/quick-writer.md`**

Sửa dòng `description:` ở frontmatter thành:

```
description: Quy trình nhanh — đề xuất 5 ý tưởng, viết kịch bản lời dẫn và tách mốc, đề xuất nhân vật @TÊN, viết + tự kiểm duyệt image prompt (có nối cảnh) và prompt clip động theo brief của bộ kênh (presets/<id>.yaml). Ghi mọi kết quả qua `vidflow quick set-*`. Kèm hướng dẫn gen sheet/ảnh mốc/clip cho flow-operator.
```

Thêm mục mới ngay sau mục "## Kịch bản và mốc":

```markdown
## Nhân vật
Nhân vật bộ kênh: `uv run vidflow quick chars -p <project> --json` (scope `channel`) — KHÔNG khai lại. Đề xuất nhân vật RIÊNG của video khi kịch bản có nhân vật lặp lại ≥ 3 mốc mà bộ kênh chưa có (thường 0–3 nhân vật).
- `id`: IN HOA, 2–24 ký tự A-Z0-9_, gợi nghĩa (`FARMER`, `ANCESTOR`). `name`: tên tiếng Việt. `color`: màu đặc trưng `#RRGGBB`.
- `desc` (tiếng Anh, 2–4 câu): hình dáng đầu/thân theo quy ước nhân vật của brief, trang phục, dáng điệu, đạo cụ đặc trưng, màu đặc trưng; điểm phân biệt với các nhân vật khác.
JSON `[{"id","name","desc","color"}]` → `uv run vidflow quick set-chars -p <project> --json <file>` (ghi đè toàn bộ nhân vật riêng; CLI từ chối xóa nhân vật đang được prompt dùng).
```

Trong mục "## Image prompt từng mốc", thêm 2 gạch đầu dòng sau gạch "Đọc cả các mốc trước/sau...":

```markdown
- Nhân vật đã khai báo (`quick chars --json`) PHẢI nhắc bằng `@ID` (IN HOA, đúng id) ở chỗ mô tả nhân vật, ví dụ `@MODERNYOU buried under a blanket`. Không mô tả lại ngoại hình mâu thuẫn với `desc`; chỉ tả biểu cảm/hành động. CLI tự tách `@ID` và từ chối id lạ hoặc viết thường.
- Nối cảnh: mốc tiếp nối CÙNG khoảnh khắc với mốc liền trước (cùng bối cảnh, chỉ đổi biểu cảm/thêm 1 chi tiết) → thêm `"cont": true` (khi `allow_cont` trong `quick status --json` là true). Đổi cảnh/đổi bối cảnh → không `cont`. Mốc 1 không bao giờ `cont`.
```

Trong bảng kiểm, thêm mục 7:

```markdown
7. Nhân vật đã khai báo được nhắc bằng `@ID`; không mô tả ngoại hình mâu thuẫn `desc`; `cont` chỉ khi thật sự cùng khoảnh khắc với mốc trước.
```

Và sửa ví dụ JSON ghi lô thành `[{"n": 1, "prompt": "...", "verdict": "pass", "score": 8, "issues": [], "cont": false}]`.

Thêm mục mới sau mục Image prompt:

```markdown
## Clip động
Chỉ khi `max_clips` > 0 (`quick status --json` → `clips.max`) và số clip đang bật (`clips.enabled`) chưa đủ. Chọn mốc có MỘT hành động rõ, dễ chuyển động (vật rơi, nhân vật quay đầu, đồ vật rung…), ưu tiên mốc mở đầu/cao trào; không chọn mốc chỉ có chữ hoặc biểu đồ.
Prompt clip (tiếng Anh) = câu neo đầu của bộ kênh, đổi "cartoon" thành "cartoon animation" + `frame-by-frame doodle motion — ` + MỘT chuyển động ≤ 8 giây (ai/cái gì, làm gì, nhân vật nhắc bằng `@ID`) + máy quay (đứng yên / đẩy vào chậm / rung nhẹ) + `no morphing artifacts, no extra limbs or fingers` + `Sound: <một âm thanh ngắn>`.
Bảng kiểm clip (0–10, đạt khi ≥ 7 và mục 1–2 đạt): 1. MỘT chuyển động khớp nội dung ảnh mốc và lời dẫn; 2. không yêu cầu đổi phong cách/bối cảnh so với ảnh; 3. nhân vật nhắc bằng `@ID`; 4. có máy quay và dòng `Sound:`.
JSON `[{"n","prompt","verdict","score","issues"}]` → `uv run vidflow quick set-clip-prompts -p <project> --json <file>` (tự bật clip; CLI từ chối khi vượt `max_clips`).
```

Thay mục "## Gen ảnh mốc (flow-operator)" bằng:

```markdown
## Gen character sheet (flow-operator)
1. `uv run vidflow quick chars -p <project> --json` → nhân vật có `image` null và `uses` > 0.
2. Trong Flow tạo ẢNH 16:9, x1, prompt (thay <...>):
   `A clean character reference sheet for ONE simple hand-drawn 2D doodle cartoon character, on a pure white background with a thin light-grey grid. LAYOUT: 1. full-body front 2. full-body side 3. full-body back 4. head turnaround: front / three-quarter / side 5. four expression panels 6. close-up of the signature prop. DESIGN: <desc>. Signature color: <color>. CONSISTENCY: all panels show the EXACT same character — identical head shape, face, outline weight, colors, proportions. STYLE: <câu neo đầu của bộ kênh> NEGATIVE: no text, labels, numbers or watermark, no redesign between panels.`
3. Tải về → `uv run vidflow quick char-image -p <project> <ID> "<file>"` (+ `--channel` nếu `scope` là channel).

## Gen ảnh mốc (flow-operator)
Dùng kiến thức giao diện, tải file và điều kiện dừng trong `flow-operator.md`.
1. `uv run vidflow quick beats -p <project> --json --todo` → `beats` (gen được ngay) và `blocked` (KHÔNG gen, chỉ báo). `aspect` ở đầu JSON. `beats` rỗng → báo xong.
2. Mỗi mốc: trong ô tạo ẢNH, bấm "+" đính lần lượt TỪNG file trong `attach` (ảnh nhân vật trước, ảnh mốc trước sau cùng nếu có), rồi dán NGUYÊN VĂN `prompt`; tỉ lệ `aspect`, x1, model ảnh mặc định của gói. Làm theo lô 20 mốc, tuần tự.
3. Tải ảnh về (~/Downloads, file mới nhất) rồi chạy ngay `uv run vidflow quick set-image -p <project> <n> "<file>"`. Không tự đổi tên/copy vào images/.
4. Flow từ chối prompt → `uv run vidflow quick fail -p <project> <n> --reason "<nguyên văn>"`, sang mốc sau (mốc lỗi tự rời danh sách tới khi người dùng `retry`).
5. Hết lô → lấy lại `--todo` (mốc nối cảnh được mở khóa khi mốc trước có ảnh), làm tiếp tới khi `beats` rỗng. Captcha, hết tín dụng, giao diện khác hẳn → dừng và báo.
Báo cáo: số ảnh đã gen, mốc lỗi + lý do, mốc bị chặn + lý do, tín dụng còn lại, kết quả `uv run vidflow quick status -p <project>`.

## Gen clip động (flow-operator)
1. `uv run vidflow quick beats -p <project> --json --todo-clips` → `video_model`, `resolution`, `clips` (`n`, `image`, `prompt`, `duration`).
2. Mỗi clip, tuần tự: tạo VIDEO từ ảnh (khung đầu = file `image`), model `video_model`, tỉ lệ `aspect`, thời lượng ngắn nhất ≥ `duration`, dán NGUYÊN VĂN `prompt`, chờ xong (kiểm tra mỗi ~20 giây, tối đa 10 phút).
3. Tải bản `resolution` (mặc định 720p) → `uv run vidflow quick set-clip -p <project> <n> "<file .mp4>"`.
4. Lỗi/từ chối → `uv run vidflow quick fail -p <project> <n> --clip --reason "<nguyên văn>"`, sang clip sau.
Báo cáo: số clip đã gen, clip lỗi + lý do, tín dụng còn lại.
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_quick_jobs.py tests/test_quick_cli.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/vidflow/quick/jobs.py src/vidflow/quick/cli.py .claude/agents/quick-writer.md tests/test_quick_jobs.py tests/test_quick_cli.py
git commit -m "feat(quick): sheets/clips/review Claude jobs and agent instructions"
```

---

### Task 8: Tài liệu module và chạy toàn bộ test

**Files:**
- Modify: `src/vidflow/quick/__init__.py`
- Modify: `CLAUDE.md` (dòng quy trình)

- [ ] **Step 1: Cập nhật docstring `src/vidflow/quick/__init__.py`**

```python
"""Quy trình nhanh "1 ý tưởng → 1 video" (spec 2026-10-07, mở rộng 2026-10-12).

Hàm cho UI:
- preset: `list_presets()`, `load_preset(id)`, `channel_refs_dir(preset)`
- project: `create_quick(root, preset, title)`, `load_quick(root)`, `load_beats(root)`
- thao tác: `ops.set_ideas / pick_idea / set_beat_texts / set_prompt(s) / edit_prompt / set_review / set_image /
  mark_redo / record_fail / clear_errors / update_settings / list_beats / status_summary`
- nhân vật: `chars.lookup / char_rows / set_chars / set_char_image / promote / parse_refs`
- clip: `clips.set_clip_enabled / set_clip_prompts / set_clip / clip_todo`
- việc nền: `jobs.claude_cmd(kind, root, preset)` (kind ∈ jobs.QUICK_KINDS; jobs.CHROME_KINDS cần Chrome),
  `jobs.review_cmd(root, preset, n, clip=)`, `voice.run_voice`, `build.build_quick`
"""
```

- [ ] **Step 2: Cập nhật `CLAUDE.md`** — thêm sau dòng "Gen video: ...":

```markdown
- Quy trình nhanh (`vidflow quick`): nhân vật `@TÊN` (bộ kênh: `presets/refs/<preset>/<ID>.png`; video: `projects/<tên>/refs/<ID>.png`), mốc `cont` đính ảnh mốc trước, clip động tối đa `max_clips` (`quick settings`). Flow: `quick sheets` → `quick flow` → `quick clips`; lỗi Flow ghi bằng `quick fail`, gen lại bằng `quick retry`.
```

- [ ] **Step 3: Chạy toàn bộ test**

Run: `uv run pytest -q`
Expected: tất cả PASS, không có test `skip` mới do kế hoạch này để lại.

- [ ] **Step 4: Kiểm tra thủ công CLI trên project tạm** (không dùng Flow)

```bash
uv run vidflow quick new /tmp/vf-smoke --preset doodle-giai-ma --title Thử
uv run vidflow quick settings -p /tmp/vf-smoke --video-model "Veo 3.1 Lite" --max-clips 2
uv run vidflow quick chars -p /tmp/vf-smoke
uv run vidflow quick status -p /tmp/vf-smoke
uv run vidflow quick prompts -p /tmp/vf-smoke --print | head -c 600
rm -rf /tmp/vf-smoke
```

Expected: không lỗi; `settings` in "clip: Veo 3.1 Lite 720p · tối đa 2 clip"; `prompts --print` có "@TÊN" và "set-clip-prompts".

- [ ] **Step 5: Commit**

```bash
git add src/vidflow/quick/__init__.py CLAUDE.md
git commit -m "docs(quick): document characters, cont and clips workflow"
```
