# Quick pipeline — Nhiều nguồn gen (Giai đoạn 1b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho phép gen ảnh/clip/character sheet bằng `flow` (mặc định), `gemini` (gemini.google.com) hoặc `aistudio` (aistudio.google.com) qua phiên Chrome đã đăng nhập của người dùng; ghi nguồn của từng ảnh/clip; khi hết lượt thì job dừng với mã 3 và thông báo rõ.

**Architecture:** `FlowSettings` thêm `image_provider`/`video_provider`; `QuickProject.limits` lưu các lần hết lượt. `ops`/`clips` ghi `provider` khi nhập ảnh/clip, thêm `record_limit`/`clear_limits`. `jobs.claude_task/claude_cmd/run_claude` nhận `provider` và sinh lời giao việc cho đúng nguồn; `cli._claude` chọn nguồn (ghi đè `--provider` hoặc cài đặt), xóa mốc hết lượt cũ của nguồn đó trước khi chạy, và thoát mã 3 nếu agent báo hết lượt. Hướng dẫn thao tác từng nguồn nằm trong `.claude/agents/gen-providers.md`.

**Tech Stack:** Python 3.11, pydantic v2, typer, pytest (`uv run pytest`).

**Spec:** `docs/superpowers/specs/2026-10-12-quick-refs-clips-ui-design.md` — mục "Bổ sung 2026-10-12 — Nhiều nguồn gen".

## Global Constraints

- Không gọi API trả phí; mọi nguồn dùng phiên Chrome đã đăng nhập của người dùng (`claude --chrome`).
- Nguồn hợp lệ: `flow`, `gemini`, `aistudio` (cả ảnh và clip). Mặc định `flow`.
- Hết lượt / giao diện đòi trả phí → agent chạy `vidflow quick limit ...` rồi DỪNG; không tự chuyển nguồn.
- Job hết lượt kết thúc mã thoát 3, thông báo tiếng Việt chứa "Hết lượt" và tên nguồn.
- Không sửa tay `quick.yaml`/`beats.json`; thông báo lỗi tiếng Việt qua `VidflowError`.
- Test không ghi vào `presets/` thật (fixture `quick_presets`).

## Review Focus

- `beats.json`/`quick.yaml` cũ (không có `provider`, `limits`, `image_provider`) vẫn đọc được — test ở Task 1.
- Nguồn sai chính tả (`--provider gemeni`) → lỗi rõ, không chạy job — test ở Task 1 (settings) và Task 2 (`--provider`).
- Hết lượt ở `gemini` không được làm hỏng/xóa mốc hết lượt của `flow` — test ở Task 2.
- Job chạy xong bình thường (rc 0) nhưng agent đã ghi `limit` → vẫn thoát mã 3 — test ở Task 2.
- `--print` không xóa `limits` và không chạy agent — test ở Task 2.

---

### Task 1: Dữ liệu nguồn gen + ghi nguồn + hết lượt (Model: haiku)

**Files:**
- Modify: `src/vidflow/quick/model.py`, `src/vidflow/quick/ops.py`, `src/vidflow/quick/clips.py`, `src/vidflow/quick/cli.py`
- Test: `tests/test_quick_providers.py`

**Interfaces:**
- Produces: `PROVIDERS = ("flow", "gemini", "aistudio")`, `Provider` (Literal), `FlowSettings.image_provider/video_provider: Provider = "flow"`, `Beat.provider: str = ""`, `Clip.provider: str = ""`, `LimitHit(provider: Provider, kind: Literal["image","video"], reason: str = "", at: str)`, `QuickProject.limits: list[LimitHit]`; `ops.set_image(root, n, src, *, provider="")`, `clips.set_clip(root, n, src, *, provider="")`, `ops.record_limit(root, provider, kind, reason="") -> QuickProject`, `ops.clear_limits(root, provider) -> int`, `ops.check_provider(name) -> str`, `ops.update_settings(..., image_provider=None, video_provider=None)`; `status_summary` thêm `"providers": {"image","video"}` và `"limits": [dict]`. CLI: `set-image --provider`, `set-clip --provider`, `settings --image-provider/--video-provider`, lệnh mới `limit`.

- [ ] **Step 1: Write the failing tests** — `tests/test_quick_providers.py`:

```python
import json

import pytest
from typer.testing import CliRunner

from vidflow.cli import app
from vidflow.errors import VidflowError
from vidflow.quick import clips, ops
from vidflow.quick.model import FlowSettings, load_beats, load_quick

runner = CliRunner()
CP = "doodle motion of @MODERNYOU stretching. Sound: a yawn."


def test_defaults_and_old_files_load(tmp_path):
    (tmp_path / "quick.yaml").write_text("preset: x\nflow: {image_model: A, video_model: '', resolution: 720p}\n",
                                         encoding="utf-8")
    q = load_quick(tmp_path)
    assert q.flow.image_provider == "flow" and q.flow.video_provider == "flow"
    assert q.limits == []
    assert FlowSettings().image_provider == "flow"


def test_settings_providers(qroot):
    q = ops.update_settings(qroot, image_provider="gemini", video_provider="aistudio")
    assert q.flow.image_provider == "gemini" and q.flow.video_provider == "aistudio"
    with pytest.raises(VidflowError, match="gemeni"):
        ops.update_settings(qroot, image_provider="gemeni")
    s = ops.status_summary(qroot)
    assert s["providers"] == {"image": "gemini", "video": "aistudio"}


def test_set_image_and_clip_record_provider(qroot, P, img):
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("a"), "verdict": "pass", "score": 8}])
    b = ops.set_image(qroot, 1, img(), provider="gemini")
    assert b.provider == "gemini"
    b = ops.set_image(qroot, 2, img("b.png"))
    assert b.provider == ""  # không khai → để trống
    clips.set_clip_prompts(qroot, [{"n": 1, "prompt": CP, "verdict": "pass", "score": 8}])
    b = clips.set_clip(qroot, 1, img("v.mp4", b"x"), provider="aistudio")
    assert b.clip.provider == "aistudio"
    with pytest.raises(VidflowError):
        ops.set_image(qroot, 3, img("c.png"), provider="midjourney")


def test_record_and_clear_limits(qroot):
    ops.record_limit(qroot, "flow", "image", reason="hết tín dụng")
    ops.record_limit(qroot, "gemini", "video")
    s = ops.status_summary(qroot)
    assert [(x["provider"], x["kind"]) for x in s["limits"]] == [("flow", "image"), ("gemini", "video")]
    assert s["limits"][0]["reason"] == "hết tín dụng" and s["limits"][0]["at"]
    assert "Hết lượt" in ops.format_status(s)
    assert ops.clear_limits(qroot, "gemini") == 1
    assert [x.provider for x in load_quick(qroot).limits] == ["flow"]
    with pytest.raises(VidflowError):
        ops.record_limit(qroot, "flow", "audio")


def test_cli_provider_commands(qroot, P, img):
    r = runner.invoke(app, ["quick", "settings", "-p", str(qroot), "--image-provider", "aistudio"])
    assert r.exit_code == 0 and "aistudio" in r.output
    ops.set_prompts(qroot, [{"n": 1, "prompt": P("a"), "verdict": "pass", "score": 8}])
    r = runner.invoke(app, ["quick", "set-image", "-p", str(qroot), "1", str(img()), "--provider", "aistudio"])
    assert r.exit_code == 0, r.output
    assert load_beats(qroot).beats[0].provider == "aistudio"
    r = runner.invoke(app, ["quick", "limit", "-p", str(qroot), "--provider", "aistudio", "--kind", "image",
                            "--reason", "cần trả phí"])
    assert r.exit_code == 0, r.output
    s = json.loads(runner.invoke(app, ["quick", "status", "-p", str(qroot), "--json"]).output)
    assert s["limits"][0]["reason"] == "cần trả phí"
    r = runner.invoke(app, ["quick", "limit", "-p", str(qroot), "--provider", "x", "--kind", "image"])
    assert r.exit_code == 1 and "Traceback" not in r.output
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_quick_providers.py -v`
Expected: FAIL — `AttributeError`/`ValidationError` (chưa có `image_provider`).

- [ ] **Step 3: Implement — `src/vidflow/quick/model.py`**

Thêm sau `CHAR_ID`:

```python
PROVIDERS = ("flow", "gemini", "aistudio")
Provider = Literal["flow", "gemini", "aistudio"]
```

Trong `FlowSettings` thêm cuối:

```python
    image_provider: Provider = "flow"  # nguồn gen ảnh + character sheet
    video_provider: Provider = "flow"  # nguồn gen clip
```

Thêm sau `class FlowSettings`:

```python
class LimitHit(BaseModel):
    """Một lần nguồn gen báo hết lượt (hoặc đòi trả phí) — agent ghi qua `quick limit`."""
    provider: Provider
    kind: Literal["image", "video"]
    reason: str = ""
    at: str  # ISO 8601, giờ máy
```

Trong `QuickProject` thêm cuối (sau `allow_cont`): `limits: list[LimitHit] = []`.
Trong `Clip` thêm cuối: `provider: str = ""  # nguồn đã gen clip`.
Trong `Beat` thêm cuối: `provider: str = ""  # nguồn đã gen ảnh`.

- [ ] **Step 4: Implement — `src/vidflow/quick/ops.py`**

Thêm `PROVIDERS, LimitHit` vào import từ `vidflow.quick.model`; thêm `from datetime import datetime`. Thêm hàm (đặt trước `set_image`):

```python
def check_provider(name: str) -> str:
    if name not in PROVIDERS:
        raise VidflowError(f"Nguồn gen không hợp lệ: {name!r} (chọn: {', '.join(PROVIDERS)}).")
    return name


def record_limit(root: Path, provider: str, kind: str, reason: str = "") -> QuickProject:
    """Agent báo nguồn hết lượt / đòi trả phí. Job đang chạy sẽ kết thúc mã 3."""
    check_provider(provider)
    if kind not in ("image", "video"):
        raise VidflowError("kind phải là image hoặc video.")
    q = load_quick(root)
    q.limits.append(LimitHit(provider=provider, kind=kind, reason=reason.strip(),
                             at=datetime.now().isoformat(timespec="seconds")))
    save_quick(root, q)
    return q


def clear_limits(root: Path, provider: str) -> int:
    """Xóa các mốc hết lượt của một nguồn (khi bắt đầu job mới với nguồn đó). Trả số mục đã xóa."""
    q = load_quick(root)
    before = len(q.limits)
    q.limits = [x for x in q.limits if x.provider != provider]
    if len(q.limits) != before:
        save_quick(root, q)
    return before - len(q.limits)
```

Sửa `set_image`: chữ ký thành `def set_image(root: Path, n: int, src: Path, *, provider: str = "") -> Beat:`; dòng đầu thân hàm thêm `if provider: check_provider(provider)`; thay `beat.image, beat.status, beat.error = rel, "ok", ""` bằng `beat.image, beat.status, beat.error, beat.provider = rel, "ok", "", provider`.

Sửa `update_settings`: thêm 2 tham số cuối `image_provider: str | None = None, video_provider: str | None = None`, và ngay trước `save_quick(root, q)` cuối hàm thêm:

```python
    if image_provider is not None:
        q.flow.image_provider = check_provider(image_provider)
    if video_provider is not None:
        q.flow.video_provider = check_provider(video_provider)
```

Trong `status_summary`, thêm vào dict trả về (cạnh `"allow_cont"`):

```python
        "providers": {"image": q.flow.image_provider, "video": q.flow.video_provider},
        "limits": [x.model_dump() for x in q.limits],
```

Trong `format_status`, trước `if s["voice_s"] is not None:` thêm:

```python
    for x in s.get("limits", []):
        what = "ảnh" if x["kind"] == "image" else "clip"
        lines.append(f"Hết lượt {what} ở {x['provider']} ({x['at']})" + (f": {x['reason']}" if x["reason"] else ""))
```

- [ ] **Step 5: Implement — `src/vidflow/quick/clips.py`**

Import thêm `from vidflow.quick.ops import PASSING, check_provider`. Sửa `set_clip` chữ ký thành `def set_clip(root: Path, n: int, src: Path, *, provider: str = "") -> Beat:`, dòng đầu thân hàm thêm `if provider: check_provider(provider)`, và thay `b.clip.file, b.clip.status, b.clip.error = rel, "ok", ""` bằng `b.clip.file, b.clip.status, b.clip.error, b.clip.provider = rel, "ok", "", provider`.

- [ ] **Step 6: Implement — `src/vidflow/quick/cli.py`**

Thêm hằng sau `ClipOpt`:

```python
ProviderOpt = Annotated[Optional[str], typer.Option("--provider", help="Nguồn gen: flow | gemini | aistudio")]
```

Sửa `set_image`:

```python
@_cmd(quick_app, "set-image")
def set_image(project: ProjectOpt, n: Annotated[int, typer.Argument()], file: Annotated[Path, typer.Argument()],
              provider: ProviderOpt = None):
    """Gắn ảnh cho mốc → images/NNN_MM-SS.<ext>."""
    b = ops.set_image(project, n, file, provider=provider or "")
    typer.echo(f"Mốc {n} → {b.image}")
```

Sửa `set_clip` tương tự (`provider: ProviderOpt = None`, gọi `clips.set_clip(project, n, file, provider=provider or "")`).

Sửa `settings`: thêm 2 option cuối và truyền vào `update_settings`, in thêm nguồn:

```python
             image_provider: Annotated[Optional[str], typer.Option(help="Nguồn gen ảnh: flow | gemini | aistudio")] = None,
             video_provider: Annotated[Optional[str], typer.Option(help="Nguồn gen clip: flow | gemini | aistudio")] = None):
    """Cài đặt nguồn gen, model, giới hạn clip, nối cảnh, nhân vật bộ kênh."""
    q = ops.update_settings(project, image_model=image_model, video_model=video_model, resolution=resolution,
                            max_clips=max_clips, allow_cont=allow_cont, channel_chars=channel_char,
                            image_provider=image_provider, video_provider=video_provider)
    typer.echo(f"Nguồn ảnh: {q.flow.image_provider} · nguồn clip: {q.flow.video_provider} · "
               f"ảnh: {q.flow.image_model} · clip: {q.flow.video_model or '(chưa chọn)'} {q.flow.resolution} · "
               f"tối đa {q.max_clips} clip · nối cảnh: {'bật' if q.allow_cont else 'tắt'}")
```

Thêm lệnh mới (cạnh `fail`):

```python
@_cmd(quick_app, "limit")
def limit(project: ProjectOpt,
          provider: Annotated[str, typer.Option(help="flow | gemini | aistudio")],
          kind: Annotated[str, typer.Option(help="image | video")],
          reason: Annotated[str, typer.Option(help="Nguyên văn thông báo của dịch vụ")] = ""):
    """Agent báo nguồn gen hết lượt / đòi trả phí (job sẽ dừng, mã 3)."""
    ops.record_limit(project, provider, kind, reason)
    typer.echo(f"Đã ghi: hết lượt {'ảnh' if kind == 'image' else 'clip'} ở {provider}")
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_quick_providers.py tests/test_quick_clips.py tests/test_quick_cli.py tests/test_quick_model.py -q`
Expected: PASS. Then `uv run pytest -q` — all pass.

- [ ] **Step 8: Commit**

```bash
git add src/vidflow/quick/model.py src/vidflow/quick/ops.py src/vidflow/quick/clips.py src/vidflow/quick/cli.py tests/test_quick_providers.py
git commit -m "feat(quick): generation providers in settings, provider per image/clip, quota limits"
```

---

### Task 2: Job theo nguồn, `--provider`, mã thoát 3, hướng dẫn agent (Model: sonnet)

**Files:**
- Modify: `src/vidflow/quick/jobs.py`, `src/vidflow/quick/cli.py`, `.claude/agents/quick-writer.md`
- Create: `.claude/agents/gen-providers.md`
- Test: `tests/test_quick_jobs.py`, `tests/test_quick_providers.py`

**Interfaces:**
- Consumes (Task 1): `ops.check_provider`, `ops.clear_limits`, `QuickProject.limits`, `FlowSettings.image_provider/video_provider`, CLI `limit`, `set-image/set-clip --provider`.
- Produces: `jobs.PROVIDER_LABELS = {"flow": "Google Flow", "gemini": "Gemini (gemini.google.com)", "aistudio": "Google AI Studio (aistudio.google.com)"}`; `jobs.provider_for(kind, q) -> str` (sheets/flow → image_provider, clips → video_provider); `claude_task(kind, root, preset, provider="flow")`, `claude_cmd(kind, root, preset, provider="flow")`, `run_claude(kind, root, preset, *, provider="flow", log=None)`; `cli._claude(kind, project, print_only, provider=None)`; options `--provider` on `quick sheets|flow|clips`; `LIMIT_EXIT = 3`.

- [ ] **Step 1: Write the failing tests**

Thêm vào `tests/test_quick_jobs.py`:

```python
from vidflow.quick.jobs import PROVIDER_LABELS


@pytest.mark.parametrize("kind", ["sheets", "flow", "clips"])
@pytest.mark.parametrize("provider", ["flow", "gemini", "aistudio"])
def test_gen_tasks_follow_provider(kind, provider, preset):
    t = claude_task(kind, ROOT, preset, provider=provider)
    assert "gen-providers.md" in t and PROVIDER_LABELS[provider] in t
    assert f"--provider {provider}" in t
    assert "quick limit" in t and "DỪNG" in t
    assert "trả phí" in t
    other = [p for p in PROVIDER_LABELS if p != provider]
    for p in other:
        assert PROVIDER_LABELS[p] not in t
    cmd = claude_cmd(kind, ROOT, preset, provider=provider)
    assert "--chrome" in cmd and cmd[-1] == t


def test_flow_default_still_mentions_flow_operator(preset):
    assert "flow-operator.md" in claude_task("flow", ROOT, preset)


def test_unknown_provider_rejected(preset):
    with pytest.raises(ValueError):
        claude_task("flow", ROOT, preset, provider="midjourney")
```

Thêm vào `tests/test_quick_providers.py`:

```python
import vidflow.quick.jobs as jobs_mod


def _ready_for_flow(qroot, P):
    ops.set_prompts(qroot, [{"n": i, "prompt": P("x"), "verdict": "pass", "score": 8} for i in range(1, 5)])


def test_job_uses_settings_provider_and_override(qroot, P, monkeypatch):
    _ready_for_flow(qroot, P)
    calls = []
    monkeypatch.setattr(jobs_mod, "run_claude", lambda kind, root, preset, **kw: calls.append((kind, kw.get("provider"))) or 0)
    ops.update_settings(qroot, image_provider="gemini")
    assert runner.invoke(app, ["quick", "flow", "-p", str(qroot)]).exit_code == 0
    assert runner.invoke(app, ["quick", "sheets", "-p", str(qroot), "--provider", "aistudio"]).exit_code == 0
    assert calls == [("flow", "gemini"), ("sheets", "aistudio")]
    r = runner.invoke(app, ["quick", "flow", "-p", str(qroot), "--provider", "gemeni"])
    assert r.exit_code == 1 and len(calls) == 2


def test_job_exits_3_when_agent_records_limit(qroot, P, monkeypatch):
    _ready_for_flow(qroot, P)
    ops.record_limit(qroot, "flow", "video")  # cũ, nguồn khác loại — vẫn bị xóa vì cùng nguồn flow
    ops.record_limit(qroot, "gemini", "image")  # nguồn khác — giữ nguyên

    def fake_run(kind, root, preset, **kw):
        ops.record_limit(root, kw["provider"], "image", reason="đã dùng hết")
        return 0

    monkeypatch.setattr(jobs_mod, "run_claude", fake_run)
    r = runner.invoke(app, ["quick", "flow", "-p", str(qroot)])
    assert r.exit_code == 3
    assert "Hết lượt" in r.output and "flow" in r.output
    hits = [(x.provider, x.kind) for x in load_quick(qroot).limits]
    assert hits == [("gemini", "image"), ("flow", "image")]


def test_print_does_not_clear_limits_or_run(qroot, P, monkeypatch):
    _ready_for_flow(qroot, P)
    ops.record_limit(qroot, "flow", "image")
    monkeypatch.setattr(jobs_mod, "run_claude", lambda *a, **kw: pytest.fail("không được chạy"))
    r = runner.invoke(app, ["quick", "flow", "-p", str(qroot), "--print", "--provider", "gemini"])
    assert r.exit_code == 0 and "Gemini" in r.output
    assert len(load_quick(qroot).limits) == 1
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_quick_jobs.py tests/test_quick_providers.py -v`
Expected: FAIL — `ImportError: cannot import name 'PROVIDER_LABELS'`.

- [ ] **Step 3: Implement `src/vidflow/quick/jobs.py`**

Thêm sau `CHROME_KINDS`:

```python
PROVIDER_LABELS = {
    "flow": "Google Flow",
    "gemini": "Gemini (gemini.google.com)",
    "aistudio": "Google AI Studio (aistudio.google.com)",
}
GEN_KINDS = ("sheets", "flow", "clips")


def provider_for(kind: str, q) -> str:
    """Nguồn mặc định cho job gen theo cài đặt video (q: QuickProject)."""
    return q.flow.video_provider if kind == "clips" else q.flow.image_provider


def _operator(provider: str, section: str, writer: Path) -> str:
    """Câu mở đầu cho agent thao tác trình duyệt theo nguồn."""
    if provider not in PROVIDER_LABELS:
        raise ValueError(f"Nguồn gen không hỗ trợ: {provider}")
    label = PROVIDER_LABELS[provider]
    extra = (f" và {AGENTS / 'flow-operator.md'} (kiến thức giao diện Flow, tải file, điều kiện dừng)"
             if provider == "flow" else "")
    return (f"Bạn là operator gen trên {label}, dùng phiên Chrome đã đăng nhập của người dùng. Đọc và tuân thủ mục "
            f"'{provider}' trong {AGENTS / 'gen-providers.md'}{extra}, và mục '{section}' trong {writer}.")


def _limit_rule(cli: str, root: Path, provider: str, kind: str) -> str:
    return (f"Hết lượt/hết tín dụng ở {PROVIDER_LABELS[provider]}, hoặc giao diện đòi bật thanh toán / nhập thẻ / "
            f"API key trả phí / báo phí → KHÔNG bấm tiếp, chạy `{cli} limit -p {root} --provider {provider} "
            f"--kind {kind} --reason \"<nguyên văn>\"` rồi DỪNG và báo cáo.")
```

Trong `LABELS`, bỏ đuôi "trong Google Flow" của 3 nhãn gen (CLI tự in tên nguồn): `"sheets": "Gen character sheet"`, `"flow": "Gen ảnh mốc"`, `"clips": "Gen clip động"`.

Sửa chữ ký `def claude_task(kind: str, project_root: Path, preset: Preset, provider: str = "flow") -> str:`.

Thay 3 nhánh `flow`, `sheets`, `clips` bằng:

```python
    if kind == "flow":
        label = PROVIDER_LABELS.get(provider, provider)
        return (f"{_operator(provider, 'Gen ảnh mốc', writer)} {common} "
                f"Lấy việc bằng `{cli} beats -p {root} --json --todo` (mốc gen được ngay; trường `file` là tên đích "
                "NNN_MM-SS; `attach` là các ảnh phải đính kèm theo đúng thứ tự trước khi dán prompt; `blocked` là mốc "
                f"chưa gen được — KHÔNG gen, chỉ báo). Gen ẢNH (không phải video) trên {label}, tỉ lệ {preset.aspect}, "
                f"x1 mỗi mốc, prompt nguyên văn `prompt`, theo lô {BATCH} mốc. Tải từng ảnh về rồi chạy ngay "
                f"`{cli} set-image -p {root} <n> \"<file tải về>\" --provider {provider}` — lệnh tự lưu thành "
                "images/NNN_MM-SS.jpg và cập nhật beats.json. Dịch vụ từ chối prompt → "
                f"`{cli} fail -p {root} <n> --reason \"<nguyên văn>\"` rồi sang mốc sau. "
                f"{_limit_rule(cli, root, provider, 'image')} "
                f"Hết lô thì chạy lại `{cli} beats -p {root} --json --todo` và làm lô tiếp cho tới khi `beats` rỗng. "
                "Báo cáo: số ảnh đã gen, mốc lỗi kèm lý do, mốc bị chặn kèm lý do, lượt/tín dụng còn lại nếu thấy.")
    if kind == "sheets":
        label = PROVIDER_LABELS.get(provider, provider)
        return (f"{_operator(provider, 'Gen character sheet', writer)} {common} Lấy nhân vật bằng "
                f"`{cli} chars -p {root} --json`; với mỗi nhân vật có `image` null và `uses` > 0: gen MỘT ảnh "
                f"character sheet trên {label} (tỉ lệ 16:9, x1) theo mẫu prompt trong mục đó, tải về rồi chạy "
                f"`{cli} char-image -p {root} <ID> \"<file>\"` (thêm `--channel` khi `scope` là channel; nguồn: "
                f"--provider {provider} chỉ để ghi nhận trong báo cáo). {_limit_rule(cli, root, provider, 'image')} "
                "Báo cáo: nhân vật đã gen, nhân vật lỗi kèm lý do, lượt/tín dụng còn lại nếu thấy.")
    if kind == "clips":
        label = PROVIDER_LABELS.get(provider, provider)
        return (f"{_operator(provider, 'Gen clip động', writer)} {common} Lấy việc bằng "
                f"`{cli} beats -p {root} --json --todo-clips` (model, độ phân giải, và từng clip: ảnh nguồn `image`, "
                f"`prompt`, `duration`). Mỗi clip: tạo VIDEO từ ảnh trên {label}, đính `image` làm khung đầu, chọn "
                "model gần `video_model` nhất mà nguồn này có, thời lượng ngắn nhất ≥ `duration` (không có thì dài nhất), "
                "dán `prompt` nguyên văn, tải bản `resolution` (hoặc gần nhất) về rồi chạy "
                f"`{cli} set-clip -p {root} <n> \"<file>\" --provider {provider}`. Từ chối/lỗi → "
                f"`{cli} fail -p {root} <n> --clip --reason \"<nguyên văn>\"`. "
                f"{_limit_rule(cli, root, provider, 'video')} Tuần tự từng clip. "
                "Báo cáo: số clip đã gen, clip lỗi kèm lý do, lượt/tín dụng còn lại nếu thấy.")
```

(Lưu ý: test `test_gen_tasks_follow_provider` yêu cầu chuỗi `--provider {provider}` xuất hiện cả ở `sheets` — câu "nguồn: --provider X chỉ để ghi nhận" đáp ứng điều đó; nhãn của nguồn khác không được xuất hiện, nên `_common` và hướng dẫn chung không nhắc tên các nguồn khác.)

Sửa `claude_cmd` và `run_claude`:

```python
def claude_cmd(kind: str, project_root: Path, preset: Preset, provider: str = "flow") -> list[str]:
    cmd = ["claude", "-p", "--permission-mode", "bypassPermissions"]
    if kind in CHROME_KINDS:
        cmd.append("--chrome")
    return cmd + [claude_task(kind, project_root, preset, provider)]


def run_claude(kind: str, project_root: Path, preset: Preset, *, provider: str = "flow", log: IO | None = None) -> int:
    """Chạy job Claude đồng bộ (CLI). UI nên dùng `claude_cmd` với JobRunner riêng."""
    r = subprocess.run(claude_cmd(kind, project_root, preset, provider), cwd=REPO, stdin=subprocess.DEVNULL,
                       stdout=log, stderr=subprocess.STDOUT if log else None)
    return r.returncode
```

Kiểm tra `_common(...)` không chứa chữ "Google Flow": hiện có câu "Người dùng chỉ dùng tín dụng gói Google Flow" — đổi thành "Người dùng chỉ dùng gói Google AI qua phiên đăng nhập (không API trả phí)" để không lộ nhãn nguồn khác trong task của gemini/aistudio. Giữ nguyên phần tiếp theo của câu: "KHÔNG chạy `vidflow gen`, `vidflow estimate`, `vidflow refimg`" (test hiện có kiểm tra chuỗi này).

- [ ] **Step 4: Implement `src/vidflow/quick/cli.py`**

Thêm hằng `LIMIT_EXIT = 3`. Thay `_claude` bằng:

```python
def _claude(kind: str, project: Path, print_only: bool, provider: str | None = None):
    q = load_quick(project)
    if kind == "script" and not q.picked_idea():
        raise VidflowError("Chưa chọn ý tưởng — `vidflow quick pick -p ... <n>`.")
    if kind in ("prompts", "flow", "clips"):
        require_beats(project)
    if kind == "clips" and not q.flow.video_model:
        raise VidflowError("Chưa chọn model clip — `vidflow quick settings -p <project> --video-model \"Veo 3.1 Lite\"`.")
    preset = load_preset(q.preset)
    prov = ops.check_provider(provider) if provider else (jobs.provider_for(kind, q) if kind in jobs.GEN_KINDS else "flow")
    if print_only:
        typer.echo(jobs.claude_task(kind, project, preset, prov))
        return
    if kind in jobs.GEN_KINDS:
        ops.clear_limits(project, prov)
    typer.echo(f"{jobs.LABELS[kind]} ({jobs.PROVIDER_LABELS[prov]})…" if kind in jobs.GEN_KINDS else f"{jobs.LABELS[kind]}…")
    rc = jobs.run_claude(kind, project, preset, provider=prov)
    hits = [x for x in load_quick(project).limits if x.provider == prov] if kind in jobs.GEN_KINDS else []
    if hits:
        h = hits[-1]
        typer.secho(f"Hết lượt {'ảnh' if h.kind == 'image' else 'clip'} ở {prov}"
                    + (f": {h.reason}" if h.reason else "")
                    + " — đổi nguồn bằng `vidflow quick settings -p <project> --image-provider/--video-provider ...` "
                      "hoặc chạy lại với `--provider ...`.", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(LIMIT_EXIT)
    if rc:
        raise VidflowError(f"Job Claude '{kind}' lỗi (mã {rc}).")
    typer.echo(ops.format_status(ops.status_summary(project)))
```

Sửa 3 lệnh gen để nhận `--provider` (dùng `ProviderOpt` từ Task 1):

```python
@_cmd(quick_app, "sheets")
def sheets(project: ProjectOpt, print_only: PrintOpt = False, provider: ProviderOpt = None):
    """Gen character sheet còn thiếu (nguồn theo cài đặt hoặc --provider; claude --chrome)."""
    _claude("sheets", project, print_only, provider)


@_cmd(quick_app, "flow")
def flow(project: ProjectOpt, print_only: PrintOpt = False, provider: ProviderOpt = None):
    """Gen ảnh mốc pending/redo (nguồn theo cài đặt hoặc --provider; claude --chrome)."""
    _claude("flow", project, print_only, provider)


@_cmd(quick_app, "clips")
def clips_flow(project: ProjectOpt, print_only: PrintOpt = False, provider: ProviderOpt = None):
    """Gen clip động (nguồn theo cài đặt hoặc --provider; claude --chrome)."""
    _claude("clips", project, print_only, provider)
```

`ProviderOpt` phải được định nghĩa phía trên các lệnh này (chuyển định nghĩa lên ngay sau `ClipOpt` nếu đang ở dưới). `typer.Exit(3)` không phải `VidflowError` nên wrapper `_cmd` để nó đi qua với mã 3; CliRunner ghi `exit_code == 3` và `typer.secho(err=True)` vẫn xuất hiện trong `r.output` (CliRunner gộp stderr mặc định — nếu phiên bản click tách stderr, kiểm tra `r.output + (r.stderr or "")` trong test thay vì sửa code).

- [ ] **Step 5: Create `.claude/agents/gen-providers.md`**

```markdown
---
name: gen-providers
description: Hướng dẫn thao tác các nguồn gen ảnh/clip qua phiên Chrome đã đăng nhập của người dùng — Google Flow, Gemini (gemini.google.com), Google AI Studio (aistudio.google.com). Agent gen (job sheets/flow/clips của `vidflow quick`) đọc đúng mục của nguồn được giao.
---

Quy tắc chung cho mọi nguồn:
- Dùng công cụ Claude in Chrome trên trình duyệt của người dùng; không có công cụ trình duyệt → DỪNG, báo "Cần mở phiên bằng `claude --chrome`".
- Chưa đăng nhập → nhờ người dùng tự đăng nhập; không nhập mật khẩu hộ.
- KHÔNG gọi API, KHÔNG tạo API key, KHÔNG bật thanh toán, KHÔNG nhập thẻ. Mọi màn hình nhắc phí/thanh toán/nâng cấp trả tiền = hết lượt: chạy `uv run vidflow quick limit -p <project> --provider <nguồn> --kind image|video --reason "<nguyên văn>"` rồi DỪNG.
- Dấu hiệu hết lượt (mọi nguồn): thông báo đạt giới hạn/hạn mức ngày, hết tín dụng, "try again tomorrow", nút tạo bị khóa kèm lời nhắc nâng cấp → `quick limit ...` rồi DỪNG.
- Tải file: Chrome phải tắt "Ask where to save each file before downloading". File không xuất hiện trong ~/Downloads sau 15 giây → DỪNG và nhờ người dùng tắt tùy chọn đó.
- Dịch vụ từ chối một prompt (vi phạm chính sách, lỗi một lần) KHÔNG phải hết lượt: `quick fail ...` rồi làm mốc tiếp.
- Giao diện khác hẳn mô tả dưới đây → làm theo giao diện thật nếu chắc chắn, ghi lại ngắn gọn giao diện quan sát được (vị trí nút, tên model, cách đính ảnh, cách tải) trong báo cáo để cập nhật file này; không chắc → DỪNG và báo.

## flow
Theo `flow-operator.md` (giao diện Flow, cài đặt tác nhân, tải 1K/2K, điều kiện dừng) cùng các mục gen trong `quick-writer.md`. Đính ảnh tham chiếu bằng nút "+" ở ô "Bạn muốn tạo gì?".

## gemini
Trang: https://gemini.google.com (tài khoản gói Google AI của người dùng; hạn mức theo ngày, tách khỏi tín dụng Flow).
- Mỗi mốc/clip: mở cuộc trò chuyện MỚI để ảnh trước không ảnh hưởng (trừ khi chính `attach` yêu cầu ảnh mốc trước).
- Ảnh: chọn công cụ/chế độ tạo ảnh (Nano Banana / "Create image"); đính các file trong `attach` bằng nút tải tệp/"+" của ô nhập; dán prompt nguyên văn, thêm câu "Aspect ratio <tỉ lệ>." ở cuối nếu giao diện không có nút chọn tỉ lệ; tạo 1 ảnh.
- Clip: chọn công cụ video (Veo); tải ảnh nguồn `image` lên làm khung đầu; dán prompt nguyên văn; chờ (kiểm tra mỗi ~20 giây, tối đa 10 phút).
- Tải: dùng nút tải xuống của ảnh/video (bản chất lượng cao nhất có), lấy file mới nhất trong ~/Downloads.
- Hạn mức video ở Gemini thường rất thấp (vài video/ngày): gặp thông báo giới hạn → `quick limit ... --kind video` rồi DỪNG.

## aistudio
Trang: https://aistudio.google.com (đăng nhập bằng tài khoản Google của người dùng, chỉ dùng giao diện web).
- Chọn model tạo ảnh (Nano Banana / Gemini image) hoặc model video (Veo) trong danh sách model của giao diện; đặt tỉ lệ khung hình trong phần cài đặt chạy nếu có.
- Đính ảnh tham chiếu (`attach` / `image`) bằng nút thêm tệp của ô prompt; dán prompt nguyên văn; chạy (Run).
- Tải ảnh/video bằng nút tải xuống của kết quả.
- AI Studio có thể yêu cầu dự án có thanh toán hoặc API key cho một số model (đặc biệt video): gặp bất kỳ yêu cầu nào như vậy → `quick limit ... --reason "cần trả phí"` rồi DỪNG. Không chọn "Get API key", không liên kết billing.
```

- [ ] **Step 6: `.claude/agents/quick-writer.md`** — trong mục "Gen ảnh mốc (flow-operator)" bước 3 đổi lệnh thành `uv run vidflow quick set-image -p <project> <n> "<file>" --provider <nguồn>`; trong mục "Gen clip động" bước 3 đổi thành `uv run vidflow quick set-clip -p <project> <n> "<file .mp4>" --provider <nguồn>`; thêm cuối mỗi mục gen (sheet, ảnh mốc, clip) một dòng: `Nguồn gen do lời giao việc chỉ định (flow / gemini / aistudio) — thao tác theo mục tương ứng trong gen-providers.md; hết lượt hoặc bị đòi trả phí → quick limit ... rồi DỪNG.`

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_quick_jobs.py tests/test_quick_providers.py tests/test_quick_cli.py -q`
Expected: PASS. Then `uv run pytest -q` — all pass.

- [ ] **Step 8: Commit**

```bash
git add src/vidflow/quick/jobs.py src/vidflow/quick/cli.py .claude/agents/gen-providers.md .claude/agents/quick-writer.md tests/test_quick_jobs.py tests/test_quick_providers.py
git commit -m "feat(quick): provider-aware gen jobs, --provider override, exit 3 on quota"
```
