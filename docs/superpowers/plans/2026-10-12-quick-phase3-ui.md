# Quick pipeline — Giao diện mới + 4 màn quy trình nhanh (Giai đoạn 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đổi toàn bộ `vidflow ui` sang giao diện sáng theo mockup (token màu, Be Vietnam Pro + JetBrains Mono, khung 3 vùng, bỏ thiên hà/gradient/glow/emoji, trạng thái luôn bằng chữ) mà giữ nguyên chức năng quy trình đầy đủ; thêm API quy trình nhanh và 4 màn: Bảng mốc, Nhân vật, Xem thử & Xuất, Tạo video nhanh.

**Architecture:** 3a — viết lại `style.css`/`index.html`, xóa `galaxy.js`, sửa nhỏ `app.js` (vẽ thanh trái vào `#railNav`, bỏ emoji); không đổi hành vi. 3b — API quy trình nhanh nằm trong module mới `src/vidflow/ui/quick_api.py` (một `APIRouter` gắn vào `create_app`), lệnh việc nền trong `src/vidflow/ui/quick_jobs.py`; mọi ghi gọi `vidflow.quick.ops/chars/clips` (cùng luật với CLI). Việc nền dùng `JobRunner` hiện có (một việc mỗi lúc, thêm nhãn và dừng việc); kiểm duyệt một mốc chạy ở `ReviewRunner` riêng nên không bị job Flow chặn. Giao diện quy trình nhanh nằm trong `static/quick.js` (vanilla JS, nạp sau `app.js`, dùng chung `h/api/toast/S/startPolling`), mỗi màn tự đăng ký vào `QSCREENS`.

**Tech Stack:** Python 3.11, FastAPI + TestClient, pydantic v2, pytest (`uv run pytest`); HTML/CSS/vanilla JS không build; `node --check` để kiểm tra cú pháp JS.

**Spec:** `docs/superpowers/specs/2026-10-12-quick-refs-clips-ui-design.md` (Giai đoạn 3 — Giao diện) + phụ lục người dùng quyết định: nguồn gen ảnh/clip `flow | gemini | aistudio` (Giai đoạn 1b, kế hoạch riêng, làm TRƯỚC kế hoạch này). Mockup đã duyệt (chỉ tham khảo bố cục/chữ/màu) trong `docs/superpowers/mockups/quick/`: `Main.dc.html` (Bảng mốc), `Characters.dc.html`, `Preview.dc.html`, `NewVideo.dc.html`.

## Global Constraints

- Người dùng chỉ dùng tín dụng gói Google Flow: KHÔNG chạy `vidflow gen`, `vidflow estimate`, `vidflow refimg`; job UI chỉ gọi `claude -p` (job Claude của `vidflow.quick.jobs`) hoặc `python -m vidflow quick <voice|render|build>`.
- UI luôn bắt đăng nhập: mọi route mới nằm sau middleware `Auth` (`/api/*`, `/media/*` → 401 khi chưa đăng nhập). KHÔNG dùng `--no-auth` ở bất kỳ bước nào (kể cả kiểm tra tay).
- Không sửa tay `state.json`, `quick.yaml`, `beats.json` — mọi ghi qua hàm trong `vidflow.quick.ops` / `chars` / `clips`.
- Giữ stack: FastAPI + HTML/CSS/vanilla JS trong `src/vidflow/ui/static`; không React, không bước build, không thêm thư viện Python (đã có `python-multipart`).
- Token màu trên `:root`: nền `#E3EBE2`, mặt khung `#F2F6F1`, đường kẻ `#CCD8CB`, ô nhập `#EAF1E9`, viền nút `#B8C7B7`, chữ `#0E1238`, chữ phụ `#4A4F6E`; chính `#000080`, phụ `#0069ba`, thành công `#1fba00` (chữ xanh lá `#157A00`), lỗi `#C8283E`, cảnh báo `#8A4B00` trên `#FDEBD2`.
- Phông: Be Vietnam Pro (chữ), JetBrains Mono (số mốc, thời gian, `@TÊN`) qua Google Fonts.
- Bỏ nền sao/tinh vân (`galaxy.js`, `#stars`, `.nebula`), gradient, glow, emoji trong UI (cho phép duy nhất dấu `✓` ở chấm bước, như mockup).
- Khung 3 vùng: thanh trái (logo, video đang mở, điều hướng, tiến độ, trạng thái việc nền), vùng giữa, khung phải. Dưới 900px các vùng xếp dọc.
- Trạng thái luôn có chữ: Có ảnh / Đang gen / Lỗi / Chờ / Gen lại / Bị chặn.
- Màn quy trình đầy đủ (kịch bản, cảnh, khung, prompt, kiểm duyệt) giữ chức năng, chỉ đổi giao diện.
- Job quy trình nhanh: `ideas | script | prompts | sheets | flow | clips | voice | render | build` (`sheets` = gen character sheet, theo quyết định Giai đoạn 1). `JobRunner` chạy một việc mỗi lúc.
- Nguồn gen (Giai đoạn 1b — đã có khi bắt đầu kế hoạch này): `QuickProject.flow.image_provider` / `.video_provider` ∈ `flow | gemini | aistudio` (mặc định `flow`), qua phiên Chrome đã đăng nhập, dùng cho cả ảnh và clip; `ops.update_settings(root, ..., image_provider=None, video_provider=None)`; `vidflow.quick.jobs.claude_cmd(kind, root, preset, provider=None)` (ghi đè một lần cho `sheets | flow | clips`); `Beat.provider` (ảnh) và `Beat.clip.provider`; hết lượt → job kết thúc với dòng "hết lượt ở <provider>" (mã thoát 3 khi chạy qua CLI).
- Model clip bắt buộc chọn khi `max_clips > 0`; độ phân giải clip mặc định `720p`.
- Job `render` gọi CLI Giai đoạn 2 `vidflow quick render -p <project> [--resolution 1080p|720p] [--transition scene|cut|fade] [--clip-fit trim|speed] [--zoom/--no-zoom] [--subtitles/--no-subtitles] [--clip-audio/--no-clip-audio] [--logo/--no-logo] [--music/--no-music]` bằng subprocess; test giả lập, không phụ thuộc mã Giai đoạn 2.
- Kéo mép mốc để đổi thời lượng: KHÔNG làm (thời lượng do giọng đọc quyết định).
- Thông báo lỗi tiếng Việt; lỗi người dùng → HTTP 422 (409 khi trùng/đang bận, 404 khi không có).
- Test không ghi vào `presets/` thật — dùng fixture `quick_presets` (đã có trong `tests/conftest.py`).

Quyết định cho chỗ spec chưa nói rõ (ghi để người duyệt biết):
- Thêm route ngoài danh sách spec vì màn cần: `GET /api/quick` (danh sách), `GET /api/presets` (form Tạo video nhanh), `POST /api/quick/{name}/retry` (nút "Chạy lại mốc lỗi" = `ops.clear_errors` rồi chạy Flow), `POST /api/quick/{name}/jobs/stop` (nút "Tạm dừng"), `GET /api/quick/{name}/waveform` (sóng âm), `GET /media/_presets/{preset}/{file}` (ảnh `presets/refs/`; `_presets` không trùng được tên project vì tên project phải bắt đầu bằng chữ/số).
- "Đang gen" = job `flow` của chính video đang chạy VÀ mốc gen được ngay (Flow không báo từng mốc). "Bị chặn" chỉ khi thiếu ảnh nhân vật; mốc nối cảnh chờ ảnh mốc trước hiện "Chờ" kèm lý do.
- Thanh trái không hiện tín dụng Flow (server không có nguồn số liệu); chỗ đó hiện trạng thái việc nền.
- Tỉ lệ khung trong form Tạo video nhanh chỉ hiển thị (lấy từ bộ kênh; `quick.yaml` không có trường tỉ lệ). Model ảnh chỉ có "Nano Banana 2".
- Chủ đề gợi ý lưu làm tựa tạm (`title`) và gửi kèm job `ideas` như ghi chú người dùng. Tên thư mục tự sinh `<preset>-<MMDD-HHMMSS>`.
- Màn Nhân vật không có "Thêm nhân vật"/"Sửa mô tả" (spec không có API; AI đề xuất ở bước kịch bản). "Gen lại" thay bằng "Thay ảnh" (tải lên) vì job `sheets` chỉ gen nhân vật chưa có ảnh.
- `POST /review` đồng bộ: trả kết quả trong cùng request (tối đa 300 giây), hàng đợi riêng tuần tự giữa các lần kiểm duyệt.
- Khung chi tiết: thanh nút dưới cùng (Gen lại ảnh / AI viết lại / Duyệt tay / Lưu & kiểm duyệt) áp cho prompt ảnh; ô clip có nút riêng "Duyệt tay" và "Lưu & kiểm duyệt clip".
- Các bước ý tưởng → kịch bản → giọng đọc → prompt hiện thành thẻ "Bước tiếp theo" trên Bảng mốc (spec không có màn riêng). Cài đặt video của project đã tạo: bấm "Cài đặt" trên Bảng mốc (khung phải).
- Xem thử: clip phát không tiếng (giọng đọc là `<audio>`); mặc định xuất 1080p theo mockup.
- Nguồn gen trên UI: chọn mặc định (ảnh + clip) ở Tạo video nhanh và Cài đặt video; ghi đè một lần bằng ô "Nguồn" trên đầu Bảng mốc (mặc định "theo cài đặt"), áp cho Gen ảnh / Gen clip / Gen sheet (cả màn Nhân vật) → trường `provider` của `POST /api/quick/{name}/jobs`, chỉ nhận cho `sheets | flow | clips`. Job UI chạy `claude -p` trực tiếp (không qua CLI) nên "hết lượt" được nhận khi mã thoát = 3 HOẶC log có "hết lượt ở" (`Job.quota_exhausted`); `Job.provider` là nguồn thực dùng (ghi đè hoặc theo cài đặt).
- Ghi đồng thời `beats.json` (kiểm duyệt chạy song song job Flow) không khóa file: mỗi lần ghi là đọc–sửa–ghi vài mili giây; chấp nhận rủi ro nhỏ này ở bản này.

## Review Focus

- Project nhanh vừa tạo, chưa có `beats.json` (bước `new`) → `GET /api/quick/{name}` vẫn trả 200 với `beats: []` để UI mở được — test `test_get_quick_new_project_without_beats` ở Task 4.
- URL `/media` lạ (`quick.yaml`, `beats.json`, `..%2F`, id bộ kênh sai) không được lộ file ngoài `images/ clips/ refs/ out/ audio/` và `presets/refs/<id>/` — test `test_media_quick_and_preset_refs` ở Task 4.
- Tạo video nhanh lỗi giữa chừng (preset sai, `channel_chars` có tên lạ, thiếu model clip) → không để lại thư mục dở dang, không chạy job — test `test_create_validation_leaves_nothing_behind` ở Task 5.
- Tùy chọn xuất lạ/độc (`"resolution": "1080p; rm -rf /"`, khóa lạ như `output`) bị từ chối 422 và không bao giờ thành cờ CLI — test `test_bad_options_rejected` ở Task 3 và `test_jobs_validation_and_options` ở Task 5.
- Tải lên file không phải ảnh (đổi đuôi `.png`) hoặc quá lớn → 422/413, không để lại file trong `refs/` hay `tmp/` — test `test_upload_validation` ở Task 7.

## Bản đồ file

| File | Trách nhiệm |
|---|---|
| `src/vidflow/ui/static/style.css` | Viết lại: token, khung 3 vùng, kiểu quy trình đầy đủ (3a); thêm khối kiểu cho từng màn nhanh (3b) |
| `src/vidflow/ui/static/index.html` | Viết lại: phông, khung `.shell` (thanh trái + `#main`), bỏ `galaxy.js`; 3b nạp `quick.js` |
| `src/vidflow/ui/static/galaxy.js` | Xóa |
| `src/vidflow/ui/static/app.js` | Sửa: vẽ thanh trái vào `#railNav`, `setCurrent`, bỏ emoji (3a); định tuyến project nhanh, trang chủ 2 lối vào (3b) |
| `src/vidflow/ui/static/quick.js` | Mới: 4 màn quy trình nhanh |
| `src/vidflow/ui/auth.py` | Trang đăng nhập theo bảng màu mới |
| `src/vidflow/ui/jobs.py` | `Job.label`, `Job.stopped`, `JobRunner.start(quick=..., options=...)`, `JobRunner.stop()`, `ReviewRunner` |
| `src/vidflow/ui/quick_jobs.py` | Mới: loại việc, nhãn, `option_args`, `build_quick_cmd`, `check_quick_job` |
| `src/vidflow/ui/quick_api.py` | Mới: `quick_router(...)` + hàm thuần `beat_state`, `beat_rows`, `char_list`, `renders`, `media_url`, `char_url`, `sniff_image`, `waveform` |
| `src/vidflow/ui/server.py` | Gắn router, `/media` phục vụ cả project nhanh (`images/`, `out/`) |
| `scripts/seed_quick_demo.py` | Mới: tạo `projects/ui-demo` giả lập để kiểm tra giao diện bằng tay |
| `tests/test_ui_static.py`, `tests/test_ui_quick_jobs.py`, `tests/test_ui_quick.py`, `tests/test_ui_auth.py` | Test |

Kiểm tra tay (mọi task giao diện): `uv run vidflow ui --port 8788 --no-open`, mở http://127.0.0.1:8788, đăng nhập bằng mật khẩu `cat ~/.vidflow/ui_password`. Khi hộp xác nhận hỏi gen trong Google Flow, bấm **Hủy** (không tiêu tín dụng khi kiểm tra). Dừng server bằng Ctrl+C.

---

### Task 1: Phong cách chung — token, phông, khung 3 vùng, bỏ thiên hà (3a) (Model: haiku)

**Files:**
- Modify: `src/vidflow/ui/static/style.css` (viết lại toàn bộ)
- Modify: `src/vidflow/ui/static/index.html` (viết lại toàn bộ)
- Delete: `src/vidflow/ui/static/galaxy.js`
- Modify: `src/vidflow/ui/static/app.js:228-236` (hàm `render`)
- Modify: `src/vidflow/ui/auth.py:18-27` (`LOGIN_HTML`)
- Test: `tests/test_ui_static.py` (mới)

**Interfaces:**
- Produces: các id DOM `homeBtn`, `currentBox`, `projectSel`, `newBtn`, `railNav`, `jobPill`, `main`, `savebar`, `toast`, `newDlg`; hàm JS toàn cục `setCurrent(eyebrow?: string, title?: string, meta?: string)` (không đối số → ẩn ô "video đang mở"); lớp CSS khung `.shell .rail .navlist .navlink(.active) .tag(.warn) .psteps .pdot(.done|.now) .plabel .pmeta .rail-foot .kv .pill(.running|.done|.failed|.stopped) main.app main.app.single .content .panel .assistant .eyebrow .muted .grow`; biến CSS `--page --surface --line --input --btn-line --track --text --muted --muted-2 --primary --secondary --success --success-text --success-bg --error --error-text --error-bg --error-line --warn --warn-bg --warn-line --info-text --info-bg --clip-bg --clip-line --font --mono`.

- [ ] **Step 1: Write the failing tests** — tạo `tests/test_ui_static.py`:

```python
"""Kiểm tra tĩnh giao diện (spec 2026-10-12, Giai đoạn 3): token, phông, không thiên hà/gradient/glow/emoji."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from vidflow.ui import auth
from vidflow.ui.server import STATIC

TOKENS = ("--page:#E3EBE2", "--surface:#F2F6F1", "--line:#CCD8CB", "--input:#EAF1E9", "--btn-line:#B8C7B7",
          "--text:#0E1238", "--muted:#4A4F6E", "--primary:#000080", "--secondary:#0069ba", "--success:#1fba00",
          "--success-text:#157A00", "--error:#C8283E", "--warn:#8A4B00", "--warn-bg:#FDEBD2")
FORBIDDEN = re.compile("[\U0001F000-\U0001FAFF⌀-⏿☀-➿⬀-⯿️]")
ALLOWED = {"✓"}


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_tokens_fonts_and_shell():
    css, html = _read("style.css"), _read("index.html")
    for t in TOKENS:
        assert t in css, t
    assert "family=Be+Vietnam+Pro" in html and "JetBrains+Mono" in html
    for el in ('id="railNav"', 'id="currentBox"', 'id="projectSel"', 'id="jobPill"', 'id="main"', 'action="/logout"',
               'class="shell"'):
        assert el in html, el


def test_no_galaxy_gradient_or_glow():
    css, html = _read("style.css"), _read("index.html")
    assert not (STATIC / "galaxy.js").exists()
    for bad in ("galaxy.js", 'id="stars"', "nebula"):
        assert bad not in html
    for bad in ("gradient", "glow", "nebula", "#stars"):
        assert bad not in css
    assert "gradient" not in auth.LOGIN_HTML


def test_login_page_restyled():
    page = auth.Auth("x").login_page().body.decode()
    assert "#E3EBE2" in page and "Be+Vietnam+Pro" in page and "Mật khẩu" in page
    assert not FORBIDDEN.search(page)


@pytest.mark.skipif(shutil.which("node") is None, reason="cần node để kiểm tra cú pháp JS")
@pytest.mark.parametrize("js", sorted(p.name for p in STATIC.glob("*.js")))
def test_js_syntax(js):
    r = subprocess.run(["node", "--check", str(STATIC / js)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui_static.py -v`
Expected: FAIL — `test_tokens_fonts_and_shell` (thiếu `--page:#E3EBE2`), `test_no_galaxy_gradient_or_glow` (còn `galaxy.js`), `test_login_page_restyled` (thiếu `#E3EBE2`). `test_js_syntax` PASS.

- [ ] **Step 3: Viết lại `src/vidflow/ui/static/style.css`** (thay toàn bộ nội dung):

```css
/* vidflow — giao diện sáng (spec 2026-10-12, Giai đoạn 3). Không nền sao, không chuyển màu, không phát sáng, không emoji. */
:root{
  --page:#E3EBE2;--surface:#F2F6F1;--line:#CCD8CB;--input:#EAF1E9;--btn-line:#B8C7B7;--track:#D7E1D6;
  --text:#0E1238;--muted:#4A4F6E;--muted-2:#5A5F7D;
  --primary:#000080;--primary-hover:#0A0A9E;--secondary:#0069ba;
  --success:#1fba00;--success-text:#157A00;--success-bg:#E4F6DE;
  --error:#C8283E;--error-text:#A51D33;--error-bg:#FCE3E7;--error-line:#F1B9C2;
  --warn:#8A4B00;--warn-bg:#FDEBD2;--warn-line:#E5B66B;
  --info-text:#005A9E;--info-bg:#E1EEF9;--clip-bg:#F2F4FB;--clip-line:#D9DEF2;
  --font:"Be Vietnam Pro","Helvetica Neue",Arial,sans-serif;
  --mono:"JetBrains Mono",Menlo,Consolas,monospace;
  --r:8px;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--page);color:var(--text);font-family:var(--font);font-size:14px;line-height:1.45}
a{color:var(--secondary)}a:hover{color:var(--primary)}
[hidden]{display:none!important}
:focus-visible{outline:2px solid var(--secondary);outline-offset:2px}
.mono,.sid,code,pre{font-family:var(--mono)}
.hint{font-size:12px;color:var(--muted);line-height:1.45}
.mini{font-size:12px;color:var(--muted);margin:0 0 6px}
.muted{color:var(--muted)}
.grow{flex:1}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.row.between{justify-content:space-between}.row.center{justify-content:center}
.eyebrow{font-size:11px;font-weight:600;letter-spacing:.6px;text-transform:uppercase;color:var(--muted-2)}

/* ===== Khung 3 vùng: thanh trái · vùng giữa · khung phải ===== */
.shell{display:grid;grid-template-columns:248px minmax(0,1fr);min-height:100vh}
.rail{position:sticky;top:0;height:100vh;overflow:auto;padding:20px 16px;background:var(--surface);border-right:1px solid var(--line);display:flex;flex-direction:column;gap:18px}
.brand{display:flex;align-items:center;gap:10px;padding:0;min-height:0;border:none;background:none;font-weight:800;font-size:18px;letter-spacing:-.3px;color:var(--text);cursor:pointer}
.current{display:flex;flex-direction:column;gap:4px;padding:12px;border-radius:10px;background:var(--page)}
.current b{font-weight:700;line-height:1.3}
.current .meta{font-family:var(--mono);font-size:12px;color:var(--muted)}
.rail-pick{display:flex;flex-direction:column;gap:8px}
.navlist{display:flex;flex-direction:column;gap:2px;margin-bottom:18px}
.navlink{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;min-height:40px;padding:0 12px;border:none;border-radius:8px;background:transparent;color:var(--text);font-weight:500;text-align:left}
.navlink:hover:not(:disabled){background:var(--page)}
.navlink.active{background:var(--primary);color:#fff;font-weight:600}
.tag{font-size:12px;padding:1px 7px;border-radius:999px;background:var(--track);color:var(--muted);font-weight:500}
.tag.warn{background:var(--warn-bg);color:var(--warn)}
.psteps{display:flex;flex-direction:column;gap:10px}
.psteps ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.psteps li{display:flex;align-items:center;gap:10px}
.pdot{flex:none;width:20px;height:20px;border-radius:50%;display:grid;place-items:center;font-size:11px;font-weight:700;background:var(--track);color:var(--muted)}
.pdot.done{background:var(--success);color:#fff}.pdot.now{background:var(--primary);color:#fff}
.plabel{flex:1;font-weight:500}.psteps li.now .plabel{font-weight:700}.psteps li.todo .plabel{color:var(--muted-2)}
.pmeta{font-family:var(--mono);font-size:12px;color:var(--muted)}
.rail-foot{margin-top:auto;padding-top:14px;border-top:1px solid var(--line);display:flex;flex-direction:column;gap:8px;font-size:13px;color:var(--muted)}
.rail-foot form{margin:0}
.kv{display:flex;justify-content:space-between;align-items:center;gap:8px}
.pill{font-size:12px;font-weight:600;padding:2px 8px;border-radius:999px;background:var(--track);color:var(--muted);text-align:right}
.pill.running{background:var(--info-bg);color:var(--info-text)}
.pill.done{background:var(--success-bg);color:var(--success-text)}
.pill.failed{background:var(--error-bg);color:var(--error-text)}
.pill.stopped{background:var(--warn-bg);color:var(--warn)}
main{min-width:0}
main.home{padding:28px 32px;max-width:1180px}
main.app{display:grid;grid-template-columns:minmax(0,1fr) 360px;align-items:start;min-height:100vh}
main.app.single{grid-template-columns:minmax(0,1fr)}
main.app>.content{padding:20px 24px;min-width:0}
.assistant,.panel{position:sticky;top:0;max-height:100vh;min-height:100vh;overflow:auto;padding:18px 20px;background:var(--surface);border-left:1px solid var(--line)}
@media (max-width:900px){
  .shell{grid-template-columns:1fr}
  .rail{position:static;height:auto;border-right:none;border-bottom:1px solid var(--line)}
  main.app{grid-template-columns:1fr}
  .assistant,.panel{position:static;min-height:0;max-height:none;border-left:none;border-top:1px solid var(--line)}
  main.home,main.app>.content{padding:16px}
}

/* ===== Nút, ô nhập ===== */
button{font:inherit;font-weight:600;min-height:40px;padding:0 14px;border-radius:var(--r);border:1px solid var(--btn-line);background:var(--surface);color:var(--text);cursor:pointer}
button:hover:not(:disabled){border-color:var(--secondary)}
button.primary{border:none;background:var(--primary);color:#fff}
button.primary:hover:not(:disabled){background:var(--primary-hover)}
button.secondary{border:none;background:var(--secondary);color:#fff}
button.ok{border:none;background:var(--success-text);color:#fff}
button.danger{border-color:var(--error-line);background:#FFF4F5;color:var(--error-text)}
button.small{min-height:32px;padding:0 10px;font-size:12px}
button.big{min-height:48px;padding:0 24px;font-size:16px}
button.wide-btn{width:100%;margin-top:10px}
button:disabled{opacity:.45;cursor:not-allowed}
input[type=text],input[type=number],input[type=password],select,textarea{font:inherit;font-size:14px;width:100%;min-height:40px;padding:8px 10px;border-radius:var(--r);border:1px solid var(--btn-line);background:var(--input);color:var(--text)}
textarea{min-height:56px;resize:vertical;line-height:1.5}
input::placeholder,textarea::placeholder{color:#7A7F9A}
input:focus,select:focus,textarea:focus{outline:2px solid var(--secondary);outline-offset:0;border-color:var(--secondary)}
input[type=checkbox],input[type=range]{accent-color:var(--primary)}
input[type=checkbox]{width:16px;height:16px}
label.f,div.f{display:flex;flex-direction:column;gap:5px;font-size:12px;color:var(--muted)}
.flabel{display:flex;align-items:center;gap:6px;color:var(--text);font-size:13px;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px 16px}
.grid .wide{grid-column:1/-1}
.checks{display:flex;flex-wrap:wrap;gap:8px 16px}
.checks label,label.checks{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--text)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:2px}.chips.col{flex-direction:column;align-items:stretch}
.chip{min-height:28px;font-size:12px;font-weight:500;padding:4px 10px;border-radius:999px;border:1px dashed var(--btn-line);background:var(--surface);color:var(--text);text-align:left;white-space:normal}
.chip:hover:not(:disabled){border-style:solid}
.spark{min-height:24px;padding:0 8px;font-size:11px;border-radius:999px;border:1px solid var(--btn-line);background:var(--input);color:var(--secondary)}

/* ===== Thẻ, nhãn ===== */
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
.card h3{margin:0 0 12px;font-size:15px;font-weight:700}
.card.warn{border-color:var(--warn-line);background:var(--warn-bg)}.card.warn li{font-size:13px;color:var(--warn)}
.badge{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px;background:var(--track);color:var(--muted)}
.badge.ok{background:var(--success-bg);color:var(--success-text)}
.badge.err{background:var(--error-bg);color:var(--error-text)}
.badge.stale,.badge.warn{background:var(--warn-bg);color:var(--warn)}
.badge.info{background:var(--info-bg);color:var(--info-text)}
details{border-top:1px solid var(--line);padding:10px 0}
details summary{cursor:pointer;color:var(--primary);font-weight:600;margin-bottom:8px}
.prompt{background:var(--input);border:1px solid var(--line);border-radius:var(--r);padding:10px;white-space:pre-wrap;font-size:13px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:7px;text-align:left}
th{color:var(--muted);font-weight:600}
pre.log{background:var(--text);color:#E6E8F5;padding:12px;border-radius:10px;max-height:340px;overflow:auto;white-space:pre-wrap;font-size:12px}
.empty{min-height:60vh;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--muted);font-size:15px}
.savebar{position:sticky;bottom:0;padding:10px 18px;display:flex;gap:10px;align-items:center;justify-content:flex-end;background:var(--surface);border-top:1px solid var(--line);z-index:5}
.dirty{color:var(--warn);font-weight:700}
.toast{position:fixed;right:18px;bottom:70px;padding:12px 16px;border-radius:10px;display:none;max-width:440px;z-index:20;background:var(--text);color:#fff;box-shadow:0 8px 24px rgba(14,18,56,.2)}
.toast.err{background:var(--error)}
dialog{border:none;border-radius:16px;padding:24px;width:min(600px,94vw);background:var(--surface);color:var(--text);box-shadow:0 20px 50px rgba(14,18,56,.18)}
dialog::backdrop{background:rgba(14,18,56,.35)}
dialog h3{margin:0 0 6px;font-size:20px;font-weight:800}

/* ===== Quy trình đầy đủ (kịch bản · cảnh · khung · prompt · kiểm duyệt) ===== */
.ptitle{margin:0 0 14px;font-size:22px;font-weight:800;letter-spacing:-.4px}
.side-title{font-size:11px;font-weight:600;letter-spacing:.6px;text-transform:uppercase;color:var(--muted-2);margin-bottom:10px}
.stepper{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:2px}
.stp{display:flex;align-items:center;gap:10px;padding:8px;border-radius:8px;cursor:pointer}
.stp:hover{background:var(--page)}
.stp.active{background:var(--primary);color:#fff}
.stp .dot{flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:11px;font-weight:700;background:var(--track);color:var(--muted)}
.stp.done .dot{background:var(--success);color:#fff}
.stp.current:not(.active) .dot{background:var(--primary);color:#fff}
.stp-t{font-size:13px;line-height:1.3}
.now{margin-left:auto;font-size:10px;font-weight:700;padding:2px 7px;border-radius:999px;background:var(--info-bg);color:var(--info-text)}
.next{margin-top:14px;padding:12px;border-radius:10px;background:var(--page);border:1px solid var(--line)}
.next b{color:var(--primary)}.next p{font-size:12px;margin:6px 0 10px}
.guide{border-radius:12px;padding:16px;margin-bottom:16px;background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--primary)}
.guide-title{font-size:17px;font-weight:800;margin-bottom:10px}
.guide-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:12px}
.guide-grid b{font-size:11px;letter-spacing:.6px;text-transform:uppercase;color:var(--muted-2)}
.guide-grid p{margin:4px 0 0;font-size:13px;line-height:1.45}.guide-grid .ex{color:var(--secondary)}
.stepnav{display:flex;justify-content:space-between;gap:10px;margin:8px 0 30px}
.as-card{padding:12px;border-radius:10px;background:var(--page);border:1px solid var(--line);margin-bottom:12px}
.as-field{font-weight:700;display:flex;gap:8px;align-items:center;justify-content:space-between;margin-bottom:6px}
.as-sub{font-size:11px;font-weight:600;letter-spacing:.6px;text-transform:uppercase;color:var(--muted-2);margin:10px 0 6px}
.sugg{display:flex;flex-direction:column;gap:6px;margin-bottom:10px;padding:8px;border-radius:10px;background:var(--surface);border:1px solid var(--line)}
.sugg button{align-self:flex-end}
.shimmer div{height:44px;border-radius:8px;margin-top:8px;background:var(--track)}
.assistant pre.log{max-height:220px}
.scene{border-left:4px solid var(--line)}
.scene.approved{border-left-color:var(--success)}
.scene.locked{background:var(--page)}
.scene-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.scene-head .sid{font-weight:700;font-size:16px}
.scene-head select{width:auto}
.sid{font-weight:600;color:var(--primary)}
.item summary{font-size:14px}.empty-card{text-align:center;color:var(--muted)}
.promptbox{margin-top:10px;padding:12px;border-radius:10px;background:var(--page);border:1px solid var(--line)}
.media{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start}
.media figure{margin:0;text-align:center;font-size:12px;color:var(--muted)}
.media video{width:170px;border-radius:8px;background:#000;border:1px solid var(--line)}
.media figure.picked video{outline:3px solid var(--success);outline-offset:1px}
.refs{display:flex;gap:14px;flex-wrap:wrap}.refs figure{margin:0;text-align:center;font-size:12px;color:var(--muted)}
.refs img{height:170px;border-radius:8px;border:1px solid var(--line)}
.noimg{width:120px;height:170px;border-radius:8px;border:1px dashed var(--btn-line);display:grid;place-items:center;font-size:12px;color:var(--muted)}
.modebox{margin-top:10px;padding:12px;border-radius:10px;background:var(--page);border:1px dashed var(--btn-line)}
.modebox select{width:auto}
.frames{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
.frame{padding:10px;border-radius:10px;background:var(--surface);border:1px solid var(--line);display:flex;flex-direction:column;gap:6px}
.frame .thumb{width:100%;max-height:200px;object-fit:cover;border-radius:8px}
.frame-prompt{padding:10px;border-top:1px solid var(--line)}
.issues{margin:4px 0 8px;color:var(--warn);font-size:12px}
.framegrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-top:10px}
.fcol{padding:8px;border-radius:10px;background:var(--surface);border:1px solid var(--line)}
.imgs{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.imgs figure{margin:0;text-align:center;font-size:11px}
.imgs img{width:80px;height:120px;object-fit:cover;border-radius:6px;border:1px solid var(--line)}
.imgs figure.picked img{outline:3px solid var(--success);outline-offset:1px}

/* ===== Trang chủ ===== */
.hero{padding:10px 0}
.hero-title{font-size:30px;font-weight:800;letter-spacing:-.6px;margin:6px 0 10px}
.hero-sub{max-width:760px;margin:0 0 22px;color:var(--muted);font-size:15px;line-height:1.6}
.flow7{display:grid;grid-template-columns:repeat(7,1fr);gap:10px;margin:0 0 26px}
.f7{padding:12px 8px;border-radius:10px;background:var(--surface);border:1px solid var(--line);text-align:center}
.f7i{font-family:var(--mono);font-weight:600;color:var(--primary)}.f7n{font-size:12px;margin-top:4px}
.sec{margin:26px 0 12px;font-size:15px;font-weight:700}
.tpls{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.tpl{display:block;min-height:0;text-align:left;padding:16px;border-radius:12px;background:var(--surface);border:1px solid var(--line);font-weight:400;white-space:normal}
.tpl b{font-size:15px;font-weight:700}.tpl p{font-size:12px;color:var(--muted);margin:6px 0 0;line-height:1.45}
@media (max-width:1200px){.guide-grid{grid-template-columns:1fr}}
@media (max-width:900px){.flow7{grid-template-columns:repeat(2,1fr)}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
```

- [ ] **Step 4: Viết lại `src/vidflow/ui/static/index.html`** (thay toàn bộ nội dung; giữ nguyên tên các ô của form `newForm`):

```html
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>vidflow</title>
<meta name="color-scheme" content="light">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap">
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
<div class="shell">
  <nav class="rail" aria-label="Điều hướng">
    <button class="brand" id="homeBtn" type="button" title="Trang chủ">
      <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true"><rect width="28" height="28" rx="7" fill="#000080"/><path d="M8 9l6 10 6-10" fill="none" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="21" cy="20" r="2.6" fill="#1fba00"/></svg>
      <span>vidflow</span>
    </button>
    <div class="current" id="currentBox" hidden></div>
    <div class="rail-pick">
      <select id="projectSel" aria-label="Chọn video"></select>
      <button id="newBtn" type="button">Video mới</button>
    </div>
    <div id="railNav"></div>
    <div class="rail-foot">
      <span class="kv">Việc nền <span id="jobPill" class="pill">Rảnh</span></span>
      <form method="post" action="/logout"><button type="submit" class="small">Đăng xuất</button></form>
    </div>
  </nav>
  <main id="main"><div class="empty">Đang tải…</div></main>
</div>
<div class="savebar" id="savebar" hidden>
  <span id="dirtyMark"></span>
  <button id="reloadBtn">Hoàn tác thay đổi</button>
  <button id="saveBtn" class="primary">Lưu (Cmd+S)</button>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>

<dialog id="newDlg">
  <form method="dialog" id="newForm">
    <h3>Video chi tiết mới</h3>
    <p class="hint">Chỉ cần ý tưởng + model. AI sẽ viết phần còn lại, bạn duyệt từng bước.</p>
    <div class="grid">
      <label class="f wide"><span class="flabel">Ý tưởng (1–2 câu: chuyện gì, ai, cảm xúc, dài bao lâu)</span>
        <textarea name="idea" required rows="3" placeholder="vd: video hài 20s về cà phê sáng, nhân vật đeo kính tóc rẽ ngôi"></textarea>
        <span class="hint">Ví dụ — bấm để dùng:</span><div class="chips" id="ideaEx"></div></label>
      <label class="f"><span class="flabel">Tựa</span><input type="text" name="title" required></label>
      <label class="f"><span class="flabel">Tên thư mục (không dấu)</span><input type="text" name="name" required pattern="[a-z0-9][a-z0-9_-]*" placeholder="cafe-sang-2"></label>
      <label class="f"><span class="flabel">Loại hình ảnh</span><select name="style_type"><option value="anim_3d">Hoạt hình 3D</option><option value="anim_2d">Hoạt hình 2D</option><option value="live_action">Người thật</option><option value="ugc">Quay điện thoại (UGC)</option></select></label>
      <label class="f"><span class="flabel">Tỉ lệ</span><select name="aspect"><option>9:16</option><option>16:9</option></select></label>
      <label class="f"><span class="flabel">Model video (Google Flow) — bắt buộc</span><select name="video_model" required><option value="">— chọn —</option><option>Veo 3.1 Lite</option><option>Veo 3.1 Fast</option><option>Veo 3.1 Quality</option><option>Omni 1.1 Flash</option></select></label>
      <label class="f"><span class="flabel">Độ phân giải tải về</span><select name="resolution"><option>720p</option><option>1080p</option></select></label>
      <div class="checks wide"><label><input type="checkbox" name="start" checked> Cho AI viết kịch bản chi tiết ngay sau khi tạo</label></div>
    </div>
    <div class="row" style="justify-content:flex-end;margin-top:14px">
      <button value="cancel" formnovalidate>Hủy</button><button value="ok" class="primary">Tạo video</button>
    </div>
  </form>
</dialog>
<script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 5: Xóa nền thiên hà**

Run: `git rm src/vidflow/ui/static/galaxy.js`

- [ ] **Step 6: Vẽ thanh trái vào `#railNav`** — trong `src/vidflow/ui/static/app.js`, thay nguyên hàm `render()` (dòng 228–236) bằng:

```js
function setCurrent(eyebrow, title, meta) {
  const box = document.getElementById("currentBox");
  box.hidden = !title;
  box.replaceChildren(h("span", { class: "eyebrow" }, eyebrow || ""), h("b", {}, title || ""), h("span", { class: "meta" }, meta || ""));
}
function render() {
  document.getElementById("savebar").hidden = !S.name;
  const shell = document.getElementById("main"), nav = document.getElementById("railNav");
  if (!S.name || !S.data) { shell.className = "home"; nav.replaceChildren(); setCurrent(); shell.replaceChildren(renderHome()); return; }
  shell.className = "app";
  const step = STEPS.find(s => s.id === S.step) || STEPS[0];
  const view = { idea: vIdea, cast: vCast, story: vStory, shots: vShots, voice: vVoice, video: vVideo, build: vBuild }[step.id]();
  const sc = S.data.script;
  setCurrent("Video chi tiết", sc.title, `${(sc.scenes || []).length} cảnh · ${sc.aspect}`);
  nav.replaceChildren(renderSidebar());
  shell.replaceChildren(h("section", { class: "content" }, h("h2", { class: "ptitle" }, sc.title), guide(step), view, stepNav(step)), renderAssistant());
}
```

- [ ] **Step 7: Trang đăng nhập theo bảng màu mới** — trong `src/vidflow/ui/auth.py` thay toàn bộ hằng `LOGIN_HTML` bằng:

```python
LOGIN_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>vidflow · Đăng nhập</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;800&display=swap"><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:"Be Vietnam Pro","Helvetica Neue",Arial,sans-serif;color:#0E1238;background:#E3EBE2}
form{width:min(360px,90vw);padding:28px;border-radius:16px;background:#F2F6F1;border:1px solid #CCD8CB}
h1{margin:0 0 18px;font-size:22px;font-weight:800;letter-spacing:-.4px}
label{font-size:13px;font-weight:600;color:#4A4F6E}
input{width:100%;box-sizing:border-box;margin-top:6px;min-height:44px;padding:0 12px;border-radius:8px;border:1px solid #B8C7B7;background:#EAF1E9;color:#0E1238;font:inherit;font-size:15px}
input:focus{outline:2px solid #0069ba;outline-offset:1px}
button{margin-top:14px;width:100%;min-height:44px;border:none;border-radius:8px;color:#fff;font:inherit;font-weight:700;font-size:15px;cursor:pointer;background:#000080}
p{color:#C8283E;font-size:13px;min-height:1em}</style></head><body>
<form method="post" action="/login"><h1>vidflow</h1>
<label>Mật khẩu<input type="password" name="password" autofocus autocomplete="current-password"></label>
<p>{msg}</p><button>Đăng nhập</button></form></body></html>"""
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_static.py tests/test_ui_auth.py tests/test_ui_api.py -v`
Expected: PASS (mọi test).

- [ ] **Step 9: Kiểm tra tay**

Run: `uv run vidflow ui --port 8788 --no-open`, đăng nhập. Thấy: trang đăng nhập nền xanh xám nhạt `#E3EBE2`, nút xanh navy; sau đăng nhập không còn nền sao; thanh trái có logo vidflow, ô chọn video, nút "Video mới", "Việc nền: Rảnh", nút "Đăng xuất". Chọn một project chi tiết sẵn có trong `projects/` (ví dụ `cafe-sang`): ô "Video chi tiết" hiện tựa + số cảnh; danh sách 7 bước nằm trong thanh trái; vùng giữa là nội dung bước; khung phải là Trợ lý AI. Bấm qua đủ 7 bước, mỗi bước hiển thị như trước (còn emoji ở nút — Task 2 xử lý). Thu cửa sổ còn ~800px: thanh trái, vùng giữa, khung phải xếp dọc, không cuộn ngang.

- [ ] **Step 10: Commit**

```bash
git add src/vidflow/ui/static/style.css src/vidflow/ui/static/index.html src/vidflow/ui/static/app.js src/vidflow/ui/auth.py tests/test_ui_static.py
git commit -m "feat(ui): giao diện sáng — token màu, phông, khung 3 vùng, bỏ nền thiên hà"
```

---

### Task 2: Bỏ emoji, trạng thái bằng chữ trong `app.js` (3a) (Model: haiku)

**Files:**
- Modify: `src/vidflow/ui/static/app.js` (nhiều dòng, bằng script thay thế có kiểm tra)
- Test: `tests/test_ui_static.py`

**Interfaces:**
- Consumes: `setCurrent` (Task 1).
- Produces: chữ trạng thái việc nền trong `#jobPill`: `Đang chạy: <nhãn>` / `Xong: <nhãn>` / `Lỗi: <nhãn>` / `Đã dừng: <nhãn>` / `Rảnh`; trạng thái `stopped` được Task 3 thêm phía server.

- [ ] **Step 1: Write the failing test** — thêm vào cuối `tests/test_ui_static.py`:

```python
def test_no_emoji_in_ui():
    """Mọi file tĩnh (html/js/css, kể cả quick.js về sau) và trang đăng nhập: không emoji/dingbat, trừ dấu ✓."""
    files = {p.name: p.read_text(encoding="utf-8") for p in STATIC.iterdir() if p.suffix in (".html", ".js", ".css")}
    files["auth.LOGIN_HTML"] = auth.LOGIN_HTML
    bad = {name: sorted({c for c in FORBIDDEN.findall(text) if c not in ALLOWED}) for name, text in files.items()}
    assert {k: v for k, v in bad.items() if v} == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui_static.py::test_no_emoji_in_ui -v`
Expected: FAIL — `{'app.js': ['⚙', '⛔', '✂', '✅', '✕', '✗', '✨', ...]}`.

- [ ] **Step 3: Áp thay thế** — chạy script một lần (mỗi chuỗi cũ phải xuất hiện đúng 1 lần, nếu không script dừng):

```bash
uv run python - <<'PY'
import re
from pathlib import Path

p = Path("src/vidflow/ui/static/app.js")
s = p.read_text(encoding="utf-8")
EXACT = [
    ('suggest(); } }, "✨") : null)', 'suggest(); } }, "AI gợi ý") : null)'),
    ('markDirty(); render(); } }, "✕"))),', 'markDirty(); render(); } }, "Xóa"))),'),
    ('checkbox("🔒", f, "locked")', 'checkbox("Khóa", f, "locked")'),
    ('pill.textContent = j.state === "running" ? `⚙️ ${j.label}…` : j.state === "done" ? `✓ ${j.label}` : '
     'j.state === "failed" ? `✗ ${j.label}` : "Rảnh";',
     'pill.textContent = j.state === "running" ? `Đang chạy: ${j.label}` : j.state === "done" ? `Xong: ${j.label}` : '
     'j.state === "failed" ? `Lỗi: ${j.label}` : j.state === "stopped" ? `Đã dừng: ${j.label}` : "Rảnh";'),
    ('`${step.icon} ${step.title}`', 'step.title'),
    ('`${cur.icon} ${cur.title}: ${cur.need}`', '`${cur.title}: ${cur.need}`'),
    ('h("div", { class: "f7i" }, s.icon)', 'h("div", { class: "f7i" }, String(i + 1))'),
    ('h("div", { class: "tpl-i" }, t.icon), ', ''),
    ('h("div", { class: "tpl-i" }, "🎞️"), ', ''),
    ('"hoặc tự điền các ô bên dưới — bấm ✨ ở từng ô để AI gợi ý"', '"hoặc tự điền các ô bên dưới — bấm “AI gợi ý” ở từng ô"'),
    ('(bỏ qua phần đã khóa 🔒)', '(bỏ qua phần đã khóa)'),
    ('// ô nhập có: nhãn, gợi ý, ví dụ bấm-điền, nút ✨ AI gợi ý;', '// ô nhập có: nhãn, gợi ý, ví dụ bấm-điền, nút AI gợi ý;'),
]
for old, new in EXACT:
    assert s.count(old) == 1, (old, s.count(old))
    s = s.replace(old, new)
s = re.sub(r'\s*icon: "[^"]*",', "", s)  # bỏ trường icon (emoji) của STEPS và TEMPLATES
EMOJI = re.compile("[\U0001F000-\U0001FAFF⌀-⏿☀-✒✔-➿⬀-⯿]️? ?")
s = EMOJI.sub("", s).replace("️", "")
p.write_text(s, encoding="utf-8")
print("ok")
PY
```

Expected: in `ok`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_static.py -v`
Expected: PASS (gồm `test_no_emoji_in_ui` và `test_js_syntax[app.js]`).

- [ ] **Step 5: Kiểm tra tay**

Run: `uv run vidflow ui --port 8788 --no-open`, đăng nhập, mở project chi tiết. Thấy: không còn biểu tượng emoji ở tiêu đề bước, nút ("AI viết toàn bộ kịch bản chi tiết", "Kiểm duyệt prompt (agent độc lập)", "Gen video trong Flow"…), thẻ mẫu trang chủ, trợ lý AI; nút gợi ý cạnh mỗi ô ghi "AI gợi ý" và vẫn hoạt động (bấm → khung phải hiện "Gợi ý 3 phương án"); ô khung ảnh có nút "Xóa" và ô "Khóa"; trang chủ: dãy 7 bước đánh số 1–7. Bấm "Hoàn tác thay đổi" sau khi sửa một ô: dòng "● Có thay đổi chưa lưu" biến mất.

- [ ] **Step 6: Commit**

```bash
git add src/vidflow/ui/static/app.js tests/test_ui_static.py
git commit -m "feat(ui): bỏ emoji, trạng thái việc nền bằng chữ"
```

---

### Task 3: `JobRunner` — nhãn, dừng việc, lệnh việc nền quy trình nhanh (Model: haiku)

**Files:**
- Create: `src/vidflow/ui/quick_jobs.py`
- Modify: `src/vidflow/ui/jobs.py` (import, `Job`, `JobRunner`)
- Test: `tests/test_ui_quick_jobs.py` (mới)

**Interfaces:**
- Consumes: `vidflow.quick.jobs.QUICK_KINDS`, `LABELS`, `claude_cmd(kind, root, preset, provider=None)` (Giai đoạn 1b); `vidflow.quick.model.load_quick`, `require_beats`; `vidflow.quick.preset.load_preset`.
- Produces:
  - `quick_jobs.CLI_QUICK = ("voice", "render", "build")`, `QUICK_UI_KINDS = ("ideas", "script", "prompts", "sheets", "flow", "clips", "voice", "render", "build")`, `QUICK_LABELS: dict[str, str]` (`"voice": "Tạo giọng đọc (Gemini)"`, `"render": "Xuất MP4 (Remotion)"`, `"build": "Dựng draft CapCut"` + nhãn Claude của Giai đoạn 1).
  - `option_args(kind: str, options: dict | None) -> list[str]` (ValueError khi khóa/giá trị lạ).
  - `PROVIDERS = ("flow", "gemini", "aistudio")`, `PROVIDER_KINDS = ("sheets", "flow", "clips")`, `check_provider(kind: str, provider: str | None) -> None` (ValueError).
  - `build_quick_cmd(kind: str, root: Path, instruction: str = "", options: dict | None = None, provider: str | None = None) -> list[str]`.
  - `check_quick_job(kind: str, root: Path, options: dict | None = None, provider: str | None = None) -> None` (ValueError: loại việc/tùy chọn/nguồn sai; VidflowError: điều kiện chưa đủ).
  - `Job.label: str`, `Job.stopped: bool`, `Job.provider: str`, `Job.state ∈ {"running", "done", "failed", "stopped"}`; `Job.to_dict()` thêm `provider` và `quota_exhausted: bool` (đã kết thúc, không bị dừng tay, và mã 3 hoặc log có "hết lượt ở").
  - `JobRunner.quick_command_for(kind, project_root, instruction="", options=None, provider=None) -> list[str]` (test ghi đè được).
  - `JobRunner.start(kind, project, project_root, scenes=None, instruction="", *, quick=False, options=None, provider=None) -> Job`.
  - `JobRunner.stop() -> bool`.

- [ ] **Step 1: Write the failing tests** — tạo `tests/test_ui_quick_jobs.py`:

```python
import sys

import pytest

from vidflow.errors import VidflowError
from vidflow.quick.model import create_quick
from vidflow.ui.jobs import JobRunner
from vidflow.ui.quick_jobs import QUICK_UI_KINDS, build_quick_cmd, check_quick_job, option_args


def test_kinds():
    assert QUICK_UI_KINDS == ("ideas", "script", "prompts", "sheets", "flow", "clips", "voice", "render", "build")


def test_cli_kinds(qroot):
    assert build_quick_cmd("voice", qroot) == [sys.executable, "-m", "vidflow", "quick", "voice", "-p", str(qroot)]
    assert build_quick_cmd("build", qroot, options={"zoom": False, "subtitles": True})[-2:] == ["--no-zoom", "--subtitles"]


def test_render_options_become_flags(qroot):
    cmd = build_quick_cmd("render", qroot, options={"music": False, "resolution": "720p", "zoom": False, "transition": "cut",
                                                    "clip_fit": "speed", "subtitles": True, "clip_audio": True, "logo": False})
    assert cmd[3:7] == ["quick", "render", "-p", str(qroot)]
    assert cmd[7:] == ["--resolution", "720p", "--transition", "cut", "--clip-fit", "speed",
                       "--no-zoom", "--subtitles", "--clip-audio", "--no-logo", "--no-music"]


@pytest.mark.parametrize("kind,opts", [
    ("render", {"resolution": "4k"}),
    ("render", {"resolution": "1080p; rm -rf /"}),
    ("render", {"zoom": "yes"}),
    ("render", {"output": "/tmp/x.mp4"}),
    ("build", {"music": True}),
    ("flow", {"zoom": True}),
])
def test_bad_options_rejected(kind, opts):
    with pytest.raises(ValueError):
        option_args(kind, opts)


def test_claude_kinds(qroot):
    flow = build_quick_cmd("flow", qroot)
    assert flow[0] == "claude" and "--chrome" in flow and "flow-operator.md" in flow[-1]
    ideas = build_quick_cmd("ideas", qroot, instruction="chủ đề tổ tiên")
    assert "--chrome" not in ideas and "quick set-ideas" in ideas[-1]
    assert ideas[-1].endswith('"chủ đề tổ tiên".')
    assert build_quick_cmd("voice", qroot, instruction="bỏ qua") == build_quick_cmd("voice", qroot)


def test_check_quick_job(qroot, tmp_path):
    with pytest.raises(VidflowError, match="ý tưởng"):
        check_quick_job("script", qroot)
    with pytest.raises(VidflowError, match="model clip"):
        check_quick_job("clips", qroot)
    with pytest.raises(ValueError):
        check_quick_job("gen", qroot)
    with pytest.raises(ValueError):
        check_quick_job("render", qroot, {"resolution": "4k"})
    check_quick_job("voice", qroot)
    create_quick(tmp_path / "moi", preset="doodle-giai-ma")
    with pytest.raises(VidflowError, match="beats.json"):
        check_quick_job("voice", tmp_path / "moi")


class SleepRunner(JobRunner):
    def quick_command_for(self, kind, project_root, instruction="", options=None, provider=None):
        return [sys.executable, "-c", "import time; time.sleep(5)"]


def test_runner_quick_label_busy_and_stop(tmp_path):
    r = SleepRunner()
    job = r.start("flow", "vid", tmp_path / "vid", quick=True)
    assert job.to_dict(tail=0)["label"] == "Gen ảnh mốc trong Google Flow"
    with pytest.raises(RuntimeError, match="Gen ảnh mốc trong Google Flow"):
        r.start("voice", "vid", tmp_path / "vid", quick=True)
    assert r.stop() is True
    assert job.state == "stopped" and r.busy() is False
    assert r.stop() is False
    r.start("voice", "vid", tmp_path / "vid", quick=True)  # chạy được việc mới sau khi dừng
    assert r.current.to_dict(tail=0)["label"] == "Tạo giọng đọc (Gemini)"
    r.stop()


def test_provider_override_passed_and_validated(qroot, monkeypatch):
    import vidflow.quick.jobs as qj

    seen = {}

    def fake_claude_cmd(kind, root, preset, provider=None):
        seen[kind] = provider
        return ["claude", "-p", "task"]

    monkeypatch.setattr(qj, "claude_cmd", fake_claude_cmd)
    build_quick_cmd("flow", qroot, provider="gemini")
    build_quick_cmd("clips", qroot)
    build_quick_cmd("sheets", qroot, provider="aistudio")
    assert seen == {"flow": "gemini", "clips": None, "sheets": "aistudio"}
    for kind, prov in (("voice", "gemini"), ("ideas", "flow"), ("flow", "midjourney"), ("flow", "")):
        with pytest.raises(ValueError):
            build_quick_cmd(kind, qroot, provider=prov)
        with pytest.raises(ValueError):
            check_quick_job(kind, qroot, provider=prov)


class CmdRunner(JobRunner):
    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def quick_command_for(self, kind, project_root, instruction="", options=None, provider=None):
        return self.cmd


@pytest.mark.parametrize("code,want", [
    ("import sys; sys.exit(3)", True),
    ("print('Báo cáo: hết lượt ở gemini, đã gen 12 ảnh')", True),
    ("print('xong')", False),
    ("import sys; sys.exit(1)", False),
])
def test_quota_exhausted_flag(tmp_path, code, want):
    r = CmdRunner([sys.executable, "-c", code])
    job = r.start("flow", "vid", tmp_path / "vid", quick=True, provider="gemini")
    job.proc.wait()
    d = job.to_dict()
    assert d["quota_exhausted"] is want and d["provider"] == "gemini"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui_quick_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vidflow.ui.quick_jobs'`.

- [ ] **Step 3: Tạo `src/vidflow/ui/quick_jobs.py`**:

```python
"""Lệnh việc nền của quy trình nhanh trên UI: job Claude (vidflow.quick.jobs) và CLI `vidflow quick voice|render|build`."""
from __future__ import annotations

import sys
from pathlib import Path

from vidflow.errors import VidflowError
from vidflow.quick import jobs as qjobs
from vidflow.quick.model import load_quick, require_beats
from vidflow.quick.preset import load_preset

CLI_QUICK = ("voice", "render", "build")
QUICK_UI_KINDS = qjobs.QUICK_KINDS + CLI_QUICK
QUICK_LABELS = {**qjobs.LABELS, "voice": "Tạo giọng đọc (Gemini)", "render": "Xuất MP4 (Remotion)",
                "build": "Dựng draft CapCut"}
RENDER_CHOICES = {"resolution": ("1080p", "720p"), "transition": ("scene", "cut", "fade"), "clip_fit": ("trim", "speed")}
RENDER_FLAGS = ("zoom", "subtitles", "clip_audio", "logo", "music")
BUILD_FLAGS = ("zoom", "subtitles")
NEEDS_BEATS = ("voice", "prompts", "flow", "clips", "render", "build")
PROVIDERS = ("flow", "gemini", "aistudio")
PROVIDER_KINDS = ("sheets", "flow", "clips")


def check_provider(kind: str, provider: str | None) -> None:
    """Ghi đè nguồn gen một lần (None = theo cài đặt video). Chỉ cho việc gen sheet/ảnh/clip."""
    if provider is None:
        return
    if kind not in PROVIDER_KINDS:
        raise ValueError(f"Việc '{kind}' không chọn nguồn gen.")
    if provider not in PROVIDERS:
        raise ValueError(f"Nguồn gen chỉ nhận: {', '.join(PROVIDERS)}")


def option_args(kind: str, options: dict | None) -> list[str]:
    """Đổi tùy chọn UI thành cờ CLI — chỉ nhận khóa/giá trị trong danh sách trắng. Sai → ValueError."""
    options = dict(options or {})
    choices = RENDER_CHOICES if kind == "render" else {}
    flags = RENDER_FLAGS if kind == "render" else BUILD_FLAGS if kind == "build" else ()
    unknown = sorted(set(options) - set(choices) - set(flags))
    if unknown:
        raise ValueError(f"Tùy chọn không hỗ trợ cho '{kind}': {', '.join(unknown)}")
    args: list[str] = []
    for key, allowed in choices.items():
        if key in options:
            if options[key] not in allowed:
                raise ValueError(f"{key} chỉ nhận: {', '.join(allowed)}")
            args += [f"--{key.replace('_', '-')}", options[key]]
    for key in flags:
        if key in options:
            if not isinstance(options[key], bool):
                raise ValueError(f"{key} phải là true/false")
            name = key.replace("_", "-")
            args.append(f"--{name}" if options[key] else f"--no-{name}")
    return args


def build_quick_cmd(kind: str, root: Path, instruction: str = "", options: dict | None = None,
                    provider: str | None = None) -> list[str]:
    root = Path(root)
    check_provider(kind, provider)
    if kind in CLI_QUICK:
        return [sys.executable, "-m", "vidflow", "quick", kind, "-p", str(root)] + option_args(kind, options)
    if kind in qjobs.QUICK_KINDS:
        option_args(kind, options)  # việc Claude không nhận tùy chọn nào
        cmd = qjobs.claude_cmd(kind, root, load_preset(load_quick(root).preset), provider=provider)
        if instruction.strip():
            cmd[-1] += f' Ghi chú của người dùng (ưu tiên làm theo): "{instruction.strip()}".'
        return cmd
    raise ValueError(f"Không hỗ trợ việc '{kind}'")


def check_quick_job(kind: str, root: Path, options: dict | None = None, provider: str | None = None) -> None:
    """Kiểm tra trước khi chạy (giống CLI). Loại việc/tùy chọn/nguồn sai → ValueError; điều kiện chưa đủ → VidflowError."""
    if kind not in QUICK_UI_KINDS:
        raise ValueError(f"Việc không hỗ trợ: {kind}")
    option_args(kind, options)
    check_provider(kind, provider)
    q = load_quick(root)
    if kind == "script" and not q.picked_idea():
        raise VidflowError("Chưa chọn ý tưởng — chọn một ý tưởng trước khi viết kịch bản.")
    if kind in NEEDS_BEATS:
        require_beats(root)
    if kind == "clips" and not q.flow.video_model:
        raise VidflowError("Chưa chọn model clip — chọn trong Cài đặt video.")
```

- [ ] **Step 4: Sửa `src/vidflow/ui/jobs.py`**

Thêm import sau `from pathlib import Path`:

```python
from vidflow.ui.quick_jobs import QUICK_LABELS, build_quick_cmd
```

Thay nguyên lớp `Job` và `JobRunner` bằng:

```python
@dataclass
class Job:
    kind: str
    project: str
    log_path: Path
    proc: subprocess.Popen
    started_at: str
    scenes: list[str] | None = None
    _log_file: object = field(default=None, repr=False)
    label: str = ""
    stopped: bool = False
    provider: str = ""  # nguồn gen thực dùng (flow | gemini | aistudio) — chỉ việc sheets/flow/clips

    @property
    def state(self) -> str:
        rc = self.proc.poll()
        if rc is None:
            return "running"
        if self.stopped:
            return "stopped"
        return "done" if rc == 0 else "failed"

    def to_dict(self, tail: int = 20000) -> dict:
        text = self.log_path.read_text(encoding="utf-8", errors="replace") if self.log_path.exists() else ""
        rc = self.proc.poll()
        exhausted = rc is not None and not self.stopped and (rc == 3 or "hết lượt ở" in text[-4000:])
        return {"kind": self.kind, "label": self.label or LABELS.get(self.kind, self.kind), "project": self.project,
                "state": self.state, "returncode": rc, "started_at": self.started_at,
                "scenes": self.scenes, "log": text[-tail:], "provider": self.provider, "quota_exhausted": exhausted}


class JobRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self.current: Job | None = None

    def command_for(self, kind: str, project_root: Path, scenes: list[str] | None, instruction: str = "") -> list[str]:
        return build_job_cmd(kind, project_root, scenes, instruction)

    def quick_command_for(self, kind: str, project_root: Path, instruction: str = "",
                          options: dict | None = None, provider: str | None = None) -> list[str]:
        return build_quick_cmd(kind, project_root, instruction, options, provider)

    def busy(self) -> bool:
        return self.current is not None and self.current.state == "running"

    def start(self, kind: str, project: str, project_root: Path, scenes: list[str] | None = None,
              instruction: str = "", *, quick: bool = False, options: dict | None = None,
              provider: str | None = None) -> Job:
        with self._lock:
            if self.busy():
                raise RuntimeError(f"Đang chạy: {self.current.label or LABELS.get(self.current.kind, self.current.kind)}")
            if quick:
                cmd = self.quick_command_for(kind, project_root, instruction, options, provider)
                label = QUICK_LABELS.get(kind, kind)
            else:
                if kind == "assist" and not instruction.strip():
                    raise ValueError("Cần nội dung yêu cầu cho AI")
                cmd = (self.command_for(kind, project_root, scenes, instruction) if instruction
                       else self.command_for(kind, project_root, scenes))
                label = LABELS.get(kind, kind)
            logs = project_root / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            log_path = logs / f"job-{stamp}-{kind}.log"
            f = open(log_path, "w", encoding="utf-8")
            proc = subprocess.Popen(cmd, cwd=REPO, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            self.current = Job(kind, project, log_path, proc, stamp, scenes, f, label=label, provider=provider or "")
            return self.current

    def stop(self) -> bool:
        """Dừng việc đang chạy (nút "Tạm dừng"). Trả False nếu không có việc nào đang chạy."""
        with self._lock:
            if not self.busy():
                return False
            job = self.current
            job.stopped = True
            job.proc.terminate()
            try:
                job.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                job.proc.kill()
                job.proc.wait()
            return True
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_quick_jobs.py tests/test_ui_api.py tests/test_ui_frames.py -v`
Expected: PASS (test cũ của quy trình đầy đủ không đổi).

- [ ] **Step 6: Commit**

```bash
git add src/vidflow/ui/quick_jobs.py src/vidflow/ui/jobs.py tests/test_ui_quick_jobs.py
git commit -m "feat(ui): JobRunner có nhãn, dừng việc và lệnh việc nền quy trình nhanh"
```

---

### Task 4: API đọc + media cho quy trình nhanh (Model: haiku)

**Files:**
- Create: `src/vidflow/ui/quick_api.py`
- Modify: `src/vidflow/ui/server.py` (import, `MEDIA_DIRS`, gắn router, route `/media`)
- Test: `tests/test_ui_quick.py` (mới)

**Interfaces:**
- Consumes: `ops.list_beats`, `ops.status_summary`, `ops.PASSING`, `ops.VOICE_FILE`; `chars.lookup`, `chars.char_rows`, `CharRef`; `is_quick`, `load_quick`, `load_beats`; `list_presets`, `load_preset`, `channel_refs_dir`, `ID_RE`; `JobRunner.start(..., quick=True)`, `JobRunner.stop()` (Task 3).
- Produces:
  - `quick_api.NAME_RE`, `CHAR_RE`, `SHEET_RE`.
  - `media_url(root: Path, name: str, rel: str | None) -> str | None` → `/media/<name>/<rel>?v=<mtime>`.
  - `char_url(name: str, preset_id: str, ref: CharRef | None) -> str | None` → `/media/<name>/refs/<file>?v=` (video) hoặc `/media/_presets/<preset>/<file>?v=` (bộ kênh).
  - `beat_state(row: dict, flow_running: bool) -> str` ∈ `ok | gen | error | blocked | redo | pending`.
  - `beat_rows(root, name, flow_running) -> list[dict]`: mỗi mốc = trường của `ops.list_beats` + `state`, `image_url`, `clip_url`, `attach: [{"kind": "char", "id", "url"} | {"kind": "prev", "n", "url"}]`.
  - `char_list(root, name) -> list[dict]`: `{id, name, desc, color, scope, uses, blocked, image_url}`.
  - `renders(root, name) -> list[dict]`: `{file: "out/<f>.mp4", url, size_mb, mtime}` mới nhất trước.
  - `quick_router(projects_root: Path, runner: JobRunner) -> APIRouter` với `GET /api/quick`, `GET /api/presets`, `GET /api/quick/{name}`, `GET /media/_presets/{preset_id}/{filename}`.
  - Payload `GET /api/quick/{name}`: `{name, quick, preset: {id, name, aspect}, aspect, status, beats, characters, renders, voice_url, job}`.
  - Test: fixture `env` (`env.c`, `env.root`, `env.tmp`, `env.presets`, `env.runner`), lớp `QuickFakeRunner` (`.cmd`, `.calls: list[(kind, instruction, options, provider)]`), hằng `FARMER`, hàm `wait_idle(c)`.

- [ ] **Step 1: Write the failing tests** — tạo `tests/test_ui_quick.py`:

```python
"""API quy trình nhanh trên UI (spec 2026-10-12, Giai đoạn 3)."""
import sys
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vidflow.quick import chars, ops
from vidflow.quick.model import create_quick
from vidflow.ui.jobs import JobRunner
from vidflow.ui.quick_api import beat_state
from vidflow.ui.server import create_app

FARMER = {"id": "FARMER", "name": "Nông dân", "desc": "hunched neolithic farmer", "color": "#8B5E3C"}


class QuickFakeRunner(JobRunner):
    """Thay lệnh thật (claude / vidflow quick) bằng lệnh python ngắn; ghi lại việc được gọi."""

    def __init__(self):
        super().__init__()
        self.cmd = [sys.executable, "-c", "print('ok')"]
        self.calls = []

    def quick_command_for(self, kind, project_root, instruction="", options=None, provider=None):
        self.calls.append((kind, instruction, dict(options or {}), provider))
        return self.cmd


def wait_idle(c):
    for _ in range(80):
        j = c.get("/api/jobs/current").json()
        if j.get("state") != "running":
            return j
        time.sleep(0.1)
    raise AssertionError("việc nền chưa xong")


@pytest.fixture
def env(tmp_path, qroot, quick_presets):
    runner = QuickFakeRunner()
    c = TestClient(create_app(projects_root=tmp_path, runner=runner))
    yield SimpleNamespace(c=c, root=qroot, tmp=tmp_path, presets=quick_presets, runner=runner)
    runner.stop()


def test_list_presets_and_quick(env):
    assert env.c.get("/api/quick").json() == [
        {"name": "vid", "title": "T", "preset": "doodle-giai-ma", "stage": "script", "beats": 4}]
    p = env.c.get("/api/presets").json()
    assert [x["id"] for x in p] == ["doodle-giai-ma"] and p[0]["characters"][0]["id"] == "MODERNYOU"


def test_get_quick_payload(env):
    d = env.c.get("/api/quick/vid").json()
    assert d["name"] == "vid" and d["aspect"] == "16:9" and d["preset"]["id"] == "doodle-giai-ma"
    assert [b["n"] for b in d["beats"]] == [1, 2, 3, 4]
    assert {b["state"] for b in d["beats"]} == {"pending"}
    assert d["beats"][0]["image_url"] is None and d["beats"][0]["attach"] == []
    assert d["characters"] == [{"id": "MODERNYOU", "name": "Người hiện đại",
                                "desc": "round-headed modern person in a cobalt t-shirt", "color": "#3557D6",
                                "scope": "channel", "uses": 0, "blocked": 0, "image_url": None}]
    assert d["status"]["beats"]["total"] == 4 and d["renders"] == [] and d["voice_url"] is None
    assert d["job"] is None and d["quick"]["flow"]["resolution"] == "720p"


def test_get_quick_new_project_without_beats(env):
    create_quick(env.tmp / "moi", preset="doodle-giai-ma")
    r = env.c.get("/api/quick/moi")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["beats"] == [] and d["status"]["stage"] == "new" and d["aspect"] == "16:9"


def test_unknown_quick_404(env):
    assert env.c.get("/api/quick/nope").status_code == 404
    assert env.c.get("/api/quick/Bad!").status_code == 404


def test_beat_states_attach_and_media(env, P, img):
    c, root = env.c, env.root
    chars.set_chars(root, [FARMER])
    ops.set_prompts(root, [{"n": 1, "prompt": P("a cave"), "verdict": "pass", "score": 8},
                           {"n": 2, "prompt": P("@FARMER digging"), "verdict": "pass", "score": 8},
                           {"n": 3, "prompt": P("the same cave"), "verdict": "pass", "score": 8, "cont": True}])
    ops.set_image(root, 1, img())
    ops.record_fail(root, 4, "Flow từ chối")
    d = c.get("/api/quick/vid").json()
    assert {b["n"]: b["state"] for b in d["beats"]} == {1: "ok", 2: "blocked", 3: "pending", 4: "error"}
    b1, b2, b3 = d["beats"][:3]
    assert b1["image_url"].startswith("/media/vid/images/001_00-00.png?v=")
    assert c.get(b1["image_url"].split("?")[0]).status_code == 200
    assert b2["attach"] == [{"kind": "char", "id": "FARMER", "url": None}] and b2["blocked"] == "thiếu ảnh @FARMER"
    assert b3["attach"] == [{"kind": "prev", "n": 2, "url": None}]
    far = next(x for x in d["characters"] if x["id"] == "FARMER")
    assert far["scope"] == "video" and far["uses"] == 1 and far["blocked"] == 1 and far["image_url"] is None


def test_flow_running_marks_gen(env, P):
    ops.set_prompts(env.root, [{"n": 1, "prompt": P("a cave"), "verdict": "pass", "score": 8}])
    env.runner.cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    env.runner.start("flow", "vid", env.root, quick=True)
    d = env.c.get("/api/quick/vid").json()
    assert [b["state"] for b in d["beats"]] == ["gen", "pending", "pending", "pending"]
    assert d["job"]["label"] == "Gen ảnh mốc trong Google Flow" and d["job"]["state"] == "running"


def test_media_quick_and_preset_refs(env):
    (env.root / "out" / "vid-v1.mp4").write_bytes(b"mp4")
    assert env.c.get("/media/vid/out/vid-v1.mp4").status_code == 200
    d = env.c.get("/api/quick/vid").json()
    assert d["renders"][0]["file"] == "out/vid-v1.mp4"
    assert d["renders"][0]["url"].startswith("/media/vid/out/vid-v1.mp4?v=")
    for bad in ("/media/vid/quick.yaml", "/media/vid/beats.json", "/media/vid/images/..%2Fquick.yaml",
                "/media/_presets/doodle-giai-ma/..%2F..%2Fdoodle-giai-ma.yaml", "/media/_presets/NOPE/X.png",
                "/media/_presets/doodle-giai-ma/MODERNYOU.png"):
        assert env.c.get(bad).status_code == 404, bad
    refs = env.presets / "refs" / "doodle-giai-ma"
    refs.mkdir(parents=True)
    (refs / "MODERNYOU.png").write_bytes(b"\x89PNGx")
    assert env.c.get("/media/_presets/doodle-giai-ma/MODERNYOU.png").status_code == 200
    me = next(x for x in env.c.get("/api/quick/vid").json()["characters"] if x["id"] == "MODERNYOU")
    assert me["image_url"].startswith("/media/_presets/doodle-giai-ma/MODERNYOU.png?v=")


def _row(**kw):
    base = dict(error="", status="pending", image=None, blocked=None, prompt="p", review={"verdict": "pass"}, start=0.0)
    return {**base, **kw}


@pytest.mark.parametrize("row,flow,want", [
    (_row(error="x", status="ok", image="i"), False, "error"),
    (_row(status="ok", image="i"), True, "ok"),
    (_row(blocked="thiếu ảnh @A"), True, "blocked"),
    (_row(blocked="chờ ảnh mốc 1"), True, "pending"),
    (_row(status="redo", image="i", review={"verdict": "override"}), True, "gen"),
    (_row(status="redo", image="i"), False, "redo"),
    (_row(review={"verdict": "fail"}), True, "pending"),
    (_row(start=None), True, "pending"),
])
def test_beat_state(row, flow, want):
    assert beat_state(row, flow) == want
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui_quick.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vidflow.ui.quick_api'`.

- [ ] **Step 3: Tạo `src/vidflow/ui/quick_api.py`**:

```python
"""API quy trình nhanh cho UI (spec 2026-10-12, Giai đoạn 3). Mọi ghi đi qua vidflow.quick.* (cùng luật với CLI)."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from vidflow.errors import VidflowError
from vidflow.quick import ops
from vidflow.quick.chars import CharRef, char_rows, lookup
from vidflow.quick.model import CHAR_ID, is_quick, load_beats, load_quick
from vidflow.quick.preset import ID_RE, channel_refs_dir, list_presets, load_preset
from vidflow.ui.jobs import JobRunner

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
CHAR_RE = re.compile(CHAR_ID)
SHEET_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,23}\.(png|jpg|webp)$")


def media_url(root: Path, name: str, rel: str | None) -> str | None:
    """URL /media của file trong project, kèm ?v=mtime để trình duyệt tải lại khi file đổi. None nếu chưa có file."""
    if not rel:
        return None
    f = Path(root) / rel
    if not f.is_file():
        return None
    return f"/media/{name}/{rel}?v={int(f.stat().st_mtime)}"


def char_url(name: str, preset_id: str, ref: CharRef | None) -> str | None:
    if ref is None or ref.image is None or not ref.image.is_file():
        return None
    v = int(ref.image.stat().st_mtime)
    if ref.scope == "channel":
        return f"/media/_presets/{preset_id}/{ref.image.name}?v={v}"
    return f"/media/{name}/refs/{ref.image.name}?v={v}"


def beat_state(row: dict, flow_running: bool) -> str:
    """Trạng thái hiển thị của mốc (UI luôn kèm chữ): ok | gen | error | blocked | redo | pending.
    "gen" = job Flow của video đang chạy và mốc gen được ngay; "blocked" = thiếu ảnh nhân vật."""
    if row["error"]:
        return "error"
    if row["status"] == "ok" and row["image"]:
        return "ok"
    reason = row.get("blocked") or ""
    if reason.startswith("thiếu ảnh"):
        return "blocked"
    review = row["review"]
    wants = (bool(row["prompt"]) and review is not None and review["verdict"] in ops.PASSING
             and row["start"] is not None and not reason)
    if flow_running and wants:
        return "gen"
    return "redo" if row["status"] == "redo" else "pending"


def beat_rows(root: Path, name: str, flow_running: bool) -> list[dict]:
    beats = load_beats(root)
    if beats is None or not beats.beats:
        return []
    q = load_quick(root)
    preset = load_preset(q.preset)
    known = lookup(root, q, preset)
    out: list[dict] = []
    prev: dict | None = None
    for r in ops.list_beats(root)["beats"]:
        attach = [{"kind": "char", "id": cid, "url": char_url(name, preset.id, known.get(cid))} for cid in r["refs"]]
        if r["cont"] and prev is not None:
            attach.append({"kind": "prev", "n": prev["n"], "url": media_url(root, name, prev["image"])})
        r.update(state=beat_state(r, flow_running), image_url=media_url(root, name, r["image"]),
                 clip_url=media_url(root, name, r["clip"]["file"]), attach=attach)
        out.append(r)
        prev = r
    return out


def char_list(root: Path, name: str) -> list[dict]:
    q = load_quick(root)
    preset = load_preset(q.preset)
    known = lookup(root, q, preset)
    rows = char_rows(root)
    for r in rows:
        r["image_url"] = char_url(name, preset.id, known.get(r["id"]))
        r.pop("image", None)  # đường dẫn tuyệt đối trên máy — không trả ra ngoài
    return rows


def renders(root: Path, name: str) -> list[dict]:
    out_dir = Path(root) / "out"
    files = sorted(out_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True) if out_dir.is_dir() else []
    return [{"file": f"out/{f.name}", "url": media_url(root, name, f"out/{f.name}"),
             "size_mb": round(f.stat().st_size / 1e6, 1),
             "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")} for f in files]


def quick_router(projects_root: Path, runner: JobRunner) -> APIRouter:
    router = APIRouter()
    projects_root = Path(projects_root)

    def qroot(name: str) -> Path:
        if not NAME_RE.match(name) or not is_quick(projects_root / name):
            raise HTTPException(404, f"Không có video nhanh '{name}'")
        return projects_root / name

    def job_of(name: str):
        cur = runner.current
        return cur if cur is not None and cur.project == name else None

    @router.get("/api/quick")
    def list_quick():
        out = []
        for d in sorted(projects_root.iterdir()):
            if not (d.is_dir() and NAME_RE.match(d.name) and is_quick(d)):
                continue
            try:
                q, b = load_quick(d), load_beats(d)
                out.append({"name": d.name, "title": q.title or d.name, "preset": q.preset, "stage": q.stage,
                            "beats": len(b.beats) if b else 0})
            except VidflowError as e:
                out.append({"name": d.name, "title": d.name, "error": str(e)})
        return out

    @router.get("/api/presets")
    def presets():
        try:
            return [{"id": p.id, "name": p.name, "aspect": p.aspect,
                     "characters": [c.model_dump() for c in p.characters]} for p in list_presets()]
        except VidflowError as e:
            raise HTTPException(422, str(e))

    @router.get("/api/quick/{name}")
    def get_quick(name: str):
        root = qroot(name)
        job = job_of(name)
        flow_running = job is not None and job.kind == "flow" and job.state == "running"
        try:
            q = load_quick(root)
            preset = load_preset(q.preset)
            beats = load_beats(root)
            return {"name": name, "quick": q.model_dump(mode="json"),
                    "preset": {"id": preset.id, "name": preset.name, "aspect": preset.aspect},
                    "aspect": beats.aspect if beats else preset.aspect,
                    "status": ops.status_summary(root),
                    "beats": beat_rows(root, name, flow_running),
                    "characters": char_list(root, name),
                    "renders": renders(root, name),
                    "voice_url": media_url(root, name, ops.VOICE_FILE),
                    "job": job.to_dict(tail=4000) if job else None}
        except VidflowError as e:
            raise HTTPException(422, str(e))

    @router.get("/media/_presets/{preset_id}/{filename}")
    def preset_media(preset_id: str, filename: str):
        if not ID_RE.match(preset_id) or not SHEET_RE.match(filename):
            raise HTTPException(404, "Không có file")
        try:
            folder = channel_refs_dir(load_preset(preset_id))
        except VidflowError:
            raise HTTPException(404, "Không có file")
        f = folder / filename
        if not f.is_file():
            raise HTTPException(404, "Không có file")
        return FileResponse(f)

    return router
```

- [ ] **Step 4: Gắn router và mở `/media` cho project nhanh** — trong `src/vidflow/ui/server.py`:

Thêm import (sau `from vidflow.ui.jobs import KINDS, JobRunner`):

```python
from vidflow.ui.quick_api import quick_router
```

Đổi hằng:

```python
MEDIA_DIRS = ("audio", "clips", "refs", "music", "inbox", "frames", "images", "out")
```

Ngay sau dòng `app.mount("/static", StaticFiles(directory=STATIC), name="static")` thêm (phải đứng TRƯỚC route `/media/{name}/{path:path}` để `/media/_presets/...` khớp trước):

```python
    app.include_router(quick_router(projects_root, runner))
```

Thay nguyên route `media` bằng:

```python
    @app.get("/media/{name}/{path:path}")
    def media(name: str, path: str):
        root = projects_root / name
        if not NAME_RE.match(name) or not ((root / "script.yaml").is_file() or (root / "quick.yaml").is_file()):
            raise HTTPException(404, "Không có file")
        root = root.resolve()
        target = (root / path).resolve()
        allowed = [(root / d).resolve() for d in MEDIA_DIRS]
        if not any(d in target.parents for d in allowed) or not target.is_file():
            raise HTTPException(404, "Không có file")
        return FileResponse(target)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_quick.py tests/test_ui_api.py tests/test_ui_frames.py -v`
Expected: PASS (gồm `test_media_cannot_escape_project` cũ).

- [ ] **Step 6: Commit**

```bash
git add src/vidflow/ui/quick_api.py src/vidflow/ui/server.py tests/test_ui_quick.py
git commit -m "feat(ui): API đọc quy trình nhanh, trạng thái mốc và media project nhanh"
```

---

### Task 5: API ghi — tạo video, cài đặt, chọn ý tưởng, mốc, clip, prompt, duyệt tay, việc nền (Model: haiku)

**Files:**
- Modify: `src/vidflow/ui/quick_api.py` (import, model request, route ghi)
- Test: `tests/test_ui_quick.py`

**Interfaces:**
- Consumes: `ops.update_settings` (có `image_provider`, `video_provider` — Giai đoạn 1b), `pick_idea`, `mark_redo`, `clear_errors`, `edit_prompt`, `set_review`; `clips.set_clip_enabled`; `chars.promote`; `create_quick`; `check_quick_job` (Task 3); `JobRunner.start(..., quick=True, options=...)`, `JobRunner.stop()`.
- Produces (body JSON → kết quả):
  - `POST /api/quick` `{name="", preset, topic="", channel_chars=None, image_model="Nano Banana 2", video_model="", resolution="720p", image_provider="flow", video_provider="flow", max_clips=12, allow_cont=True, start=True}` → 201 `{name, job: dict|None, warning: str|None}`.
  - `POST /api/quick/{name}/settings` `{image_model?, video_model?, resolution?, image_provider?, video_provider?, max_clips?, allow_cont?, channel_chars?}` → `{quick}` (nguồn sai → 422).
  - `POST /pick` `{n}` → `{title}`; `/redo` `{ns, clip=False}` → `{ok}`; `/retry` `{ns=None, clip=False}` → `{count}`; `/clip` `{ns, on}` → `{ok}`; `/prompt` `{n, prompt, clip=False}` → `{beat}`; `/override` `{n, clip=False}` → `{ok}`; `/chars/{char_id}/promote` → `{ok}`.
  - `POST /api/quick/{name}/jobs` `{kind, instruction="", options={}, provider=None}` → 202 job dict (có `provider` = nguồn thực dùng, `quota_exhausted`); `POST /api/quick/{name}/jobs/stop` → `{stopped: true}` (409 khi không có việc của video này).
  - Hàm `default_name(preset: str) -> str`, `ideas_hint(topic: str) -> str`.

- [ ] **Step 1: Write the failing tests** — thêm vào cuối `tests/test_ui_quick.py` (thêm `from vidflow.quick.model import load_beats, load_quick` và `from vidflow.quick.preset import load_preset` vào khối import đầu file):

```python
def test_create_quick_project_and_ideas_job(env):
    r = env.c.post("/api/quick", json={"preset": "doodle-giai-ma", "topic": "tổ tiên 50.000 năm trước",
                                       "video_model": "Veo 3.1 Lite", "max_clips": 5, "allow_cont": False})
    assert r.status_code == 201, r.text
    name = r.json()["name"]
    assert name.startswith("doodle-giai-ma-")
    q = load_quick(env.tmp / name)
    assert q.title == "tổ tiên 50.000 năm trước" and q.flow.video_model == "Veo 3.1 Lite"
    assert q.max_clips == 5 and q.allow_cont is False and q.flow.resolution == "720p"
    kind, instruction, _, _ = env.runner.calls[0]
    assert kind == "ideas" and "tổ tiên 50.000 năm trước" in instruction
    assert r.json()["job"]["label"] == "Claude đề xuất 5 ý tưởng"
    assert name in [x["name"] for x in env.c.get("/api/quick").json()]
    wait_idle(env.c)


def test_create_validation_leaves_nothing_behind(env):
    base = {"preset": "doodle-giai-ma", "start": False}
    r = env.c.post("/api/quick", json={**base, "max_clips": 3})
    assert r.status_code == 422 and "model clip" in r.json()["detail"]
    assert env.c.post("/api/quick", json={**base, "name": "x1", "max_clips": 0}).status_code == 201
    assert env.c.post("/api/quick", json={**base, "name": "x1", "max_clips": 0}).status_code == 409
    assert env.c.post("/api/quick", json={**base, "name": "Bad Name", "max_clips": 0}).status_code == 422
    assert env.c.post("/api/quick", json={**base, "preset": "nope", "name": "x2", "max_clips": 0}).status_code == 422
    assert env.c.post("/api/quick", json={**base, "preset": "../x", "name": "x4", "max_clips": 0}).status_code == 422
    r = env.c.post("/api/quick", json={**base, "name": "x3", "max_clips": 0, "channel_chars": ["GHOST"]})
    assert r.status_code == 422 and "GHOST" in r.json()["detail"]
    for gone in ("x2", "x3", "x4"):
        assert not (env.tmp / gone).exists()
    assert env.runner.calls == []


def test_settings_pick_clip_redo_retry(env, img):
    c, root = env.c, env.root
    assert c.post("/api/quick/vid/settings", json={"video_model": "Veo 3.1 Lite", "max_clips": 1}).status_code == 200
    q = load_quick(root)
    assert q.flow.video_model == "Veo 3.1 Lite" and q.max_clips == 1
    assert c.post("/api/quick/vid/settings", json={"resolution": "4k"}).status_code == 422
    ops.set_ideas(root, [{"title": "Ý A"}, {"title": "Ý B"}])
    r = c.post("/api/quick/vid/pick", json={"n": 2})
    assert r.status_code == 200 and r.json() == {"title": "Ý B"}
    assert c.post("/api/quick/vid/pick", json={"n": 9}).status_code == 422
    assert c.post("/api/quick/vid/clip", json={"ns": [1], "on": True}).status_code == 200
    r = c.post("/api/quick/vid/clip", json={"ns": [2], "on": True})
    assert r.status_code == 422 and "Tối đa 1 clip" in r.json()["detail"]
    ops.set_image(root, 1, img())
    assert c.post("/api/quick/vid/redo", json={"ns": [1]}).status_code == 200
    assert load_beats(root).get(1).status == "redo"
    assert c.post("/api/quick/vid/redo", json={"ns": [99]}).status_code == 422
    assert c.post("/api/quick/vid/redo", json={"ns": []}).status_code == 422
    ops.record_fail(root, 2, "bị chặn nội dung")
    r = c.post("/api/quick/vid/retry", json={})
    assert r.status_code == 200 and r.json() == {"count": 1}
    assert load_beats(root).get(2).error == ""


def test_prompt_edit_clears_review_and_validates(env, P):
    c, root = env.c, env.root
    ops.set_prompts(root, [{"n": 1, "prompt": P("a cave"), "verdict": "pass", "score": 9}])
    r = c.post("/api/quick/vid/prompt", json={"n": 1, "prompt": P("@MODERNYOU in a cave")})
    assert r.status_code == 200, r.text
    b = load_beats(root).get(1)
    assert b.review is None and b.refs == ["MODERNYOU"]
    assert c.post("/api/quick/vid/prompt", json={"n": 1, "prompt": "no anchors"}).status_code == 422
    r = c.post("/api/quick/vid/prompt", json={"n": 1, "prompt": P("@GHOST")})
    assert r.status_code == 422 and "@GHOST" in r.json()["detail"]
    r = c.post("/api/quick/vid/prompt", json={"n": 1, "prompt": "@MODERNYOU waves", "clip": True})
    assert r.status_code == 200 and load_beats(root).get(1).clip.prompt == "@MODERNYOU waves"


def test_override_marks_review(env, P):
    ops.set_prompts(env.root, [{"n": 1, "prompt": P("x"), "verdict": "fail", "score": 3}])
    assert env.c.post("/api/quick/vid/override", json={"n": 1}).status_code == 200
    assert load_beats(env.root).get(1).review.verdict == "override"
    assert env.c.post("/api/quick/vid/override", json={"n": 2}).status_code == 422  # chưa có prompt


def test_promote(env):
    chars.set_chars(env.root, [FARMER])
    assert env.c.post("/api/quick/vid/chars/FARMER/promote").status_code == 200
    assert "FARMER" in [x.id for x in load_preset("doodle-giai-ma").characters]
    assert env.c.post("/api/quick/vid/chars/FARMER/promote").status_code == 422
    assert env.c.post("/api/quick/vid/chars/bad/promote").status_code == 404


def test_jobs_validation_and_options(env):
    c = env.c
    assert c.post("/api/quick/vid/jobs", json={"kind": "gen"}).status_code == 422
    r = c.post("/api/quick/vid/jobs", json={"kind": "script"})
    assert r.status_code == 422 and "ý tưởng" in r.json()["detail"]
    r = c.post("/api/quick/vid/jobs", json={"kind": "clips"})
    assert r.status_code == 422 and "model clip" in r.json()["detail"]
    for bad in ({"resolution": "4k"}, {"resolution": "1080p; rm -rf /"}, {"output": "/tmp/x.mp4"}):
        assert c.post("/api/quick/vid/jobs", json={"kind": "render", "options": bad}).status_code == 422, bad
    assert env.runner.calls == []
    r = c.post("/api/quick/vid/jobs", json={"kind": "render", "options": {"resolution": "720p", "zoom": False}})
    assert r.status_code == 202 and r.json()["label"] == "Xuất MP4 (Remotion)"
    assert env.runner.calls[-1] == ("render", "", {"resolution": "720p", "zoom": False}, None)
    wait_idle(c)
    assert c.post("/api/quick/nope/jobs", json={"kind": "voice"}).status_code == 404


def test_providers_settings_create_and_job_override(env):
    c, root = env.c, env.root
    r = c.post("/api/quick/vid/settings", json={"image_provider": "gemini", "video_provider": "aistudio"})
    assert r.status_code == 200, r.text
    q = load_quick(root)
    assert (q.flow.image_provider, q.flow.video_provider) == ("gemini", "aistudio")
    assert c.post("/api/quick/vid/settings", json={"image_provider": "midjourney"}).status_code == 422
    r = c.post("/api/quick", json={"preset": "doodle-giai-ma", "name": "p1", "max_clips": 0, "start": False,
                                   "image_provider": "aistudio", "video_provider": "gemini"})
    assert r.status_code == 201, r.text
    q1 = load_quick(env.tmp / "p1")
    assert (q1.flow.image_provider, q1.flow.video_provider) == ("aistudio", "gemini")
    assert c.post("/api/quick", json={"preset": "doodle-giai-ma", "name": "p2", "max_clips": 0,
                                      "image_provider": "x"}).status_code == 422
    assert c.post("/api/quick/vid/jobs", json={"kind": "voice", "provider": "gemini"}).status_code == 422
    assert c.post("/api/quick/vid/jobs", json={"kind": "flow", "provider": "midjourney"}).status_code == 422
    r = c.post("/api/quick/vid/jobs", json={"kind": "flow"})
    assert r.status_code == 202 and r.json()["provider"] == "gemini"  # theo cài đặt video
    assert env.runner.calls[-1][3] is None
    wait_idle(c)
    r = c.post("/api/quick/vid/jobs", json={"kind": "flow", "provider": "flow"})  # ghi đè một lần
    assert r.json()["provider"] == "flow" and env.runner.calls[-1][3] == "flow"
    wait_idle(c)
    assert load_quick(root).flow.image_provider == "gemini"  # ghi đè không đổi cài đặt
    j = c.get("/api/quick/vid").json()["job"]
    assert j["provider"] == "flow" and j["quota_exhausted"] is False


def test_quota_exhausted_job_reported(env):
    env.runner.cmd = [sys.executable, "-c", "import sys; print('hết lượt ở gemini'); sys.exit(3)"]
    assert env.c.post("/api/quick/vid/jobs", json={"kind": "flow", "provider": "gemini"}).status_code == 202
    j = wait_idle(env.c)
    assert j["quota_exhausted"] is True and j["provider"] == "gemini" and j["state"] == "failed"
    assert env.c.get("/api/quick/vid").json()["job"]["quota_exhausted"] is True


def test_stop_job(env):
    env.runner.cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    assert env.c.post("/api/quick/vid/jobs", json={"kind": "voice"}).status_code == 202
    assert env.c.post("/api/quick/vid/jobs", json={"kind": "voice"}).status_code == 409
    r = env.c.post("/api/quick/vid/jobs/stop")
    assert r.status_code == 200 and r.json() == {"stopped": True}
    assert env.c.get("/api/jobs/current").json()["state"] == "stopped"
    assert env.c.post("/api/quick/vid/jobs/stop").status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui_quick.py -v`
Expected: FAIL — các test mới nhận 404/405 (`POST /api/quick` chưa có).

- [ ] **Step 3: Thay khối import đầu `src/vidflow/ui/quick_api.py`** bằng:

```python
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from vidflow.errors import VidflowError
from vidflow.quick import chars, clips, ops
from vidflow.quick.chars import CharRef, char_rows, lookup
from vidflow.quick.model import CHAR_ID, create_quick, is_quick, load_beats, load_quick
from vidflow.quick.preset import ID_RE, channel_refs_dir, list_presets, load_preset
from vidflow.ui.jobs import JobRunner
from vidflow.ui.quick_jobs import PROVIDER_KINDS, check_quick_job
```

- [ ] **Step 4: Thêm model request và hàm phụ** — ngay trước `def quick_router(`:

```python
Provider = Literal["flow", "gemini", "aistudio"]


class NewQuick(BaseModel):
    name: str = ""
    preset: str
    topic: str = ""
    channel_chars: list[str] | None = None  # None = mọi nhân vật bộ kênh
    image_model: str = "Nano Banana 2"
    video_model: str = ""
    resolution: str = "720p"
    image_provider: Provider = "flow"
    video_provider: Provider = "flow"
    max_clips: int = Field(default=12, ge=0, le=200)
    allow_cont: bool = True
    start: bool = True  # chạy job đề xuất ý tưởng ngay


class SettingsReq(BaseModel):
    image_model: str | None = None
    video_model: str | None = None
    resolution: str | None = None
    image_provider: Provider | None = None
    video_provider: Provider | None = None
    max_clips: int | None = None
    allow_cont: bool | None = None
    channel_chars: list[str] | None = None


class PickReq(BaseModel):
    n: int


class BeatsReq(BaseModel):
    ns: list[int] = Field(min_length=1)
    clip: bool = False


class RetryReq(BaseModel):
    ns: list[int] | None = None
    clip: bool = False


class ClipReq(BaseModel):
    ns: list[int] = Field(min_length=1)
    on: bool


class PromptReq(BaseModel):
    n: int
    prompt: str
    clip: bool = False


class BeatReq(BaseModel):
    n: int
    clip: bool = False


class QuickJobReq(BaseModel):
    kind: str
    instruction: str = ""
    options: dict = Field(default_factory=dict)
    provider: str | None = None  # ghi đè nguồn gen một lần (sheets/flow/clips)


def default_name(preset: str) -> str:
    return f"{preset}-{datetime.now():%m%d-%H%M%S}"[:41]


def ideas_hint(topic: str) -> str:
    topic = topic.strip()
    return f"Chủ đề người dùng gợi ý: {topic} — cả 5 ý tưởng xoay quanh chủ đề này." if topic else ""


def _do(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except VidflowError as e:
        raise HTTPException(422, str(e))
```

- [ ] **Step 5: Thêm route ghi** — trong `quick_router`, ngay trước `return router`:

```python
    @router.post("/api/quick", status_code=201)
    def create(req: NewQuick):
        if not ID_RE.match(req.preset):
            raise HTTPException(422, f"Không có bộ kênh '{req.preset}'")
        name = req.name.strip() or default_name(req.preset)
        if not NAME_RE.match(name):
            raise HTTPException(422, "Tên thư mục chỉ gồm chữ thường không dấu, số, '-' hoặc '_'")
        root = projects_root / name
        if root.exists():
            raise HTTPException(409, f"'{name}' đã tồn tại")
        if req.max_clips > 0 and not req.video_model.strip():
            raise HTTPException(422, "Chọn model clip động (bắt buộc khi số clip tối đa > 0).")
        try:
            load_preset(req.preset)
            create_quick(root, preset=req.preset, title=req.topic.strip())
            ops.update_settings(root, image_model=req.image_model, video_model=req.video_model,
                                resolution=req.resolution, image_provider=req.image_provider,
                                video_provider=req.video_provider, max_clips=req.max_clips, allow_cont=req.allow_cont,
                                channel_chars=req.channel_chars)
        except VidflowError as e:
            shutil.rmtree(root, ignore_errors=True)
            raise HTTPException(422, str(e))
        out = {"name": name, "job": None, "warning": None}
        if req.start:
            try:
                job = runner.start("ideas", name, root, instruction=ideas_hint(req.topic), quick=True)
                out["job"] = job.to_dict(tail=0)
            except RuntimeError as e:
                out["warning"] = f"{e} — bấm “Đề xuất 5 ý tưởng” sau."
        return out

    @router.post("/api/quick/{name}/settings")
    def settings(name: str, req: SettingsReq):
        q = _do(ops.update_settings, qroot(name), **req.model_dump(exclude_unset=True))
        return {"quick": q.model_dump(mode="json")}

    @router.post("/api/quick/{name}/pick")
    def pick(name: str, req: PickReq):
        return {"title": _do(ops.pick_idea, qroot(name), req.n).title}

    @router.post("/api/quick/{name}/redo")
    def redo(name: str, req: BeatsReq):
        _do(ops.mark_redo, qroot(name), req.ns, clip=req.clip)
        return {"ok": True}

    @router.post("/api/quick/{name}/retry")
    def retry(name: str, req: RetryReq):
        return {"count": _do(ops.clear_errors, qroot(name), req.ns, clip=req.clip)}

    @router.post("/api/quick/{name}/clip")
    def clip_toggle(name: str, req: ClipReq):
        _do(clips.set_clip_enabled, qroot(name), req.ns, req.on)
        return {"ok": True}

    @router.post("/api/quick/{name}/prompt")
    def prompt_ep(name: str, req: PromptReq):
        beat = _do(ops.edit_prompt, qroot(name), req.n, req.prompt, clip=req.clip)
        return {"beat": beat.model_dump(mode="json")}

    @router.post("/api/quick/{name}/override")
    def override(name: str, req: BeatReq):
        _do(ops.set_review, qroot(name), req.n, "override", score=0, issues=["người dùng duyệt tay"], clip=req.clip)
        return {"ok": True}

    @router.post("/api/quick/{name}/chars/{char_id}/promote")
    def promote(name: str, char_id: str):
        root = qroot(name)
        if not CHAR_RE.match(char_id):
            raise HTTPException(404, f"Không có nhân vật @{char_id}")
        _do(chars.promote, root, char_id)
        return {"ok": True}

    @router.post("/api/quick/{name}/jobs", status_code=202)
    def start_job(name: str, req: QuickJobReq):
        root = qroot(name)
        try:
            check_quick_job(req.kind, root, req.options, req.provider)
            job = runner.start(req.kind, name, root, instruction=req.instruction, quick=True, options=req.options,
                               provider=req.provider)
        except (VidflowError, ValueError) as e:
            raise HTTPException(422, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))
        if req.kind in PROVIDER_KINDS:  # nguồn thực dùng: ghi đè, hoặc theo cài đặt video
            flow = load_quick(root).flow
            job.provider = req.provider or (flow.video_provider if req.kind == "clips" else flow.image_provider)
        return job.to_dict(tail=0)

    @router.post("/api/quick/{name}/jobs/stop")
    def stop_job(name: str):
        qroot(name)
        cur = runner.current
        if cur is None or cur.project != name or cur.state != "running":
            raise HTTPException(409, "Không có việc đang chạy của video này")
        runner.stop()
        return {"stopped": True}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_quick.py tests/test_ui_quick_jobs.py tests/test_ui_api.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/vidflow/ui/quick_api.py tests/test_ui_quick.py
git commit -m "feat(ui): API ghi quy trình nhanh — tạo video, cài đặt, mốc, clip, prompt, việc nền"
```

---

### Task 6: Kiểm duyệt một mốc ở hàng đợi riêng (Model: haiku)

**Files:**
- Modify: `src/vidflow/ui/jobs.py` (thêm `ReviewRunner`)
- Modify: `src/vidflow/ui/quick_api.py` (import, chữ ký `quick_router`, route `/review`)
- Modify: `src/vidflow/ui/server.py` (`create_app(..., review_runner=None)`)
- Test: `tests/test_ui_quick.py` (sửa fixture `env`, thêm test)

**Interfaces:**
- Consumes: `vidflow.quick.jobs.review_cmd(root, preset, n, clip=)` (Giai đoạn 1, không dùng `--chrome`); `require_beats`.
- Produces:
  - `ReviewRunner` (`timeout = 300`; `run(cmd: list[str]) -> tuple[int, str]`; trả mã 124 khi quá thời gian; tuần tự bằng khóa riêng, độc lập `JobRunner`).
  - `quick_router(projects_root: Path, runner: JobRunner, reviews: ReviewRunner) -> APIRouter`.
  - `create_app(projects_root, runner=None, config_path=None, suggester=None, password=None, review_runner=None)`.
  - `POST /api/quick/{name}/review` `{n, clip=False}` → 200 `{n, clip, review: {verdict, score, issues}, summary}`; 422 chưa có prompt; 502 claude lỗi hoặc không ghi kết quả; 504 quá thời gian.
  - Fixture `env` thêm `env.reviews` (`FakeReview`: `.cmds`, `.action`, `.rc`, `.out`).

- [ ] **Step 1: Write the failing tests** — trong `tests/test_ui_quick.py`: thêm import `from vidflow.ui.jobs import ReviewRunner` (cạnh import `JobRunner`), thêm lớp sau `QuickFakeRunner`, thay fixture `env`, rồi thêm các test ở cuối file:

```python
class FakeReview(ReviewRunner):
    """Giả lập `claude -p` vai prompt-reviewer: chạy `action` (ghi kết quả qua ops) rồi trả (rc, out)."""

    def __init__(self):
        super().__init__()
        self.cmds, self.action, self.rc, self.out = [], None, 0, "Mốc 1: trượt 4/10"

    def run(self, cmd):
        self.cmds.append(cmd)
        if self.action:
            self.action()
        return self.rc, self.out


@pytest.fixture
def env(tmp_path, qroot, quick_presets):
    runner, reviews = QuickFakeRunner(), FakeReview()
    c = TestClient(create_app(projects_root=tmp_path, runner=runner, review_runner=reviews))
    yield SimpleNamespace(c=c, root=qroot, tmp=tmp_path, presets=quick_presets, runner=runner, reviews=reviews)
    runner.stop()
```

```python
def test_review_runs_while_flow_job_running(env, P):
    c, root = env.c, env.root
    ops.set_prompts(root, [{"n": 1, "prompt": P("@MODERNYOU at dawn"), "verdict": "pass", "score": 8}])
    assert c.post("/api/quick/vid/prompt", json={"n": 1, "prompt": P("@MODERNYOU at dusk")}).status_code == 200
    env.reviews.action = lambda: ops.set_review(root, 1, "fail", score=4, issues=["thiếu bối cảnh — thêm hang đá"])
    env.runner.cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    assert c.post("/api/quick/vid/jobs", json={"kind": "flow"}).status_code == 202
    r = c.post("/api/quick/vid/review", json={"n": 1})
    assert r.status_code == 200, r.text
    assert r.json() == {"n": 1, "clip": False, "summary": "Mốc 1: trượt 4/10",
                        "review": {"verdict": "fail", "score": 4.0, "issues": ["thiếu bối cảnh — thêm hang đá"]}}
    assert c.get("/api/jobs/current").json()["state"] == "running"  # job Flow vẫn chạy, kiểm duyệt không bị chặn
    cmd = env.reviews.cmds[0]
    assert cmd[0] == "claude" and "--chrome" not in cmd and "mốc 1" in cmd[-1] and "set-review" in cmd[-1]


def test_review_clip_prompt(env, P):
    from vidflow.quick import clips
    clips.set_clip_prompts(env.root, [{"n": 2, "prompt": "frame-by-frame doodle motion", "verdict": "fail", "score": 2}])
    env.reviews.action = lambda: ops.set_review(env.root, 2, "pass", score=8, clip=True)
    r = env.c.post("/api/quick/vid/review", json={"n": 2, "clip": True})
    assert r.status_code == 200 and r.json()["review"]["verdict"] == "pass"
    assert "--clip" in env.reviews.cmds[0][-1]


def test_review_errors(env, P):
    c, root = env.c, env.root
    assert c.post("/api/quick/vid/review", json={"n": 1}).status_code == 422  # chưa có prompt ảnh
    assert c.post("/api/quick/vid/review", json={"n": 1, "clip": True}).status_code == 422
    assert c.post("/api/quick/vid/review", json={"n": 99}).status_code == 422
    ops.edit_prompt(root, 1, P("a cave"))
    env.reviews.rc, env.reviews.out = 1, "claude: lỗi mạng"
    r = c.post("/api/quick/vid/review", json={"n": 1})
    assert r.status_code == 502 and "lỗi mạng" in r.json()["detail"]
    env.reviews.rc = 0  # chạy xong nhưng không ghi kết quả
    r = c.post("/api/quick/vid/review", json={"n": 1})
    assert r.status_code == 502 and "không ghi kết quả" in r.json()["detail"]
    env.reviews.rc, env.reviews.out = 124, "Kiểm duyệt quá 300 giây"
    assert c.post("/api/quick/vid/review", json={"n": 1}).status_code == 504
    assert env.reviews.cmds and len(env.reviews.cmds) == 3


def test_review_runner_real_subprocess():
    r = ReviewRunner()
    assert r.run([sys.executable, "-c", "print('Mốc 3: đạt 9/10')"]) == (0, "Mốc 3: đạt 9/10")
    r.timeout = 0.3
    rc, out = r.run([sys.executable, "-c", "import time; time.sleep(3)"])
    assert rc == 124 and "quá" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui_quick.py -v`
Expected: FAIL — `ImportError: cannot import name 'ReviewRunner' from 'vidflow.ui.jobs'`.

- [ ] **Step 3: Thêm `ReviewRunner`** — cuối `src/vidflow/ui/jobs.py`:

```python
class ReviewRunner:
    """Hàng đợi RIÊNG cho kiểm duyệt một mốc (`claude -p`, không Chrome): các lần kiểm duyệt chạy tuần tự với nhau
    nhưng độc lập với JobRunner — không bị job Flow đang chạy chặn (nút "Lưu & kiểm duyệt")."""
    timeout = 300

    def __init__(self):
        self._lock = threading.Lock()

    def run(self, cmd: list[str]) -> tuple[int, str]:
        with self._lock:
            try:
                r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=self.timeout,
                                   stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                return 124, f"Kiểm duyệt quá {self.timeout} giây"
            return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
```

- [ ] **Step 4: Route `/review`** — trong `src/vidflow/ui/quick_api.py`:

Trong khối import: đổi dòng model thành `from vidflow.quick.model import CHAR_ID, create_quick, is_quick, load_beats, load_quick, require_beats`, thêm `from vidflow.quick.jobs import review_cmd`, đổi `from vidflow.ui.jobs import JobRunner` thành `from vidflow.ui.jobs import JobRunner, ReviewRunner`.

Đổi dòng định nghĩa router thành:

```python
def quick_router(projects_root: Path, runner: JobRunner, reviews: ReviewRunner) -> APIRouter:
```

Thêm route trước `return router`:

```python
    @router.post("/api/quick/{name}/review")
    def review(name: str, req: BeatReq):
        root = qroot(name)
        try:
            q = load_quick(root)
            beat = require_beats(root).get(req.n)
            if not (beat.clip.prompt if req.clip else beat.prompt):
                raise VidflowError(f"Mốc {req.n} chưa có prompt {'clip' if req.clip else 'ảnh'} để kiểm duyệt.")
            cmd = review_cmd(root, load_preset(q.preset), req.n, clip=req.clip)
        except VidflowError as e:
            raise HTTPException(422, str(e))
        rc, out = reviews.run(cmd)
        if rc == 124:
            raise HTTPException(504, out)
        if rc != 0:
            raise HTTPException(502, f"Kiểm duyệt lỗi (mã {rc}): {out[-400:]}")
        beat = require_beats(root).get(req.n)
        rv = beat.clip.review if req.clip else beat.review
        if rv is None:
            raise HTTPException(502, "Kiểm duyệt không ghi kết quả — thử lại.")
        lines = [ln for ln in out.splitlines() if ln.strip()]
        return {"n": req.n, "clip": req.clip, "review": rv.model_dump(), "summary": lines[-1] if lines else ""}
```

- [ ] **Step 5: `create_app` nhận `review_runner`** — trong `src/vidflow/ui/server.py`:

Đổi import thành `from vidflow.ui.jobs import KINDS, JobRunner, ReviewRunner`.

Đổi chữ ký:

```python
def create_app(projects_root: Path, runner: JobRunner | None = None, config_path: Path | None = None,
               suggester: Suggester | None = None, password: str | None = None,
               review_runner: ReviewRunner | None = None) -> FastAPI:
```

Đổi dòng gắn router thành:

```python
    app.include_router(quick_router(projects_root, runner, review_runner or ReviewRunner()))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_quick.py tests/test_ui_api.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/vidflow/ui/jobs.py src/vidflow/ui/quick_api.py src/vidflow/ui/server.py tests/test_ui_quick.py
git commit -m "feat(ui): kiểm duyệt một mốc ở hàng đợi riêng, chạy song song job Flow"
```

---

### Task 7: Tải ảnh nhân vật, sóng âm giọng đọc, chốt đăng nhập cho mọi route mới (Model: haiku)

**Files:**
- Modify: `src/vidflow/ui/quick_api.py` (import, `MAX_UPLOAD`, `sniff_image`, `waveform`, 2 route)
- Test: `tests/test_ui_quick.py`, `tests/test_ui_auth.py`

**Interfaces:**
- Consumes: `chars.set_char_image(root, id, src, channel=)`, `lookup`; `IMAGE_EXTS`; `ops.VOICE_FILE`.
- Produces:
  - `MAX_UPLOAD = 15 * 1024 * 1024`; `sniff_image(data: bytes) -> str | None` (`.png` / `.jpg` / `.webp`).
  - `waveform(path: Path, bins: int) -> tuple[list[float], float]` (đỉnh 0–1 mỗi đoạn, độ dài giây).
  - `POST /api/quick/{name}/chars/{char_id}/image` (multipart, trường `file`) → `{image_url}`; 404 nhân vật lạ; 422 đuôi/nội dung không phải ảnh; 413 quá 15 MB.
  - `GET /api/quick/{name}/waveform?bins=300` (20 ≤ bins ≤ 2000) → `{peaks: list[float], duration: float}`; chưa có giọng → `{peaks: [], duration: 0}`.

- [ ] **Step 1: Write the failing tests** — thêm vào cuối `tests/test_ui_quick.py` (thêm `import wave` và `from array import array` vào khối import đầu file):

```python
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def test_upload_char_image_video_and_channel(env):
    chars.set_chars(env.root, [FARMER])
    r = env.c.post("/api/quick/vid/chars/FARMER/image", files={"file": ("farmer.PNG", PNG, "image/png")})
    assert r.status_code == 200, r.text
    assert (env.root / "refs" / "FARMER.png").read_bytes() == PNG
    url = r.json()["image_url"]
    assert url.startswith("/media/vid/refs/FARMER.png?v=")
    assert env.c.get(url.split("?")[0]).status_code == 200
    r = env.c.post("/api/quick/vid/chars/MODERNYOU/image",
                   files={"file": ("m.jpg", b"\xff\xd8\xff\xe0" + b"0" * 20, "image/jpeg")})
    assert r.status_code == 200, r.text
    assert (env.presets / "refs" / "doodle-giai-ma" / "MODERNYOU.jpg").is_file()
    assert r.json()["image_url"].startswith("/media/_presets/doodle-giai-ma/MODERNYOU.jpg?v=")
    assert env.c.get("/media/_presets/doodle-giai-ma/MODERNYOU.jpg").status_code == 200
    assert list((env.root / "tmp").iterdir()) == []


def test_upload_validation(env, monkeypatch):
    import vidflow.ui.quick_api as qa

    chars.set_chars(env.root, [FARMER])

    def up(cid, fname, data):
        return env.c.post(f"/api/quick/vid/chars/{cid}/image", files={"file": (fname, data, "application/octet-stream")})

    assert up("FARMER", "f.gif", PNG).status_code == 422
    r = up("FARMER", "f.png", b"<script>alert(1)</script>")
    assert r.status_code == 422 and "không phải ảnh" in r.json()["detail"]
    assert up("GHOST", "f.png", PNG).status_code == 404
    assert up("bad-id", "f.png", PNG).status_code == 404
    monkeypatch.setattr(qa, "MAX_UPLOAD", 10)
    assert up("FARMER", "f.png", PNG).status_code == 413
    assert not any((env.root / "refs").iterdir())
    assert list((env.root / "tmp").iterdir()) == []


def test_waveform(env):
    assert env.c.get("/api/quick/vid/waveform").json() == {"peaks": [], "duration": 0}
    a = array("h", [0] * 24000 + [16384] * 24000)
    with wave.open(str(env.root / "audio" / "voice.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(a.tobytes())
    r = env.c.get("/api/quick/vid/waveform?bins=100").json()
    assert r["duration"] == 2.0 and len(r["peaks"]) == 100
    assert r["peaks"][0] == 0.0 and r["peaks"][-1] == 0.5
    assert env.c.get("/api/quick/vid/waveform?bins=5").status_code == 422
    assert env.c.get("/api/quick/vid").json()["voice_url"].startswith("/media/vid/audio/voice.wav?v=")
```

Thêm vào cuối `tests/test_ui_auth.py`:

```python
QUICK_ROUTES = [
    ("get", "/api/quick"), ("get", "/api/presets"), ("get", "/api/quick/vid"), ("post", "/api/quick"),
    ("post", "/api/quick/vid/settings"), ("post", "/api/quick/vid/pick"), ("post", "/api/quick/vid/redo"),
    ("post", "/api/quick/vid/retry"), ("post", "/api/quick/vid/clip"), ("post", "/api/quick/vid/prompt"),
    ("post", "/api/quick/vid/review"), ("post", "/api/quick/vid/override"),
    ("post", "/api/quick/vid/chars/FARMER/image"), ("post", "/api/quick/vid/chars/FARMER/promote"),
    ("post", "/api/quick/vid/jobs"), ("post", "/api/quick/vid/jobs/stop"), ("get", "/api/quick/vid/waveform"),
    ("get", "/media/vid/images/001_00-00.jpg"), ("get", "/media/_presets/doodle-giai-ma/MODERNYOU.png"),
]


@pytest.mark.parametrize("method,path", QUICK_ROUTES)
def test_quick_routes_require_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui_quick.py tests/test_ui_auth.py -v`
Expected: FAIL — `test_upload_*` nhận 404/405, `test_waveform` nhận 404. (`test_quick_routes_require_login` PASS ngay — middleware đã chặn; giữ làm test chốt chống hồi quy.)

- [ ] **Step 3: Cài đặt** — trong `src/vidflow/ui/quick_api.py`:

Khối import: thêm `import wave` và `from array import array` (sau `import shutil`), đổi `from fastapi import APIRouter, HTTPException` thành `from fastapi import APIRouter, File, HTTPException, Query, UploadFile`, đổi dòng model thành `from vidflow.quick.model import CHAR_ID, IMAGE_EXTS, create_quick, is_quick, load_beats, load_quick, require_beats`.

Thêm sau `SHEET_RE = ...`:

```python
MAX_UPLOAD = 15 * 1024 * 1024


def sniff_image(data: bytes) -> str | None:
    """Đuôi theo nội dung thật (không tin tên file): .png / .jpg / .webp; None nếu không phải ảnh."""
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def waveform(path: Path, bins: int) -> tuple[list[float], float]:
    """Đỉnh biên độ (0–1) của WAV 16-bit chia thành tối đa `bins` đoạn, và độ dài (giây)."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise VidflowError(f"{path}: cần WAV 16-bit")
        frames, rate = w.getnframes(), w.getframerate()
        per = max(1, -(-frames // bins))
        peaks: list[float] = []
        while True:
            data = w.readframes(per)
            if not data:
                break
            a = array("h")
            a.frombytes(data[: len(data) // 2 * 2])
            peaks.append(round(max(max(a), -min(a)) / 32768, 3) if len(a) else 0.0)
    return peaks, round(frames / rate, 3)
```

Thêm 2 route trước `return router`:

```python
    @router.post("/api/quick/{name}/chars/{char_id}/image")
    def upload_char_image(name: str, char_id: str, file: UploadFile = File(...)):
        root = qroot(name)
        known = _do(lookup, root)
        if not CHAR_RE.match(char_id) or char_id not in known:
            raise HTTPException(404, f"Không có nhân vật @{char_id}")
        if not IMAGE_EXTS.get(Path(file.filename or "").suffix.lower()):
            raise HTTPException(422, "Chỉ nhận ảnh png, jpg hoặc webp.")
        data = file.file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, f"Ảnh quá {MAX_UPLOAD // (1024 * 1024)} MB.")
        ext = sniff_image(data)
        if ext is None:
            raise HTTPException(422, "File không phải ảnh png/jpg/webp.")
        tmp = root / "tmp" / f"upload-{char_id}{ext}"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        try:
            _do(chars.set_char_image, root, char_id, tmp, channel=known[char_id].scope == "channel")
        finally:
            tmp.unlink(missing_ok=True)
        return {"image_url": char_url(name, load_quick(root).preset, lookup(root).get(char_id))}

    @router.get("/api/quick/{name}/waveform")
    def waveform_ep(name: str, bins: int = Query(300, ge=20, le=2000)):
        voice = qroot(name) / ops.VOICE_FILE
        if not voice.is_file():
            return {"peaks": [], "duration": 0}
        peaks, duration = _do(waveform, voice, bins)
        return {"peaks": peaks, "duration": duration}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_quick.py tests/test_ui_auth.py tests/test_ui_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vidflow/ui/quick_api.py tests/test_ui_quick.py tests/test_ui_auth.py
git commit -m "feat(ui): tải ảnh nhân vật, sóng âm giọng đọc; test bắt đăng nhập mọi route mới"
```

---

### Task 8: Màn Bảng mốc — nền `quick.js`, bảng mốc, khung chi tiết sửa prompt tại chỗ (Model: sonnet)

**Files:**
- Create: `src/vidflow/ui/static/quick.js`
- Create: `scripts/seed_quick_demo.py`
- Modify: `src/vidflow/ui/static/app.js` (`loadProjects`, `openProject`, `render`, `save`, khởi động)
- Modify: `src/vidflow/ui/static/index.html` (nạp `quick.js`)
- Modify: `src/vidflow/ui/static/style.css` (thêm khối Bảng mốc)
- Test: `tests/test_ui_static.py`

**Interfaces:**
- Consumes: API Task 4–7; từ `app.js`: `h`, `api`, `toast`, `S` (`S.name`, `S.kind`, `S.job`, `S.projects`), `setCurrent`, `startPolling`, `openProject`, `loadProjects`.
- Produces (toàn cục trong `quick.js`): `Q` (`Q.open(name)`, `Q.render(opts?)`, `Q.name`, `Q.data`, `Q.screen`, `Q.sel`, `Q.drafts`, `Q.player`, `Q.wave`, `Q.exportOpts`), `QSCREENS` (màn tự đăng ký: `QSCREENS.board = qBoard`), `QNAV`, `QST`, `QJOB`, `QSTAGE`, `SCENE_COLORS`, `VIDEO_MODELS`, `IMAGE_MODELS`, hàm `fmtT(s)`, `fmtT1(s)`, `pad3(n)`, `qBeat(n)`, `qChar(id)`, `qPost(path, body)`, `qReload()`, `qJob(kind, {instruction, options, confirmText})`, `qSceneList(beats) -> [{beats, color, index}]`. Trong `app.js`: `S.kind ∈ {"full", "quick", null}`, `stopMedia()`.

- [ ] **Step 1: Write the failing test** — thêm vào cuối `tests/test_ui_static.py`:

```python
def test_quick_script_loaded_after_app():
    html = _read("index.html")
    assert html.index('src="/static/app.js"') < html.index('src="/static/quick.js"')
    js = _read("quick.js")
    assert "QSCREENS.board = qBoard" in js and "Lưu & kiểm duyệt" in js and "Duyệt tay" in js
    assert "qQuotaBanner" in js and "Nguồn: theo cài đặt" in js and "provider:" in js
    assert "j.quota_exhausted" in _read("app.js")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui_static.py::test_quick_script_loaded_after_app -v`
Expected: FAIL — `ValueError: substring not found`.

- [ ] **Step 3: Tạo `src/vidflow/ui/static/quick.js`**:

```js
"use strict";
// vidflow — quy trình nhanh: Bảng mốc · Nhân vật · Xem thử & Xuất · Tạo video nhanh (spec 2026-10-12, Giai đoạn 3).
// Dùng chung tiện ích của app.js (nạp trước): h, api, toast, S, setCurrent, startPolling, openProject, loadProjects.

const Q = {
  name: null, data: null, screen: "board", filter: "all", sel: null, fresh: false, provider: null,
  drafts: {}, reviewing: {}, timer: null, wave: null, player: null,
  exportOpts: { resolution: "1080p", transition: "scene", clip_fit: "trim", zoom: true, subtitles: true, logo: true, clip_audio: false, music: false },
};
const QSCREENS = {}; // id màn → hàm trả [vùng giữa, khung phải | null]; mỗi màn tự đăng ký
const QNAV = [["board", "Bảng mốc"], ["chars", "Nhân vật"], ["preview", "Xem thử & Xuất"]];
const QST = { ok: ["Có ảnh", "st-ok"], gen: ["Đang gen", "st-gen"], error: ["Lỗi", "st-error"], pending: ["Chờ", "st-pending"], redo: ["Gen lại", "st-redo"], blocked: ["Bị chặn", "st-blocked"] };
const QCLIP = { pending: "chưa gen", ok: "đã có clip", redo: "chờ gen lại", error: "lỗi" };
const QJOB = { running: "đang chạy", done: "xong", failed: "lỗi", stopped: "đã dừng" };
const QSTAGE = { new: "mới tạo", ideas: "chờ chọn ý tưởng", picked: "đã chọn ý tưởng", script: "đã có kịch bản", voiced: "đã có giọng đọc", prompted: "đã có prompt", imaged: "đủ ảnh", built: "đã dựng" };
const SCENE_COLORS = ["#3557D6", "#E09A2D", "#8B5E3C", "#2E8B6E", "#7A4FB5", "#0069ba"];
const PROVIDERS = [["flow", "Flow"], ["gemini", "Gemini"], ["aistudio", "AI Studio"]];
const VIDEO_MODELS = ["", "Veo 3.1 Lite", "Veo 3.1 Fast", "Veo 3.1 Quality", "Omni 1.1 Flash"];
const IMAGE_MODELS = ["Nano Banana 2"];
const FLOW_JOBS = { flow: "gen ảnh mốc", clips: "gen clip động", sheets: "gen character sheet" };
const QFILTERS = [
  ["all", "Tất cả", () => true],
  ["error", "Lỗi", b => b.state === "error" || b.clip.status === "error"],
  ["noimg", "Chưa có ảnh", b => b.state !== "ok"],
  ["blocked", "Bị chặn", b => b.state === "blocked"],
  ["clip", "Clip", b => b.clip.enabled],
  ["cont", "Nối cảnh", b => b.cont],
];

// ================= tiện ích =================
function fmtT(s) { if (s == null) return "--:--"; const m = Math.floor(s / 60), x = Math.floor(s % 60); return `${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}`; }
function fmtT1(s) { s = Math.max(0, s || 0); const m = Math.floor(s / 60); return `${String(m).padStart(2, "0")}:${(s - m * 60).toFixed(1).padStart(4, "0")}`; }
function pad3(n) { return String(n).padStart(3, "0"); }
function qBeat(n) { return (Q.data?.beats || []).find(b => b.n === n) || null; }
function qChar(id) { return (Q.data?.characters || []).find(c => c.id === id) || null; }
async function qPost(path, body) { return api(`/api/quick/${Q.name}${path}`, { method: "POST", body: JSON.stringify(body || {}) }); }
async function qReload() { Q.data = await api(`/api/quick/${Q.name}`); if (Q.data.job) S.job = Q.data.job; }
function provLabel(p) { return (PROVIDERS.find(x => x[0] === p) || [p, p || "Flow"])[1]; }
// nguồn gen cho việc gen: ô "Nguồn" (ghi đè một lần) hoặc cài đặt video (ảnh/sheet: image_provider; clip: video_provider)
function qProvider(kind) { const f = Q.data.quick.flow; return Q.provider || (kind === "clips" ? f.video_provider : f.image_provider) || "flow"; }

// ================= mở / vẽ =================
Q.open = async function (name) {
  if (Q.name !== name) Object.assign(Q, { name, screen: "board", filter: "all", sel: null, fresh: true, drafts: {}, reviewing: {} });
  Q.wave = null;
  try { await qReload(); } catch (e) { toast(e.message, true); return; }
  if (Q.fresh) { Q.sel = Q.data.beats.length ? Q.data.beats[0].n : null; Q.fresh = false; }
  if (Q.sel != null && !qBeat(Q.sel)) Q.sel = Q.data.beats.length ? Q.data.beats[0].n : null;
  Q.render();
  qAutoRefresh();
};
function qAutoRefresh() {
  clearInterval(Q.timer);
  Q.timer = setInterval(async () => {
    if (S.kind !== "quick" || S.name !== Q.name || !(Q.data?.job && Q.data.job.state === "running")) { clearInterval(Q.timer); return; }
    if (Q.screen === "preview") return; // không làm gián đoạn trình phát
    try { await qReload(); } catch { return; }
    Q.render({ keepPanel: true });
  }, 5000);
}
Q.render = function (opts = {}) {
  const d = Q.data; if (!d) return;
  document.getElementById("savebar").hidden = true;
  const main = document.getElementById("main");
  const oldPanel = opts.keepPanel ? main.querySelector(".panel") : null;
  const keep = oldPanel && oldPanel.contains(document.activeElement) ? oldPanel : null; // đang gõ trong khung phải → giữ nguyên
  if (!keep) main.querySelectorAll("audio, video").forEach(m => m.pause());
  setCurrent(d.preset.name, d.quick.title || d.name, [d.status.voice_s ? fmtT(d.status.voice_s) : null, `${d.beats.length} mốc`, d.aspect].filter(Boolean).join(" · "));
  document.getElementById("railNav").replaceChildren(qRail());
  const [center, panel] = (QSCREENS[Q.screen] || QSCREENS.board)();
  main.className = panel ? "app" : "app single";
  main.replaceChildren(...[center, panel ? (keep || panel) : null].filter(Boolean));
};
function qSteps() {
  const d = Q.data, st = d.status, b = st.beats;
  const idx = ["new", "ideas", "picked", "script", "voiced", "prompted", "imaged", "built"].indexOf(st.stage);
  const steps = [
    ["Ý tưởng", st.ideas ? `${st.ideas} ý` : "", idx >= 2],
    ["Kịch bản · mốc", b.total ? String(b.total) : "", idx >= 3 && b.total > 0],
    ["Giọng đọc", st.voice_s ? fmtT(st.voice_s) : "", b.total > 0 && b.timed],
    ["Prompt", b.total ? `${b.prompted}/${b.total}` : "", b.total > 0 && b.prompted === b.total],
    ["Ảnh · clip", b.total ? `${b.imaged}/${b.total}` : "", b.total > 0 && b.imaged === b.total],
    ["Xuất video", d.renders.length ? String(d.renders.length) : "", d.renders.length > 0],
  ];
  const now = steps.findIndex(s => !s[2]);
  return steps.map(([label, meta, done], i) => ({ label, meta, state: done ? "done" : i === now ? "now" : "todo" }));
}
function qRail() {
  const d = Q.data, missing = d.characters.filter(c => !c.image_url && c.uses > 0).length;
  const link = (id, label) => h("button", { class: "navlink" + (Q.screen === id ? " active" : ""), onclick: () => { Q.screen = id; Q.render(); } },
    label, id === "chars" && missing ? h("span", { class: "tag warn" }, `${missing} thiếu`) : null);
  return h("div", {},
    h("div", { class: "navlist" }, QNAV.filter(([id]) => QSCREENS[id]).map(([id, label]) => link(id, label))),
    h("div", { class: "psteps" }, h("span", { class: "eyebrow" }, "Tiến độ"),
      h("ol", {}, qSteps().map((s, i) => h("li", { class: s.state },
        h("span", { class: "pdot " + s.state }, s.state === "done" ? "✓" : String(i + 1)), h("span", { class: "plabel" }, s.label), h("span", { class: "pmeta" }, s.meta))))));
}

// ================= việc nền =================
async function qJob(kind, { instruction = "", options = null, confirmText = null } = {}) {
  const q = Q.data.quick;
  if (kind === "clips" && !q.flow.video_model) { toast("Chọn model clip trong Cài đặt trước.", true); Q.screen = "board"; Q.sel = null; Q.render(); return; }
  const gen = !!FLOW_JOBS[kind];
  if (gen && !confirm(`Sẽ ${FLOW_JOBS[kind]} trong ${provLabel(qProvider(kind))} (phiên Chrome đã đăng nhập, tốn lượt/tín dụng gói). Đừng thao tác Chrome khi đang chạy. Tiếp tục?`)) return;
  if (confirmText && !confirm(confirmText)) return;
  try {
    S.job = await qPost("/jobs", { kind, instruction, options: options || {}, provider: gen && Q.provider ? Q.provider : null });
    Q.data.job = S.job;
    toast(`Bắt đầu: ${S.job.label}`); Q.render(); startPolling(); qAutoRefresh();
  } catch (e) { toast(e.message, true); }
}
async function qStop() {
  if (!confirm("Dừng việc đang chạy? Ảnh/clip đã gen giữ nguyên.")) return;
  try { await qPost("/jobs/stop"); toast("Đã dừng"); } catch (e) { toast(e.message, true); }
  await Q.open(Q.name);
}
async function qRetryErrors() {
  try {
    const img = await qPost("/retry", { ns: null, clip: false });
    const clip = await qPost("/retry", { ns: null, clip: true });
    toast(`Đã đưa ${img.count + clip.count} mốc lỗi về hàng chờ`);
    await qReload();
    await qJob(img.count ? "flow" : "clips");
  } catch (e) { toast(e.message, true); }
}
async function qPick(n) {
  try { const r = await qPost("/pick", { n }); toast(`Đã chọn: ${r.title}`); } catch (e) { toast(e.message, true); }
  await Q.open(Q.name);
}

// ================= Bảng mốc — vùng giữa =================
function qCounts() {
  const c = { ok: 0, gen: 0, error: 0, pending: 0, redo: 0, blocked: 0 };
  for (const b of Q.data.beats) c[b.state]++;
  return c;
}
function qBoardHead() {
  const d = Q.data, c = qCounts(), total = d.beats.length || 1;
  const job = d.job && d.job.state === "running" ? d.job : null, busy = S.job?.state === "running";
  const errs = d.beats.filter(b => b.error).length + d.beats.filter(b => b.clip.status === "error").length;
  const clipTodo = d.beats.filter(b => b.clip.enabled && b.clip.status !== "ok").length;
  const seg = (k, color) => h("span", { style: `width:${(c[k] / total) * 100}%;background:${color}` });
  const provSel = h("select", { class: "prov-sel", "aria-label": "Nguồn gen (ghi đè một lần)" }, h("option", { value: "" }, "Nguồn: theo cài đặt"),
    PROVIDERS.map(([v, l]) => h("option", { value: v }, "Nguồn: " + l)));
  provSel.value = Q.provider || ""; provSel.onchange = () => { Q.provider = provSel.value || null; Q.render({ keepPanel: true }); };
  const stats = [["ok", "có ảnh"], ["gen", "đang gen"], ["error", "lỗi"], ["pending", "chờ"], ["redo", "gen lại"], ["blocked", "bị chặn"]];
  return h("header", { class: "qhead" }, h("h1", {}, "Bảng mốc"),
    h("div", { class: "qprog" },
      h("div", { class: "qstats" }, stats.map(([k, l]) => h("span", { class: "qstat " + k }, h("strong", {}, String(c[k])), " " + l))),
      h("div", { class: "qbar", role: "img", "aria-label": `${c.ok} trên ${d.beats.length} mốc có ảnh` },
        seg("ok", "var(--success)"), seg("gen", "var(--secondary)"), seg("error", "var(--error)"), seg("blocked", "var(--warn)"))),
    h("div", { class: "row" }, provSel,
      job ? h("button", { onclick: qStop }, "Tạm dừng")
        : h("button", { class: "primary", disabled: !d.beats.length || busy, onclick: () => qJob("flow") }, `Gen ảnh (${provLabel(qProvider("flow"))})`),
      errs ? h("button", { class: "danger", disabled: busy, onclick: qRetryErrors }, `Chạy lại ${errs} lỗi`) : null,
      clipTodo ? h("button", { class: "primary", disabled: busy, onclick: () => qJob("clips") }, `Gen ${clipTodo} clip (${provLabel(qProvider("clips"))})`) : null,
      h("button", { onclick: () => { Q.sel = null; Q.render(); } }, "Cài đặt")));
}
function qNext() {
  const d = Q.data, st = d.status, q = d.quick, busy = S.job?.state === "running";
  const btn = (label, fn, primary = true) => h("button", { class: primary ? "primary" : "", disabled: busy, onclick: fn }, label);
  const box = (title, text, ...actions) => h("div", { class: "card next-card" }, h("h3", {}, title), text ? h("p", { class: "hint" }, text) : null, h("div", { class: "row" }, actions));
  if (st.stage === "new") return box("Bước 1 · Ý tưởng", "AI đề xuất 5 ý tưởng theo brief của bộ kênh.",
    btn("Đề xuất 5 ý tưởng", () => qJob("ideas", { instruction: q.title ? `Chủ đề người dùng gợi ý: ${q.title}` : "" })));
  if (st.stage === "ideas") return h("div", { class: "card next-card" }, h("h3", {}, "Bước 1 · Chọn một ý tưởng"),
    h("ol", { class: "ideas" }, q.ideas.map((it, i) => h("li", {}, h("div", { class: "idea" },
      h("div", {}, h("b", {}, it.title), it.hook ? h("p", { class: "hint" }, it.hook) : null, it.why_viral ? h("p", { class: "hint" }, "Vì sao: " + it.why_viral) : null),
      h("button", { class: "primary small", disabled: busy, onclick: () => qPick(i + 1) }, "Chọn"))))),
    h("div", { class: "row" }, btn("Đề xuất lại", () => qJob("ideas"), false)));
  if (st.stage === "picked") return box("Bước 2 · Kịch bản", `Ý tưởng: ${st.picked_title}. AI viết lời dẫn, tách mốc và đề xuất nhân vật riêng.`, btn("Viết kịch bản + tách mốc", () => qJob("script")));
  if (st.stage === "script") return box("Bước 3 · Giọng đọc", "Đọc từng mốc bằng Gemini TTS (gói miễn phí) và điền thời gian.", btn("Tạo giọng đọc", () => qJob("voice")));
  if (st.beats.prompted < st.beats.total) return box("Bước 4 · Prompt", `${st.beats.prompted}/${st.beats.total} mốc có prompt đạt kiểm duyệt.`, btn("Viết prompt ảnh + clip", () => qJob("prompts")));
  if (st.chars_missing.length) return box("Nhân vật thiếu ảnh", `${st.chars_missing.map(c => "@" + c).join(", ")} chưa có character sheet — ${st.blocked} mốc đang bị chặn.`,
    btn(`Gen sheet (${provLabel(qProvider("sheets"))})`, () => qJob("sheets")), QSCREENS.chars ? btn("Mở Nhân vật", () => { Q.screen = "chars"; Q.render(); }, false) : null);
  return null;
}
function qFilters() {
  return h("div", { class: "seg-group", role: "group", "aria-label": "Lọc mốc" }, QFILTERS.map(([k, label, fn]) =>
    h("button", { class: Q.filter === k ? "on" : "", "aria-pressed": Q.filter === k ? "true" : "false", onclick: () => { Q.filter = k; Q.render({ keepPanel: true }); } },
      label, " ", h("span", { class: "mono count" }, String(Q.data.beats.filter(fn).length)))));
}
function qSceneList(beats) {
  const scenes = [];
  for (const b of beats) {
    if (!b.cont || !scenes.length) scenes.push({ beats: [] });
    scenes[scenes.length - 1].beats.push(b);
  }
  scenes.forEach((s, i) => {
    const lead = s.beats.flatMap(b => b.refs).map(qChar).find(c => c && c.color);
    s.color = lead ? lead.color : SCENE_COLORS[i % SCENE_COLORS.length];
    s.index = i + 1;
  });
  return scenes;
}
function qRefChip(id) {
  const c = qChar(id)?.color || "#4A4F6E";
  return h("span", { class: "ref mono", style: `background:${c}1F;color:color-mix(in srgb, ${c} 70%, #0E1238)` }, "@" + id);
}
function qThumbLabel(b) {
  return { gen: "Flow đang vẽ…", error: "Flow từ chối prompt", blocked: "Bị chặn: " + (b.blocked || ""), redo: "Chờ gen lại",
    pending: b.blocked ? "Chờ: " + b.blocked : b.prompt ? "Chưa có ảnh" : "Chưa có prompt" }[b.state] || "";
}
function qCard(b, color) {
  const [label, cls] = QST[b.state];
  const clipTag = b.clip.enabled ? h("span", { class: "cliptag" }, b.clip.status === "ok" ? "CLIP" : b.clip.status === "error" ? "CLIP lỗi" : "CLIP chờ") : null;
  return h("div", { class: "beat-wrap" },
    b.cont ? h("span", { class: "contline", title: "Nối cảnh với mốc trước", style: `background:${color}` }) : null,
    h("button", { class: "beat" + (Q.sel === b.n ? " sel" : "") + (b.state === "error" ? " err" : ""), "aria-pressed": Q.sel === b.n ? "true" : "false", onclick: () => { Q.sel = b.n; Q.render(); } },
      h("div", { class: "thumb" }, b.image_url ? h("img", { src: b.image_url, alt: `Ảnh mốc ${b.n}`, loading: "lazy" }) : h("span", { class: "thumb-ph" }, qThumbLabel(b))),
      h("div", { class: "beat-body" },
        h("div", { class: "beat-meta" }, h("span", { class: "mono bn" }, pad3(b.n)), h("span", { class: "mono bt" }, fmtT(b.start)), b.image_url && b.provider ? h("span", { class: "prov" }, provLabel(b.provider)) : null, h("span", { class: "grow" }), clipTag, h("span", { class: "st " + cls }, label)),
        h("div", { class: "beat-text" }, b.text),
        h("div", { class: "refs-row" }, b.refs.map(qRefChip)))));
}
function qScenes() {
  const fn = QFILTERS.find(f => f[0] === Q.filter)[2];
  const out = qSceneList(Q.data.beats).map(sc => {
    const shown = sc.beats.filter(fn);
    if (!shown.length) return null;
    const first = sc.beats[0], last = sc.beats[sc.beats.length - 1];
    return h("section", { class: "scene-sec" },
      h("div", { class: "scene-h" }, h("span", { class: "swatch", style: `background:${sc.color}` }), h("h2", {}, `Cảnh ${sc.index}`),
        h("span", { class: "mono muted" }, `${pad3(first.n)}–${pad3(last.n)} · ${fmtT(first.start)}`), h("span", { class: "rule" })),
      h("div", { class: "beats-row" }, shown.map(b => qCard(b, sc.color))));
  }).filter(Boolean);
  return out.length ? h("div", { class: "scenes" }, out) : h("p", { class: "hint" }, "Không có mốc nào khớp bộ lọc.");
}
function qQuotaBanner() {
  const j = Q.data.job;
  if (!j || !j.quota_exhausted) return null;
  return h("div", { class: "notice warn banner", role: "alert" }, h("strong", {}, `Hết lượt ở ${provLabel(j.provider)}. `),
    "Chọn nguồn khác ở ô “Nguồn” phía trên (Flow, Gemini hoặc AI Studio) rồi bấm Gen lại, hoặc đổi nguồn mặc định trong Cài đặt.");
}
function qBoard() {
  const d = Q.data, job = d.job;
  const center = h("section", { class: "content" }, qBoardHead(), qQuotaBanner(), qNext(),
    d.beats.length ? qFilters() : null, d.beats.length ? qScenes() : h("p", { class: "hint" }, "Chưa có mốc — làm theo thẻ Bước tiếp theo ở trên."),
    job ? h("details", { class: "joblog", open: job.state !== "done" }, h("summary", {}, `${job.label} · ${QJOB[job.state] || job.state}`),
      h("pre", { class: "log", id: "log" }, job.log || "(đang chạy…)")) : null);
  return [center, qPanel()];
}

// ================= Bảng mốc — khung phải =================
function qPanel() {
  const b = Q.sel != null ? qBeat(Q.sel) : null;
  return h("aside", { class: "panel", "aria-label": b ? `Chi tiết mốc ${b.n}` : "Cài đặt video" }, b ? qDetail(b) : qSettings());
}
function qReviewLabel(rv, key) {
  if (Q.reviewing[key]) return h("span", { class: "rv busy" }, "Đang kiểm duyệt…");
  if (!rv) return h("span", { class: "rv none" }, "Chưa kiểm duyệt");
  if (rv.verdict === "override") return h("span", { class: "rv ok" }, "Duyệt tay");
  return h("span", { class: "rv " + (rv.verdict === "pass" ? "ok" : "bad") }, `${rv.verdict === "pass" ? "Đạt" : "Trượt"} · ${rv.score}/10`);
}
function qIssues(rv) { return rv && rv.verdict === "fail" && rv.issues.length ? h("ul", { class: "issues-list" }, rv.issues.map(x => h("li", {}, x))) : null; }
function qDraft(b, kind) { const k = `${b.n}:${kind}`; return k in Q.drafts ? Q.drafts[k] : (kind === "clip" ? b.clip.prompt : b.prompt); }
function qAttach(a) {
  const pic = a.url ? h("img", { src: a.url, alt: "" }) : h("span", { class: "att-ph" });
  if (a.kind === "prev") return h("span", { class: "att prev" }, pic, h("span", {}, `Ảnh mốc ${pad3(a.n)} · nối cảnh${a.url ? "" : " (chưa có)"}`));
  return h("span", { class: "att" + (a.url ? "" : " missing") }, pic, h("span", { class: "mono" }, "@" + a.id), a.url ? null : h("span", { class: "st st-blocked" }, "Thiếu ảnh"));
}
function qDetail(b) {
  const d = Q.data, q = d.quick, [label, cls] = QST[b.state], busy = S.job?.state === "running";
  const imgTa = h("textarea", { class: "prompt-area", rows: 6, "aria-label": "Prompt ảnh" });
  imgTa.value = qDraft(b, "img"); imgTa.oninput = () => { Q.drafts[`${b.n}:img`] = imgTa.value; };
  const clipOn = h("input", { type: "checkbox", "aria-label": "Làm clip động" });
  clipOn.checked = b.clip.enabled; clipOn.onchange = () => qToggleClip(b.n, clipOn.checked);
  let clipBlock = null;
  if (b.clip.enabled) {
    const clipTa = h("textarea", { class: "prompt-area", rows: 4, "aria-label": "Prompt clip" });
    clipTa.value = qDraft(b, "clip"); clipTa.oninput = () => { Q.drafts[`${b.n}:clip`] = clipTa.value; };
    clipBlock = h("div", { class: "clip-inner" },
      h("div", { class: "lbl" }, h("span", { class: "eyebrow" }, "Prompt clip"), qReviewLabel(b.clip.review, `${b.n}:clip`)), clipTa, qIssues(b.clip.review),
      b.clip.error ? h("p", { class: "notice err" }, "Flow từ chối clip: " + b.clip.error) : null,
      b.clip_url ? h("video", { src: b.clip_url, controls: true, preload: "metadata", class: "clip-prev" }) : null,
      h("span", { class: "hint" }, `${provLabel(q.flow.video_provider)} · ${q.flow.video_model || "Chưa chọn model clip"} · ${q.flow.resolution} · gen từ ảnh mốc này · ${d.status.clips.enabled}/${q.max_clips} clip đã chọn · ${QCLIP[b.clip.status]}${b.clip.provider ? " · clip gen bằng " + provLabel(b.clip.provider) : ""}`),
      h("div", { class: "row" },
        h("button", { class: "small", onclick: () => qOverride(b.n, true) }, "Duyệt tay"),
        b.clip.status === "ok" ? h("button", { class: "small", onclick: () => qRedo(b.n, true) }, "Gen lại clip") : null,
        h("button", { class: "small secondary", disabled: !!Q.reviewing[`${b.n}:clip`], onclick: () => qSaveReview(b.n, true) }, "Lưu & kiểm duyệt clip")));
  }
  return h("div", { class: "detail" },
    h("div", { class: "detail-h" }, h("h2", {}, `Mốc ${pad3(b.n)}`), h("span", { class: "mono muted" }, `${fmtT(b.start)} → ${fmtT(b.end)}`), h("span", { class: "grow" }), h("span", { class: "st " + cls }, label)),
    h("p", { class: "quote" }, `“${b.text}”`),
    b.image_url ? h("img", { class: "detail-img", src: b.image_url, alt: `Ảnh mốc ${b.n}` }) : null,
    b.image_url && b.provider ? h("span", { class: "hint" }, "Ảnh gen bằng " + provLabel(b.provider)) : null,
    b.error ? h("p", { class: "notice err" }, "Flow từ chối ảnh: " + b.error) : null,
    b.blocked && b.state !== "ok" ? h("p", { class: "notice warn" }, (b.state === "blocked" ? "Bị chặn: " : "Chờ: ") + b.blocked) : null,
    h("div", { class: "group" }, h("span", { class: "eyebrow" }, "Ảnh đính kèm khi gen"),
      b.attach.length ? h("div", { class: "attach" }, b.attach.map(qAttach)) : h("span", { class: "hint" }, "Không đính ảnh nào")),
    h("label", { class: "group" }, h("span", { class: "lbl" }, h("span", { class: "eyebrow" }, "Prompt ảnh"), qReviewLabel(b.review, `${b.n}:img`)), imgTa),
    qIssues(b.review),
    h("div", { class: "clipbox" }, h("label", { class: "switch" }, h("span", {}, "Làm clip động"), clipOn), clipBlock),
    h("div", { class: "actions" },
      h("button", { disabled: b.status !== "ok", onclick: () => qRedo(b.n, false) }, "Gen lại ảnh"),
      h("button", { disabled: busy, onclick: () => qJob("prompts", { instruction: `Chỉ viết lại prompt ảnh (và prompt clip nếu bật) của mốc ${b.n}; không đụng mốc khác.`, confirmText: `AI sẽ viết lại prompt mốc ${b.n}. Tiếp tục?` }) }, "AI viết lại"),
      h("button", { onclick: () => qOverride(b.n, false) }, "Duyệt tay"),
      h("button", { class: "secondary grow", disabled: !!Q.reviewing[`${b.n}:img`], onclick: () => qSaveReview(b.n, false) }, "Lưu & kiểm duyệt")));
}
function qSettings() {
  const q = Q.data.quick, f = { ...q.flow, max_clips: q.max_clips, allow_cont: q.allow_cont };
  const sel = (key, opts) => {
    const all = [...new Set([...opts, f[key] ?? ""])];
    const s = h("select", {}, all.map(o => h("option", { value: o }, o || "— chọn —")));
    s.value = f[key] ?? ""; s.onchange = () => { f[key] = s.value; }; return s;
  };
  const psel = key => { const s = h("select", {}, PROVIDERS.map(([v, l]) => h("option", { value: v }, l))); s.value = f[key] || "flow"; s.onchange = () => { f[key] = s.value; }; return s; };
  const max = h("input", { type: "number", min: 0, max: 200 }); max.value = f.max_clips; max.oninput = () => { f.max_clips = Number(max.value); };
  const cont = h("input", { type: "checkbox" }); cont.checked = f.allow_cont; cont.onchange = () => { f.allow_cont = cont.checked; };
  const save = async () => {
    if (f.max_clips > 0 && !f.video_model) { toast("Chọn model clip (bắt buộc khi số clip > 0).", true); return; }
    try {
      await qPost("/settings", { image_model: f.image_model, video_model: f.video_model, resolution: f.resolution, image_provider: f.image_provider || "flow", video_provider: f.video_provider || "flow", max_clips: f.max_clips, allow_cont: f.allow_cont });
      toast("Đã lưu cài đặt"); await qReload(); Q.render();
    } catch (e) { toast(e.message, true); }
  };
  return h("div", { class: "detail" }, h("h2", {}, "Cài đặt video"), h("p", { class: "hint" }, "Bấm một mốc trên bảng để xem chi tiết."),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Model ảnh"), sel("image_model", IMAGE_MODELS)),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Model clip động"), sel("video_model", VIDEO_MODELS)),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Độ phân giải clip"), sel("resolution", ["720p", "1080p"])),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Nguồn gen ảnh (và sheet)"), psel("image_provider")),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Nguồn gen clip"), psel("video_provider")),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Số clip tối đa (0 = chỉ ảnh)"), max),
    h("label", { class: "checks" }, cont, "Cho phép nối cảnh"),
    h("button", { class: "primary", onclick: save }, "Lưu cài đặt"));
}
async function qSaveReview(n, clip) {
  const key = `${n}:${clip ? "clip" : "img"}`, b = qBeat(n), saved = clip ? b.clip.prompt : b.prompt;
  const text = (key in Q.drafts ? Q.drafts[key] : saved).trim();
  if (!text) { toast("Prompt rỗng.", true); return; }
  try { if (text !== saved) await qPost("/prompt", { n, prompt: text, clip }); } catch (e) { toast(e.message, true); return; }
  delete Q.drafts[key];
  Q.reviewing[key] = true;
  await qReload(); Q.render();
  try {
    const r = await qPost("/review", { n, clip });
    toast(`Mốc ${n}: ${r.review.verdict === "pass" ? "đạt" : "trượt"} ${r.review.score}/10`, r.review.verdict !== "pass");
  } catch (e) { toast(e.message, true); }
  delete Q.reviewing[key];
  await qReload(); Q.render();
}
async function qOverride(n, clip) {
  const key = `${n}:${clip ? "clip" : "img"}`, b = qBeat(n), saved = clip ? b.clip.prompt : b.prompt;
  if (!confirm(`Duyệt tay prompt ${clip ? "clip" : "ảnh"} mốc ${n} (cho phép gen dù chưa đạt kiểm duyệt)?`)) return;
  try {
    const text = key in Q.drafts ? Q.drafts[key].trim() : "";
    if (text && text !== saved) await qPost("/prompt", { n, prompt: text, clip });
    delete Q.drafts[key];
    await qPost("/override", { n, clip }); toast(`Mốc ${n}: đã duyệt tay`);
  } catch (e) { toast(e.message, true); }
  await qReload(); Q.render();
}
async function qRedo(n, clip) {
  try { await qPost("/redo", { ns: [n], clip }); toast(`Mốc ${n}: chờ gen lại ${clip ? "clip" : "ảnh"}`); } catch (e) { toast(e.message, true); }
  await qReload(); Q.render();
}
async function qToggleClip(n, on) {
  try { await qPost("/clip", { ns: [n], on }); } catch (e) { toast(e.message, true); }
  await qReload(); Q.render();
}
QSCREENS.board = qBoard;
```

- [ ] **Step 4: Nạp `quick.js`** — trong `src/vidflow/ui/static/index.html` thêm ngay sau `<script src="/static/app.js"></script>`:

```html
<script src="/static/quick.js"></script>
```

- [ ] **Step 5: Định tuyến project nhanh trong `app.js`**

Thay nguyên hàm `loadProjects` bằng:

```js
async function loadProjects() {
  const [full, quick] = await Promise.all([api("/api/projects"), api("/api/quick")]);
  S.projects = [...full.map(p => ({ ...p, kind: "full" })), ...quick.map(p => ({ ...p, kind: "quick" }))];
  const sel = document.getElementById("projectSel");
  const opt = p => h("option", { value: p.name }, `${p.title} (${p.name})`);
  sel.replaceChildren(...[h("option", { value: "" }, S.projects.length ? "Chọn video" : "Chưa có video"),
    quick.length ? h("optgroup", { label: "Video nhanh" }, S.projects.filter(p => p.kind === "quick").map(opt)) : null,
    full.length ? h("optgroup", { label: "Video chi tiết" }, S.projects.filter(p => p.kind === "full").map(opt)) : null].filter(Boolean));
  sel.value = S.name || "";
}
```

Thay nguyên hàm `openProject` bằng:

```js
function stopMedia() { document.querySelectorAll("#main audio, #main video").forEach(m => m.pause()); }
async function openProject(name, jumpToCurrent = false) {
  if (S.dirty && !confirm("Có thay đổi chưa lưu. Bỏ qua?")) { document.getElementById("projectSel").value = S.name || ""; return; }
  stopMedia();
  S.name = name; S.dirty = false; S.focus = null; S.sugg = null;
  S.kind = name ? (S.projects.find(p => p.name === name)?.kind || "full") : null;
  document.getElementById("projectSel").value = name || "";
  document.getElementById("dirtyMark").textContent = "";
  if (!name) { S.data = null; history.replaceState(null, "", location.pathname); render(); return; }
  location.hash = name;
  if (S.kind === "quick") { S.data = null; await Q.open(name); return; }
  S.data = await api(`/api/projects/${name}`);
  if (jumpToCurrent) S.step = currentStep().id;
  render();
}
```

Trong `render()` chèn làm dòng đầu tiên của thân hàm:

```js
  if (S.name && S.kind === "quick") { document.getElementById("savebar").hidden = true; Q.render(); return; }
```

Trong `startPolling()` thay dòng
`if (j.state === "done") toast(\`Xong: ${j.label}\`); else if (j.state === "failed") toast(\`Lỗi: ${j.label} — xem log bên phải\`, true);`
bằng (báo hết lượt nguồn gen):

```js
      const prov = { flow: "Flow", gemini: "Gemini", aistudio: "AI Studio" }[j.provider] || j.provider || "nguồn gen";
      if (j.quota_exhausted) toast(`Hết lượt ở ${prov} — chọn nguồn khác trên Bảng mốc rồi chạy lại.`, true);
      else if (j.state === "done") toast(`Xong: ${j.label}`); else if (j.state === "failed") toast(`Lỗi: ${j.label} — xem log bên phải`, true);
```

Trong `save()` đổi dòng `if (!S.name) return;` thành:

```js
  if (!S.name || S.kind === "quick") return;
```

Thay khối khởi động ở CUỐI file (7 dòng, bắt đầu bằng dòng `(async () => {` ở cột đầu và kết thúc bằng `})();` — không nhầm với `setInterval(async () => {` trong `startPolling`) bằng:

```js
document.addEventListener("DOMContentLoaded", async () => {
  await loadProjects();
  const want = decodeURIComponent(location.hash.slice(1));
  if (want && S.projects.some(p => p.name === want)) await openProject(want, true); else render();
  const j = await api("/api/jobs/current").catch(() => null);
  if (j && j.state === "running") { S.job = j; startPolling(); }
});
```

- [ ] **Step 6: Kiểu Bảng mốc** — thêm vào cuối `src/vidflow/ui/static/style.css`:

```css
/* ===== Quy trình nhanh — Bảng mốc ===== */
.qhead{display:flex;flex-wrap:wrap;align-items:center;gap:16px;padding:0 0 16px;margin-bottom:16px;border-bottom:1px solid var(--line)}
.qhead h1,.page-h{margin:0;font-size:22px;font-weight:800;letter-spacing:-.4px}
.qprog{flex:1 1 280px;min-width:0;display:flex;flex-direction:column;gap:6px}
.qstats{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--muted)}
.qstats strong{color:var(--text)}
.qstat.ok strong{color:var(--success-text)}.qstat.gen strong{color:var(--secondary)}.qstat.error strong{color:var(--error)}.qstat.blocked strong{color:var(--warn)}
.qbar{height:6px;border-radius:999px;background:var(--track);display:flex;overflow:hidden}
.next-card .ideas{margin:0 0 12px;padding-left:20px;display:flex;flex-direction:column;gap:10px}
.idea{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.idea p{margin:2px 0 0}
.seg-group{display:flex;flex-wrap:wrap;gap:4px;padding:4px;border-radius:10px;background:var(--track);width:max-content;max-width:100%;margin-bottom:18px}
.seg-group button{border:none;background:transparent;color:var(--muted);min-height:34px;font-size:13px;padding:0 12px;border-radius:7px}
.seg-group button.on{background:var(--surface);color:var(--primary);box-shadow:0 1px 3px rgba(14,18,56,.12)}
.seg-group .count{font-size:12px;opacity:.75}
.scenes{display:flex;flex-direction:column;gap:22px}
.scene-h{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.scene-h h2{margin:0;font-size:15px;font-weight:700}
.swatch{display:inline-block;flex:none;width:12px;height:12px;border-radius:3px}
.rule{flex:1;height:1px;background:var(--line)}
.beats-row{display:flex;flex-wrap:wrap;gap:10px;align-items:stretch}
.beat-wrap{display:flex;align-items:center}
.contline{flex:none;width:14px;height:2px;margin-left:-10px}
.beat{display:block;width:196px;min-height:0;padding:0;text-align:left;font-weight:400;border-radius:8px;overflow:hidden;border:1px solid var(--line);background:var(--surface);color:inherit}
.beat.sel{border:2px solid var(--primary);box-shadow:0 6px 18px rgba(0,0,128,.16)}
.beat.err{border-color:#E59AA7}
.beat .thumb{aspect-ratio:16/9;background:var(--page);display:grid;place-items:center;overflow:hidden}
.beat .thumb img{width:100%;height:100%;object-fit:cover;display:block}
.thumb-ph{font-size:11px;color:var(--muted);padding:6px;text-align:center}
.beat-body{padding:9px 10px 10px;display:flex;flex-direction:column;gap:7px}
.beat-meta{display:flex;align-items:center;gap:6px}
.bn{font-size:11px;font-weight:600}.bt{font-size:11px;color:var(--muted-2)}
.cliptag{font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;background:var(--primary);color:#fff;letter-spacing:.4px}
.beat-text{font-size:12.5px;line-height:1.4;color:#2A2F52;height:35px;overflow:hidden}
.refs-row{display:flex;flex-wrap:wrap;gap:4px;min-height:18px}
.ref{font-size:10.5px;padding:1px 6px;border-radius:4px}
.st{display:inline-block;font-size:10.5px;font-weight:600;padding:2px 7px;border-radius:999px;white-space:nowrap}
.st-ok{background:var(--success-bg);color:var(--success-text)}.st-gen{background:var(--info-bg);color:var(--info-text)}
.st-error{background:var(--error-bg);color:var(--error-text)}.st-pending{background:var(--track);color:var(--muted)}
.st-redo,.st-blocked{background:var(--warn-bg);color:var(--warn)}
details.joblog{margin-top:22px}
.prov-sel{width:auto;min-width:180px}
.prov{font-family:var(--mono);font-size:10px;color:var(--muted-2)}
.banner{margin-bottom:16px}
.panel .detail{display:flex;flex-direction:column;gap:14px}
.detail-h{display:flex;align-items:baseline;gap:10px}
.detail-h h2,.detail>h2{margin:0;font-size:18px;font-weight:800}
.quote{margin:0;font-size:15px;line-height:1.5}
.detail-img{width:100%;border-radius:8px;border:1px solid var(--line)}
.group{display:flex;flex-direction:column;gap:6px}
.lbl{display:flex;justify-content:space-between;align-items:center;gap:8px}
.attach{display:flex;flex-wrap:wrap;gap:8px}
.att{display:flex;align-items:center;gap:8px;padding:4px 10px 4px 4px;border-radius:8px;border:1px solid var(--line);font-size:12px}
.att.prev{border-style:dashed;border-color:#A3B4A2}
.att.missing{border-color:var(--warn-line);background:var(--warn-bg)}
.att img,.att-ph{flex:none;width:30px;height:30px;border-radius:6px;object-fit:cover;background:var(--track)}
.prompt-area{font-family:var(--mono);font-size:11.5px;line-height:1.5}
.rv{font-size:12px;font-weight:600}.rv.ok{color:var(--success-text)}.rv.bad{color:var(--error)}.rv.none{color:var(--muted)}.rv.busy{color:var(--secondary)}
.issues-list{margin:0;padding-left:18px;color:var(--warn);font-size:12px}
.clipbox{display:flex;flex-direction:column;gap:10px;padding:12px;border-radius:10px;background:var(--clip-bg);border:1px solid var(--clip-line)}
.switch{display:flex;align-items:center;justify-content:space-between;gap:10px;font-weight:600}
.switch input{width:20px;height:20px}
.clip-inner{display:flex;flex-direction:column;gap:8px}
.clip-prev{width:100%;border-radius:8px;background:#000}
.notice{margin:0;padding:8px 10px;border-radius:8px;font-size:13px}
.notice.err{background:var(--error-bg);color:var(--error-text)}.notice.warn{background:var(--warn-bg);color:var(--warn)}
.actions{display:flex;flex-wrap:wrap;gap:8px}
.actions button{min-height:44px}
```

- [ ] **Step 7: Script tạo project thử** — tạo `scripts/seed_quick_demo.py`:

```python
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
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_static.py -v && uv run python scripts/seed_quick_demo.py`
Expected: PASS (gồm `test_js_syntax[quick.js]`, `test_no_emoji_in_ui`); script in "Đã tạo …/projects/ui-demo" và dòng "10 mốc · … có ảnh 5 …", "Bị chặn: …".

- [ ] **Step 9: Kiểm tra tay**

Run: `uv run vidflow ui --port 8788 --no-open`, đăng nhập, chọn "Video nhanh › Ngày thường 50.000 năm trước (ui-demo)". Thấy:
- Thanh trái: ô "Giải mã bản thân…", tựa, `00:40 · 10 mốc · 16:9`; mục "Bảng mốc" nền navy; danh sách Tiến độ 6 bước với ✓ xanh ở bước đã xong và chấm navy ở "Ảnh · clip".
- Đầu trang: "Bảng mốc", số "5 có ảnh · 0 đang gen · 1 lỗi · … bị chặn", thanh tiến độ; ô "Nguồn: theo cài đặt", nút "Gen ảnh (Flow)", "Chạy lại 1 lỗi", "Gen 1 clip (Flow)", "Cài đặt". Bấm "Gen ảnh (Flow)" → hộp xác nhận tín dụng → bấm **Hủy**.
- Thẻ "Nhân vật thiếu ảnh" nêu @FARMER.
- Bộ lọc: Tất cả 10, Lỗi 1, Chưa có ảnh 5, Bị chặn 3, Clip 1, Nối cảnh 4; bấm "Bị chặn" → chỉ mốc 007, 008, 010.
- Mốc gom thành cảnh (Cảnh 1: 001–003 có vạch nối giữa thẻ; màu ô vuông cảnh 3 là màu @ANCESTOR); thẻ có ảnh, số mốc, giờ, lời đọc, chip `@ANCESTOR` chữ mono, nhãn "CLIP" ở mốc 002, nhãn trạng thái bằng chữ (Có ảnh / Lỗi / Bị chặn / Chờ).
- Bấm mốc 003: khung phải hiện "Ảnh đính kèm khi gen: Ảnh mốc 002 · nối cảnh", prompt ảnh mono, nhãn "Đạt · 7.5/10". Bấm mốc 006: "Trượt · 5/10" và gợi ý sửa màu cam. Sửa prompt mốc 006 (giữ nguyên câu neo đầu/cuối), bấm **Duyệt tay** → OK → nhãn "Duyệt tay". Bấm mốc 007: cảnh báo "Bị chặn: thiếu ảnh @FARMER", chip @FARMER "Thiếu ảnh".
- Bấm mốc 002: ô "Làm clip động" đã bật, prompt clip, video xem trước (nếu có ffmpeg), dòng "Veo 3.1 Lite · 720p · … 1/3 clip đã chọn". Tắt rồi bật lại công tắc → thẻ mốc mất rồi có lại nhãn CLIP.
- Bấm "Cài đặt": khung phải đổi thành "Cài đặt video" (có "Nguồn gen ảnh (và sheet)", "Nguồn gen clip"); đặt số clip 0 → Lưu → toast "Đã lưu cài đặt"; đặt lại 3; đổi nguồn ảnh sang Gemini → Lưu → nút đầu trang đổi thành "Gen ảnh (Gemini)". Ô "Nguồn" đầu trang chọn "Nguồn: AI Studio" → nút thành "Gen ảnh (AI Studio)", bấm → hộp xác nhận nói "trong AI Studio" → **Hủy**; trả ô về "theo cài đặt".
- Hết lượt (giả lập, không tốn lượt): trong DevTools Console gõ `Q.data.job = {label: "Gen ảnh mốc", state: "failed", provider: "gemini", quota_exhausted: true, log: "hết lượt ở gemini"}; Q.render()` → dưới đầu trang hiện băng cảnh báo "Hết lượt ở Gemini. Chọn nguồn khác…".
- Thẻ mốc có ảnh không hiện nhãn nguồn (dữ liệu seed chưa có `provider`); nếu project thật đã gen bằng Gemini, thẻ hiện "Gemini" chữ mono nhỏ cạnh giờ và khung chi tiết ghi "Ảnh gen bằng Gemini".
- (Tùy chọn, dùng Claude chứ không dùng Flow) mốc 004: sửa một từ trong prompt, bấm **Lưu & kiểm duyệt** → nhãn "Đang kiểm duyệt…" → sau vài chục giây hiện "Đạt/Trượt · điểm".
- Chọn lại một project chi tiết từ ô chọn video: quy trình 7 bước hiển thị bình thường; Cmd+S vẫn lưu.

- [ ] **Step 10: Commit**

```bash
git add src/vidflow/ui/static/quick.js src/vidflow/ui/static/app.js src/vidflow/ui/static/index.html src/vidflow/ui/static/style.css scripts/seed_quick_demo.py tests/test_ui_static.py
git commit -m "feat(ui): màn Bảng mốc quy trình nhanh — lọc, gom cảnh, sửa prompt + kiểm duyệt tại chỗ"
```

---

### Task 9: Màn Nhân vật (Model: sonnet)

**Files:**
- Modify: `src/vidflow/ui/static/quick.js` (thêm cuối file)
- Modify: `src/vidflow/ui/static/style.css` (thêm khối Nhân vật)
- Test: `tests/test_ui_static.py`

**Interfaces:**
- Consumes: `Q`, `QSCREENS`, `qReload`, `qJob`, `qPost`, `provLabel`, `qProvider` (Task 8); API `POST /chars/{id}/image` (multipart `file`), `POST /chars/{id}/promote`; `char_list` (`{id, name, desc, color, scope, uses, blocked, image_url}`).
- Produces: `qChars() -> [center, null]`, `qCharCard(c)`, `qUpload(id, file)`, `qPromote(id)`; đăng ký `QSCREENS.chars = qChars`.

- [ ] **Step 1: Write the failing test** — thêm vào cuối `tests/test_ui_static.py`:

```python
def test_quick_chars_screen_registered():
    js = _read("quick.js")
    assert "QSCREENS.chars = qChars" in js and 'qJob("sheets")' in js and "Đưa vào bộ kênh" in js
    assert "Gen sheet (${provLabel(qProvider(\"sheets\"))})" in js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui_static.py::test_quick_chars_screen_registered -v`
Expected: FAIL — `AssertionError`.

- [ ] **Step 3: Thêm vào cuối `src/vidflow/ui/static/quick.js`**:

```js
// ================= Nhân vật =================
function qChars() {
  const d = Q.data;
  const group = (scope, title, sub, empty) => {
    const list = d.characters.filter(c => c.scope === scope);
    return h("section", { class: "char-group" },
      h("div", { class: "scene-h" }, h("h2", {}, title), h("span", { class: "muted" }, sub), h("span", { class: "rule" })),
      list.length ? h("div", { class: "chars-grid" }, list.map(qCharCard)) : h("p", { class: "hint" }, empty));
  };
  return [h("section", { class: "content" },
    h("header", { class: "qhead" }, h("div", {}, h("h1", {}, "Nhân vật"),
      h("p", { class: "hint" }, "Prompt nhắc ", h("span", { class: "mono" }, "@TÊN"), " thì ảnh nhân vật đó được đính kèm khi gen trong Flow. Nhân vật chưa có ảnh sẽ chặn các mốc dùng nó."))),
    group("channel", "Của bộ kênh", `${d.preset.name} — dùng lại ở mọi video`, "Bộ kênh chưa có nhân vật, hoặc video này không dùng."),
    group("video", "Riêng video này", "AI đề xuất từ kịch bản, bạn duyệt trước khi gen ảnh mốc", "Chưa có — AI đề xuất sau bước kịch bản.")), null];
}
function qCharCard(c) {
  const busy = S.job?.state === "running", missing = !c.image_url;
  const file = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp", hidden: true, "aria-label": `Ảnh @${c.id}` });
  file.onchange = () => { if (file.files[0]) qUpload(c.id, file.files[0]); };
  return h("article", { class: "char-card" + (missing ? " missing" : "") },
    missing ? h("div", { class: "missing-box" }, h("strong", {}, "Chưa có character sheet"),
      h("span", {}, c.blocked ? `${c.blocked} mốc đang bị chặn gen` : "Chưa mốc nào bị chặn"))
      : h("img", { class: "sheet", src: c.image_url, alt: `Character sheet @${c.id}` }),
    h("div", { class: "char-body" },
      h("div", { class: "char-h" }, h("span", { class: "swatch", style: `background:${c.color || "var(--muted)"}` }), h("span", { class: "mono cid" }, "@" + c.id),
        c.name ? h("span", { class: "muted" }, c.name) : null, h("span", { class: "grow" }), h("span", { class: "mono muted" }, `${c.uses} mốc`)),
      h("p", { class: "char-desc" }, c.desc),
      h("div", { class: "row" }, file,
        missing ? h("button", { class: "primary small", disabled: busy, onclick: () => qJob("sheets") }, `Gen sheet (${provLabel(qProvider("sheets"))})`) : null,
        h("button", { class: "small", onclick: () => file.click() }, missing ? "Tải ảnh lên" : "Thay ảnh"),
        c.scope === "video" ? h("button", { class: "small", onclick: () => qPromote(c.id) }, "Đưa vào bộ kênh") : null)));
}
async function qUpload(id, f) {
  const fd = new FormData(); fd.append("file", f);
  try {
    const r = await fetch(`/api/quick/${Q.name}/chars/${id}/image`, { method: "POST", body: fd });
    if (r.status === 401) { location.href = "/login"; return; }
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || `Lỗi ${r.status}`);
    toast(`Đã gắn ảnh @${id}`);
  } catch (e) { toast(e.message, true); }
  await qReload(); Q.render();
}
async function qPromote(id) {
  if (!confirm(`Đưa @${id} vào bộ kênh? Mọi video sau của kênh dùng được nhân vật này.`)) return;
  try { await qPost(`/chars/${id}/promote`); toast(`@${id} đã vào bộ kênh`); } catch (e) { toast(e.message, true); }
  await qReload(); Q.render();
}
QSCREENS.chars = qChars;
```

- [ ] **Step 4: Kiểu Nhân vật** — thêm vào cuối `src/vidflow/ui/static/style.css`:

```css
/* ===== Quy trình nhanh — Nhân vật ===== */
.char-group{margin-bottom:26px}
.chars-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.char-card{display:flex;flex-direction:column;border-radius:12px;overflow:hidden;background:var(--surface);border:1px solid var(--line)}
.char-card.missing{border-color:var(--warn-line)}
.sheet{width:100%;aspect-ratio:16/9;object-fit:contain;background:#fff;border-bottom:1px solid var(--line)}
.missing-box{aspect-ratio:16/9;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:12px;text-align:center;background:var(--warn-bg);color:var(--warn)}
.char-body{padding:12px 14px;display:flex;flex-direction:column;gap:8px}
.char-h{display:flex;align-items:center;gap:8px}
.cid{font-weight:600}
.char-desc{margin:0;font-size:13px;color:var(--muted);line-height:1.5}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_static.py -v`
Expected: PASS.

- [ ] **Step 6: Kiểm tra tay**

Run: `uv run python scripts/seed_quick_demo.py && uv run vidflow ui --port 8788 --no-open`, đăng nhập, mở `ui-demo`. Thanh trái: mục "Nhân vật" có nhãn cam "1 thiếu". Bấm "Nhân vật": nhóm "Của bộ kênh" báo chưa có; nhóm "Riêng video này" có @ANCESTOR (ảnh sheet, màu cam, "3 mốc") và @FARMER (khung cam "Chưa có character sheet · 3 mốc đang bị chặn gen", nút "Gen sheet (Flow)" — theo nguồn ảnh trong Cài đặt hoặc ô "Nguồn" trên Bảng mốc, "Tải ảnh lên"). Bấm "Gen sheet (Flow)" → hộp xác nhận → **Hủy**. Bấm "Tải ảnh lên" chọn một file `.png` bất kỳ → toast "Đã gắn ảnh @FARMER", thẻ hiện ảnh, nhãn "1 thiếu" biến mất; quay lại Bảng mốc: mốc 007/008 chuyển "Chờ", không còn "Bị chặn". Thử tải một file `.txt` đổi đuôi `.png` → toast đỏ "File không phải ảnh png/jpg/webp.". Không bấm "Đưa vào bộ kênh" (ghi vào `presets/` thật); nếu cần thử, chạy lại script seed sau đó và khôi phục `presets/doodle-giai-ma.yaml` bằng `git checkout presets/doodle-giai-ma.yaml`.

- [ ] **Step 7: Commit**

```bash
git add src/vidflow/ui/static/quick.js src/vidflow/ui/static/style.css tests/test_ui_static.py
git commit -m "feat(ui): màn Nhân vật — ảnh sheet, chặn N mốc, tải ảnh, đưa vào bộ kênh"
```

---

### Task 10: Tạo video nhanh + trang chủ hai lối vào (Model: sonnet)

**Files:**
- Modify: `src/vidflow/ui/static/quick.js` (thêm `Q.openNew`)
- Modify: `src/vidflow/ui/static/app.js` (`renderHome`, nút "Video mới")
- Modify: `src/vidflow/ui/static/style.css` (khối hộp thoại + trang chủ)
- Test: `tests/test_ui_static.py`

**Interfaces:**
- Consumes: `GET /api/presets` (`[{id, name, aspect, characters}]`), `POST /api/quick` (Task 5, có `image_provider`, `video_provider`); `VIDEO_MODELS`, `IMAGE_MODELS`, `QSTAGE`, `PROVIDERS` (Task 8); `openNew(tpl)` (form chi tiết có sẵn trong `app.js`).
- Produces: `Q.openNew(): Promise<void>` (mở hộp thoại "Video nhanh mới", tạo project, mở Bảng mốc, theo dõi job `ideas`).

- [ ] **Step 1: Write the failing test** — thêm vào cuối `tests/test_ui_static.py`:

```python
def test_quick_new_dialog_and_home():
    js, app = _read("quick.js"), _read("app.js")
    assert "Q.openNew = async function" in js and "Tạo và đề xuất ý tưởng" in js and "Model clip động · bắt buộc" in js
    assert "Nguồn gen ảnh" in js and "Nguồn gen clip" in js and "image_provider: f.image_provider" in js
    assert "Q.openNew()" in app and "Video nhanh" in app
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui_static.py::test_quick_new_dialog_and_home -v`
Expected: FAIL — `AssertionError`.

- [ ] **Step 3: Thêm vào cuối `src/vidflow/ui/static/quick.js`**:

```js
// ================= Tạo video nhanh =================
Q.openNew = async function () {
  let presets;
  try { presets = await api("/api/presets"); } catch (e) { toast(e.message, true); return; }
  if (!presets.length) { toast("Chưa có bộ kênh — tạo bằng lệnh `vidflow preset import`.", true); return; }
  const f = { preset: presets[0].id, chars: [], image_model: IMAGE_MODELS[0], video_model: "", resolution: "720p", image_provider: "flow", video_provider: "flow", max_clips: 12, allow_cont: true };
  const presetSel = h("select", {}, presets.map(p => h("option", { value: p.id }, p.name)));
  const topic = h("input", { type: "text", placeholder: "vd: một ngày bình thường của tổ tiên 50.000 năm trước" });
  const charsBox = h("div", { class: "pick-list" }), aspect = h("span", { class: "mono" });
  const fillPreset = () => {
    const p = presets.find(x => x.id === presetSel.value);
    f.preset = p.id; f.chars = p.characters.map(c => c.id); aspect.textContent = p.aspect;
    charsBox.replaceChildren(...(p.characters.length ? p.characters.map(c => {
      const cb = h("input", { type: "checkbox" }); cb.checked = true;
      cb.onchange = () => { f.chars = cb.checked ? [...f.chars, c.id] : f.chars.filter(x => x !== c.id); };
      return h("label", { class: "pick-char" }, cb, h("span", { class: "swatch", style: `background:${c.color || "var(--muted)"}` }),
        h("span", {}, h("span", { class: "mono cid" }, "@" + c.id), " ", h("span", { class: "hint" }, c.name || c.desc)));
    }) : [h("span", { class: "hint" }, "Bộ kênh chưa có nhân vật.")]));
  };
  presetSel.onchange = fillPreset; fillPreset();
  const pick = (key, opts) => { const s = h("select", {}, opts.map(o => h("option", { value: o }, o || "— chọn —"))); s.value = f[key]; s.onchange = () => { f[key] = s.value; }; return s; };
  const psel = key => { const s = h("select", {}, PROVIDERS.map(([v, l]) => h("option", { value: v }, l))); s.value = f[key]; s.onchange = () => { f[key] = s.value; }; return s; };
  const maxOut = h("span", { class: "mono" }, String(f.max_clips));
  const range = h("input", { type: "range", min: 0, max: 40, value: f.max_clips, "aria-label": "Số clip động tối đa" });
  const vidLabel = h("label", { class: "f req" }, h("span", { class: "flabel" }, "Model clip động · bắt buộc"), pick("video_model", VIDEO_MODELS));
  range.oninput = () => { f.max_clips = Number(range.value); maxOut.textContent = range.value; vidLabel.classList.toggle("req", f.max_clips > 0); };
  const cont = h("input", { type: "checkbox" }); cont.checked = true; cont.onchange = () => { f.allow_cont = cont.checked; };
  const sec = (n, title, ...kids) => h("section", { class: "qsec" }, h("span", { class: "stepnum" }, String(n)), h("div", {}, h("h2", {}, title), kids));
  const dlg = h("dialog", { class: "qdlg", "aria-label": "Video nhanh mới" });
  dlg.addEventListener("close", () => dlg.remove());
  const submit = async () => {
    if (f.max_clips > 0 && !f.video_model) { toast("Chọn model clip động (bắt buộc khi số clip tối đa > 0).", true); return; }
    const p = presets.find(x => x.id === f.preset);
    const body = { preset: f.preset, topic: topic.value.trim(), channel_chars: f.chars.length === p.characters.length ? null : f.chars,
      image_model: f.image_model, video_model: f.video_model, resolution: f.resolution, image_provider: f.image_provider, video_provider: f.video_provider,
      max_clips: f.max_clips, allow_cont: f.allow_cont, start: true };
    try {
      const r = await api("/api/quick", { method: "POST", body: JSON.stringify(body) });
      dlg.close();
      await loadProjects(); await openProject(r.name);
      if (r.job) { S.job = r.job; startPolling(); toast(`Bắt đầu: ${r.job.label}`); } else if (r.warning) toast(r.warning, true);
    } catch (e) { toast(e.message, true); }
  };
  dlg.append(
    h("div", { class: "qdlg-h" }, h("h1", {}, "Video nhanh mới"), h("p", { class: "hint" }, "AI đề xuất 5 ý tưởng, viết kịch bản, tách mốc và viết prompt. Bạn duyệt ở từng bước.")),
    h("div", { class: "qdlg-b" },
      sec(1, "Bộ kênh và chủ đề", h("label", { class: "f" }, h("span", { class: "flabel" }, "Bộ kênh"), presetSel),
        h("label", { class: "f" }, h("span", { class: "flabel" }, "Chủ đề gợi ý · không bắt buộc"), topic)),
      sec(2, "Nhân vật của kênh dùng trong video", charsBox, h("span", { class: "hint" }, "Nhân vật riêng của video do AI đề xuất sau bước kịch bản.")),
      sec(3, "Google Flow", h("div", { class: "grid2" },
        h("div", { class: "f" }, h("span", { class: "flabel" }, "Tỉ lệ (theo bộ kênh)"), aspect),
        h("label", { class: "f" }, h("span", { class: "flabel" }, "Model ảnh"), pick("image_model", IMAGE_MODELS)),
        vidLabel,
        h("label", { class: "f" }, h("span", { class: "flabel" }, "Độ phân giải clip"), pick("resolution", ["720p", "1080p"])),
        h("label", { class: "f" }, h("span", { class: "flabel" }, "Nguồn gen ảnh"), psel("image_provider")),
        h("label", { class: "f" }, h("span", { class: "flabel" }, "Nguồn gen clip"), psel("video_provider"))),
        h("span", { class: "hint" }, "Flow, Gemini (gemini.google.com) hoặc AI Studio (aistudio.google.com) qua Chrome đã đăng nhập. Hết lượt ở nguồn nào thì đổi nguồn trên Bảng mốc.")),
      sec(4, "Chuyển động",
        h("label", { class: "f" }, h("span", { class: "flabel row between" }, "Số clip động tối đa", maxOut), range,
          h("span", { class: "hint" }, "AI đề xuất tối đa ngần này mốc làm clip; bạn bật/tắt từng mốc trên Bảng mốc. 0 = chỉ ảnh tĩnh.")),
        h("label", { class: "checks" }, cont, h("span", {}, "Cho phép AI đánh dấu ", h("strong", {}, "nối cảnh"), " — mốc tiếp nối cùng khoảnh khắc được đính ảnh mốc trước làm tham chiếu.")))),
    h("div", { class: "qdlg-f" }, h("button", { type: "button", onclick: () => dlg.close() }, "Hủy"),
      h("button", { type: "button", class: "primary", onclick: submit }, "Tạo và đề xuất ý tưởng")));
  document.body.append(dlg);
  dlg.showModal();
};
```

- [ ] **Step 4: Trang chủ hai lối vào** — trong `src/vidflow/ui/static/app.js` thay nguyên hàm `renderHome` (từ `function renderHome() {` tới dấu `}` đóng hàm, ngay trước dòng `// ================= các bước`) bằng:

```js
function renderHome() {
  const quick = S.projects.filter(p => p.kind === "quick"), full = S.projects.filter(p => p.kind !== "quick");
  return h("div", { class: "hero" },
    h("h2", { class: "hero-title" }, "Làm video với vidflow"),
    h("p", { class: "hero-sub" }, "Hai quy trình: video nhanh (doodle nhiều mốc, ảnh + clip động trong Google Flow, xuất MP4) hoặc video chi tiết (từng cảnh Veo, dựng draft CapCut)."),
    h("div", { class: "entry" },
      h("div", { class: "card" }, h("h3", {}, "Video nhanh"), h("p", { class: "hint" }, "Chọn bộ kênh, AI đề xuất ý tưởng, viết kịch bản, tách mốc, viết prompt. Bạn duyệt từng bước."),
        h("button", { class: "primary", onclick: () => Q.openNew() }, "Tạo video nhanh")),
      h("div", { class: "card" }, h("h3", {}, "Video chi tiết"), h("p", { class: "hint" }, "Ý tưởng → kịch bản từng cảnh → prompt Veo → giọng đọc → clip Flow → draft CapCut."),
        h("button", { onclick: () => openNew() }, "Tạo video chi tiết"))),
    quick.length ? h("div", {}, h("h3", { class: "sec" }, "Video nhanh của bạn"),
      h("div", { class: "tpls" }, quick.map(p => h("button", { class: "tpl", onclick: () => openProject(p.name) }, h("b", {}, p.title),
        h("p", {}, p.error ? p.error : `${p.beats ?? 0} mốc · ${QSTAGE[p.stage] || p.stage}`))))) : null,
    h("h3", { class: "sec" }, "Video chi tiết — bắt đầu từ mẫu"),
    h("div", { class: "tpls" }, TEMPLATES.map(t => h("button", { class: "tpl", onclick: () => openNew(t) }, h("b", {}, t.title), h("p", {}, t.idea)))),
    full.length ? h("div", {}, h("h3", { class: "sec" }, "Video chi tiết của bạn"),
      h("div", { class: "tpls" }, full.map(p => h("button", { class: "tpl", onclick: () => openProject(p.name, true) }, h("b", {}, p.title),
        h("p", {}, `${p.scenes ?? 0} cảnh · ${p.approved ?? 0} đã duyệt · ${p.aspect ?? ""}`))))) : null);
}
```

Đổi dòng gắn nút "Video mới" (`document.getElementById("newBtn").addEventListener("click", () => openNew());`) thành:

```js
document.getElementById("newBtn").addEventListener("click", () => openProject(""));
```

- [ ] **Step 5: Kiểu hộp thoại + trang chủ** — thêm vào cuối `src/vidflow/ui/static/style.css`:

```css
/* ===== Quy trình nhanh — Tạo video nhanh, trang chủ ===== */
.entry{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
dialog.qdlg{padding:0;width:min(760px,94vw)}
.qdlg-h{padding:24px 28px 16px;border-bottom:1px solid var(--line)}
.qdlg-h h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.5px}
.qdlg-h p{margin:6px 0 0}
.qdlg-b{padding:20px 28px;display:flex;flex-direction:column;gap:22px}
.qsec{display:flex;gap:16px}
.qsec>div{flex:1;min-width:0;display:flex;flex-direction:column;gap:10px}
.qsec h2{margin:0;font-size:15px;font-weight:700}
.stepnum{flex:none;width:26px;height:26px;border-radius:50%;display:grid;place-items:center;background:var(--primary);color:#fff;font-size:12px;font-weight:700}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.pick-list{display:flex;flex-direction:column;gap:8px}
.pick-char{display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:10px;border:1px solid var(--clip-line);background:var(--clip-bg)}
.f.req .flabel{color:var(--primary)}
.f.req select{border:2px solid var(--primary)}
.qdlg-f{padding:16px 28px;border-top:1px solid var(--line);background:var(--input);display:flex;justify-content:flex-end;gap:10px}
@media (max-width:600px){.grid2{grid-template-columns:1fr}.qsec{gap:10px}}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui_static.py -v`
Expected: PASS.

- [ ] **Step 7: Kiểm tra tay**

Run: `uv run vidflow ui --port 8788 --no-open`, đăng nhập, bấm logo vidflow (trang chủ). Thấy hai thẻ "Video nhanh" / "Video chi tiết", danh sách "Video nhanh của bạn" có `ui-demo` ("10 mốc · đã có giọng đọc"), mẫu video chi tiết không còn biểu tượng. Bấm "Tạo video chi tiết" → hộp thoại cũ "Video chi tiết mới" → Hủy. Bấm "Tạo video nhanh": hộp thoại 4 mục đánh số; Tỉ lệ hiện `16:9`; nhãn "Model clip động · bắt buộc" và viền navy; kéo thanh "Số clip động tối đa" về 0 → viền thường, số hiện 0; kéo lại 12, để model trống, bấm "Tạo và đề xuất ý tưởng" → toast đỏ yêu cầu chọn model. Mục Google Flow có thêm "Nguồn gen ảnh"/"Nguồn gen clip" (Flow, Gemini, AI Studio; mặc định Flow). Chọn "Veo 3.1 Lite", nguồn ảnh "Gemini", nguồn clip "AI Studio", nhập chủ đề "thử giao diện", đặt số clip 2, bỏ "nối cảnh", bấm tạo → mở Bảng mốc của video mới (tên `doodle-giai-ma-MMDD-HHMMSS`), thẻ "Bước 1 · Ý tưởng", việc nền "Đang chạy: Claude đề xuất 5 ý tưởng" (job Claude thật — có thể để chạy hoặc bấm "Tạm dừng" → "Đã dừng"). Bấm "Cài đặt": model clip "Veo 3.1 Lite", số clip 2, nối cảnh tắt, nguồn ảnh Gemini, nguồn clip AI Studio. Xóa thư mục thử sau khi kiểm tra: `rm -rf projects/doodle-giai-ma-*`.

- [ ] **Step 8: Commit**

```bash
git add src/vidflow/ui/static/quick.js src/vidflow/ui/static/app.js src/vidflow/ui/static/style.css tests/test_ui_static.py
git commit -m "feat(ui): Tạo video nhanh và trang chủ hai quy trình"
```

---

### Task 11: Xem thử & Xuất + kiểm tra toàn bộ (Model: sonnet)

**Files:**
- Modify: `src/vidflow/ui/static/quick.js` (thêm cuối file)
- Modify: `src/vidflow/ui/static/style.css` (khối Xem thử & Xuất)
- Test: `tests/test_ui_static.py`

**Interfaces:**
- Consumes: payload `beats[].{start, end, state, image_url, clip_url, clip.status, clip.enabled, text, n}`, `voice_url`, `aspect`, `renders`, `job`; `GET /api/quick/{name}/waveform?bins=300`; job `render` (options `resolution, transition, clip_fit, zoom, subtitles, logo, clip_audio, music`) và `build` (options `zoom, subtitles`) (Task 3/5); `qSceneList`, `qJob`, `Q.exportOpts`, `QST`, `QJOB` (Task 8).
- Produces: `qPreview() -> [center, panel]`, `qPlayer(beats)`, `qTimeline(beats)`, `qLoadWave(el)`, `qExport()`; `Q.player = {seek(t), head(frac), mark(n), raf}`; đăng ký `QSCREENS.preview = qPreview`.

- [ ] **Step 1: Write the failing test** — thêm vào cuối `tests/test_ui_static.py`:

```python
def test_quick_preview_screen_registered():
    js = _read("quick.js")
    assert "QSCREENS.preview = qPreview" in js and "Xuất MP4" in js and "Dựng draft CapCut" in js
    assert "kéo mép" not in js.lower()  # đổi thời lượng bằng kéo mép: ngoài phạm vi
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui_static.py::test_quick_preview_screen_registered -v`
Expected: FAIL — `AssertionError`.

- [ ] **Step 3: Thêm vào cuối `src/vidflow/ui/static/quick.js`**:

```js
// ================= Xem thử & Xuất =================
function qPreview() {
  const d = Q.data, beats = d.beats.filter(b => b.start != null && b.end != null);
  const center = h("section", { class: "content" }, h("h1", { class: "page-h" }, "Xem thử"));
  if (!beats.length || !d.voice_url) center.append(h("div", { class: "card" }, h("p", {}, "Chưa có giọng đọc và thời gian mốc — chạy bước Giọng đọc trên Bảng mốc trước.")));
  else center.append(qPlayer(beats), qTimeline(beats));
  return [center, qExport()];
}
function qPlayer(beats) {
  const d = Q.data, total = beats[beats.length - 1].end;
  const audio = h("audio", { src: d.voice_url, preload: "auto" });
  const img = h("img", { alt: "" }), vid = h("video", { playsinline: true, preload: "auto" });
  vid.muted = true;
  const ph = h("div", { class: "stage-ph" }), sub = h("div", { class: "subtitle" });
  const stage = h("div", { class: "stage", style: `aspect-ratio:${d.aspect.replace(":", " / ")}` }, img, vid, ph, sub);
  const time = h("span", { class: "mono" }), cur = h("span", { class: "mono now-tag" });
  const subOn = h("input", { type: "checkbox" }); subOn.checked = true;
  const playBtn = h("button", { class: "play" }, "Phát");
  let idx = -1;
  const find = t => { let lo = 0, hi = beats.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (beats[m].start <= t) lo = m; else hi = m - 1; } return lo; };
  const show = (i, t) => {
    const b = beats[i];
    if (i !== idx) {
      idx = i;
      const clip = !!(b.clip_url && b.clip.status === "ok");
      img.hidden = !(b.image_url && !clip); vid.hidden = !clip; ph.hidden = !!(b.image_url || clip);
      if (!img.hidden) img.src = b.image_url;
      if (clip) vid.src = b.clip_url;
      ph.textContent = `Mốc ${pad3(b.n)} chưa có ảnh`;
      sub.textContent = b.text;
      cur.textContent = `${pad3(b.n)}${b.clip.enabled ? " · CLIP" : ""}`;
      Q.player.mark(b.n);
    }
    if (!vid.hidden) {
      const want = Math.max(0, Math.min(t - b.start, (vid.duration || 99) - 0.05)); // clip ngắn hơn mốc → giữ khung cuối
      if (Math.abs(vid.currentTime - want) > 0.3) vid.currentTime = want;
      if (!audio.paused && vid.paused) vid.play().catch(() => {});
      if (audio.paused && !vid.paused) vid.pause();
    }
    sub.hidden = !subOn.checked;
    time.textContent = `${fmtT1(t)} / ${fmtT1(total)}`;
  };
  const tick = () => {
    if (!Q.player) return;
    show(find(audio.currentTime), audio.currentTime);
    Q.player.head(audio.currentTime / total);
    if (!audio.paused) Q.player.raf = requestAnimationFrame(tick);
  };
  Q.player = { seek: t => { audio.currentTime = t; tick(); }, head: () => {}, mark: () => {}, raf: 0 };
  audio.onplay = () => { playBtn.textContent = "Dừng"; tick(); };
  audio.onpause = () => { playBtn.textContent = "Phát"; vid.pause(); cancelAnimationFrame(Q.player?.raf || 0); tick(); };
  audio.onseeked = tick;
  subOn.onchange = tick;
  playBtn.onclick = () => (audio.paused ? audio.play() : audio.pause());
  const step = dir => { const i = Math.max(0, Math.min(beats.length - 1, find(audio.currentTime) + dir)); Q.player.seek(beats[i].start + 0.01); };
  setTimeout(tick, 0);
  return h("div", { class: "player" }, stage, audio,
    h("div", { class: "controls" }, h("button", { onclick: () => step(-1) }, "Mốc trước"), playBtn, h("button", { onclick: () => step(1) }, "Mốc sau"),
      time, cur, h("span", { class: "grow" }), h("label", { class: "row" }, subOn, "Phụ đề")));
}
function qTimeline(beats) {
  const total = beats[beats.length - 1].end, scenes = qSceneList(beats), colorOf = new Map();
  scenes.forEach(sc => sc.beats.forEach(b => colorOf.set(b.n, sc.color)));
  const segs = beats.map(b => {
    const color = colorOf.get(b.n), kind = b.state === "ok" ? "ok" : b.state === "gen" ? "gen" : b.state === "error" ? "error" : "none";
    const clip = !!(b.clip_url && b.clip.status === "ok");
    const style = `flex:${Math.max(0.05, b.end - b.start)};` + (kind === "ok" ? `background:${color}` : kind === "gen" ? `background:${color};opacity:.45` : "");
    return h("button", { class: `seg ${kind}${clip ? " clip" : ""}`, style, title: `Mốc ${pad3(b.n)} · ${fmtT(b.start)} · ${QST[b.state][0]}${clip ? " · clip" : ""}`,
      "aria-label": `Mốc ${b.n}: ${QST[b.state][0]}${clip ? ", có clip" : ""}`, onclick: () => Q.player && Q.player.seek(b.start + 0.01) });
  });
  const head = h("span", { class: "playhead" });
  if (Q.player) {
    Q.player.head = frac => { head.style.left = `${Math.min(100, Math.max(0, frac * 100))}%`; };
    Q.player.mark = n => segs.forEach((s, i) => s.classList.toggle("cur", beats[i].n === n));
  }
  const wave = h("div", { class: "wave", role: "img", "aria-label": "Sóng âm giọng đọc" });
  qLoadWave(wave);
  const key = (style, label) => h("span", {}, h("i", { style }), label);
  return h("section", { class: "timeline", "aria-label": "Dòng thời gian" },
    h("div", { class: "row between" }, h("h2", {}, "Dòng thời gian"), h("span", { class: "hint" }, `bấm mốc để nhảy tới · ${fmtT(total)}`)),
    h("div", { class: "scene-labels" }, scenes.map(sc => h("span", { style: `flex:${Math.max(0.05, sc.beats[sc.beats.length - 1].end - sc.beats[0].start)}`, title: `Cảnh ${sc.index}` }, `Cảnh ${sc.index}`))),
    h("div", { class: "segs-wrap" }, h("div", { class: "segs" }, segs, head)),
    wave,
    h("div", { class: "legend" }, key("background:#3557D6", "có ảnh (màu theo cảnh)"), key("background:var(--track);border-bottom:4px solid var(--primary)", "clip động"),
      key("background:#F4C7CF;border:1px solid var(--error)", "lỗi"), key("background:#3557D6;opacity:.45", "đang gen"), key("background:var(--track)", "chưa có ảnh")));
}
async function qLoadWave(el) {
  try {
    if (!Q.wave) Q.wave = (await api(`/api/quick/${Q.name}/waveform?bins=300`)).peaks;
    el.replaceChildren(...Q.wave.map(p => h("span", { style: `height:${Math.max(2, p * 28).toFixed(1)}px` })));
  } catch { el.replaceChildren(h("span", { class: "hint" }, "Không đọc được sóng âm")); }
}
function qExport() {
  const d = Q.data, o = Q.exportOpts, busy = S.job?.state === "running";
  const sel = (key, opts) => { const s = h("select", {}, opts.map(([v, l]) => h("option", { value: v }, l))); s.value = o[key]; s.onchange = () => { o[key] = s.value; }; return s; };
  const tog = (key, label) => { const c = h("input", { type: "checkbox" }); c.checked = o[key]; c.onchange = () => { o[key] = c.checked; }; return h("label", { class: "switch" }, h("span", {}, label), c); };
  const noimg = d.beats.filter(b => b.state !== "ok").length;
  return h("aside", { class: "panel", "aria-label": "Xuất video" }, h("div", { class: "detail" },
    h("div", { class: "detail-h" }, h("h2", {}, "Xuất MP4"), h("span", { class: "grow" }), h("span", { class: "badge" }, "Remotion · mặc định")),
    h("div", { class: "grid2" },
      h("label", { class: "f" }, h("span", { class: "flabel" }, "Độ phân giải"), sel("resolution", [["1080p", "1080p"], ["720p", "720p"]])),
      h("label", { class: "f" }, h("span", { class: "flabel" }, "Chuyển cảnh"), sel("transition", [["scene", "Theo cảnh"], ["cut", "Cắt thẳng"], ["fade", "Mờ chéo"]]))),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Clip dài hơn mốc"), sel("clip_fit", [["trim", "Cắt bớt cho vừa mốc"], ["speed", "Tăng tốc cho vừa mốc"]])),
    h("div", { class: "toggles" }, tog("zoom", "Zoom chậm trên ảnh tĩnh"), tog("subtitles", "Phụ đề theo giọng"), tog("logo", "Logo kênh"),
      tog("clip_audio", "Âm thanh trong clip Veo"), tog("music", "Nhạc nền")),
    noimg ? h("p", { class: "notice warn" }, `Còn ${noimg} mốc chưa có ảnh sẽ hiện khung trống. Nên gen xong trước khi xuất bản cuối.`) : null,
    h("button", { class: "primary", disabled: busy || !d.beats.length, onclick: () => qJob("render", { options: { ...o } }) }, "Xuất MP4"),
    h("div", { class: "subcard" }, h("b", {}, "Draft CapCut"), h("span", { class: "hint" }, "Tùy chọn, khi cần chỉnh tay. Phải đóng CapCut trước khi dựng."),
      h("button", { disabled: busy || !d.beats.length, onclick: () => qJob("build", { options: { zoom: o.zoom, subtitles: o.subtitles } }) }, "Dựng draft CapCut")),
    h("div", { class: "subcard" }, h("b", {}, "Bản đã xuất"),
      d.renders.length ? d.renders.map(r => h("div", { class: "row between" }, h("span", { class: "mono" }, `${r.file.replace("out/", "")} · ${r.size_mb} MB`),
        h("a", { href: r.url, download: r.file.replace("out/", "") }, "Tải"))) : h("span", { class: "hint" }, "Chưa có bản nào.")),
    d.job ? h("div", { class: "subcard" }, h("b", {}, `${d.job.label}: ${QJOB[d.job.state] || d.job.state}`), h("pre", { class: "log", id: "log" }, d.job.log || "")) : null));
}
QSCREENS.preview = qPreview;
```

- [ ] **Step 4: Kiểu Xem thử & Xuất** — thêm vào cuối `src/vidflow/ui/static/style.css`:

```css
/* ===== Quy trình nhanh — Xem thử & Xuất ===== */
.page-h{margin-bottom:14px}
.player{display:flex;flex-direction:column;gap:12px;padding:14px;margin:14px 0 22px;border-radius:14px;background:var(--text)}
.stage{position:relative;width:100%;border-radius:8px;overflow:hidden;background:#000}
.stage img,.stage video{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#000}
.stage-ph{position:absolute;inset:0;display:grid;place-items:center;background:var(--track);color:var(--muted);font-size:14px}
.subtitle{position:absolute;left:50%;bottom:6%;transform:translateX(-50%);max-width:78%;padding:6px 14px;border-radius:6px;background:rgba(14,18,56,.82);color:#fff;font-size:clamp(13px,2vw,19px);font-weight:600;text-align:center;line-height:1.35}
.controls{display:flex;flex-wrap:wrap;align-items:center;gap:10px;color:#E6E8F5}
.controls button{border:1px solid #3A3F6B;background:transparent;color:#fff}
.controls button.play{min-width:72px;border:none;background:var(--success);color:#06210A}
.controls label{font-size:13px;color:#E6E8F5}
.now-tag{font-size:12px;padding:2px 8px;border-radius:4px;background:var(--primary);color:#fff}
.timeline{display:flex;flex-direction:column;gap:10px;padding:14px 16px;border-radius:12px;background:var(--surface);border:1px solid var(--line)}
.timeline h2{margin:0;font-size:15px}
.scene-labels{display:flex;gap:1px;font-size:11px;color:var(--muted)}
.scene-labels span{min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.segs-wrap{overflow-x:auto}
.segs{position:relative;display:flex;gap:1px;height:34px;min-width:100%}
.seg{min-width:2px;min-height:0;padding:0;border:none;border-radius:3px;background:var(--track)}
.seg.error{background:#F4C7CF;border:1px solid var(--error)}
.seg.clip{border-bottom:5px solid var(--primary)}
.seg.cur{outline:2px solid var(--text);outline-offset:1px}
.playhead{position:absolute;top:-4px;bottom:-4px;left:0;width:2px;background:var(--text);pointer-events:none}
.wave{display:flex;align-items:center;gap:1px;height:30px}
.wave span{flex:1;border-radius:1px;background:var(--success);opacity:.75}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--muted)}
.legend i{display:inline-block;width:12px;height:12px;margin-right:6px;border-radius:3px;vertical-align:-2px;box-sizing:border-box}
.toggles{display:flex;flex-direction:column;gap:8px}
.subcard{display:flex;flex-direction:column;gap:8px;padding:12px;border-radius:10px;border:1px solid var(--line);background:var(--page)}
```

- [ ] **Step 5: Run toàn bộ test**

Run: `uv run pytest`
Expected: PASS toàn bộ (test cũ + `test_ui_static.py`, `test_ui_quick_jobs.py`, `test_ui_quick.py`, `test_ui_auth.py`).

- [ ] **Step 6: Kiểm tra tay — Xem thử & Xuất**

Run: `uv run python scripts/seed_quick_demo.py && uv run vidflow ui --port 8788 --no-open`, đăng nhập, mở `ui-demo`, bấm "Xem thử & Xuất". Thấy: khung phát 16:9 nền tối, phụ đề "Sáng thứ Hai…"; bấm "Phát" → nghe tiếng sin, thời gian chạy `00:01.2 / 00:40.0`, ảnh đổi theo mốc, mốc 002 phát clip testsrc (nếu có ffmpeg) với nhãn "002 · CLIP", mốc 006 trở đi hiện "Mốc 006 chưa có ảnh"; bỏ "Phụ đề" → phụ đề ẩn. Dòng thời gian: đoạn tô màu theo cảnh, mốc 009 hồng viền đỏ, mốc 002 gạch navy dưới; di chuột thấy "Mốc 009 · 00:30 · Lỗi"; bấm đoạn mốc 007 → nhảy tới 7 và vạch phát dịch theo; sóng âm xanh lá; chú thích bằng chữ. Khung phải: Xuất MP4 (1080p, Theo cảnh, Cắt bớt…), 5 công tắc, cảnh báo "Còn 5 mốc chưa có ảnh…", Draft CapCut, "Bản đã xuất: ui-demo-v1.mp4 · … MB · Tải" (link tải được). Nếu đã có `vidflow quick render` (Giai đoạn 2): bấm "Xuất MP4" → việc nền "Xuất MP4 (Remotion)" chạy, log hiện trong khung phải, xong thì danh sách có `ui-demo-vN.mp4`; nếu chưa có: job báo lỗi "No such command 'render'" trong log — đúng như mong đợi. Chuyển sang "Bảng mốc" khi đang phát → tiếng dừng.

- [ ] **Step 7: Kiểm tra tay — toàn quy trình và giao diện chung**

Cùng phiên: (1) thu cửa sổ còn ~800px ở cả 4 màn nhanh và 7 bước quy trình đầy đủ — các vùng xếp dọc, không cuộn ngang trang; (2) Đăng xuất → mọi trang chuyển về /login, mở trực tiếp http://127.0.0.1:8788/api/quick/ui-demo → `{"detail":"Cần đăng nhập"}`; (3) đăng nhập lại, mở `cafe-sang` (quy trình đầy đủ), sửa một ô, Cmd+S → "Đã lưu"; (4) mở `ui-demo`, đi qua Bảng mốc → Nhân vật → Xem thử & Xuất → Bảng mốc: không lỗi trong Console trình duyệt (DevTools). Xóa project thử: `rm -rf projects/ui-demo`.

- [ ] **Step 8: Commit**

```bash
git add src/vidflow/ui/static/quick.js src/vidflow/ui/static/style.css tests/test_ui_static.py
git commit -m "feat(ui): màn Xem thử & Xuất — trình phát theo mốc, dòng thời gian, xuất MP4/CapCut"
```

---

## Self-review (đã chạy khi viết kế hoạch)

- **Phủ spec Giai đoạn 3:** token/phông/khung 3 vùng/bỏ thiên hà-gradient-glow-emoji → Task 1–2; trạng thái bằng chữ → Task 2 (việc nền), 8 (mốc), 11 (dòng thời gian); màn quy trình đầy đủ giữ chức năng + đăng nhập → Task 1–2 (test cũ `test_ui_api`, `test_ui_frames`, `test_ui_auth` giữ nguyên). Bảng mốc (tiến độ, Tạm dừng, Chạy lại lỗi, Gen clip, 6 bộ lọc, gom cảnh theo `cont`, màu cảnh, thẻ mốc, khung phải với ảnh đính kèm, prompt + điểm, công tắc clip, Gen lại ảnh / AI viết lại / Lưu & kiểm duyệt / Duyệt tay) → Task 8; Nhân vật → Task 9; Xem thử & Xuất (img/video + audio + phụ đề, dòng thời gian màu cảnh, clip/lỗi/chưa có ảnh, sóng âm, bấm để nhảy, Xuất MP4 với mọi tùy chọn `quick render`, Draft CapCut, bản đã xuất) → Task 11; Tạo video nhanh (bộ kênh, chủ đề, nhân vật bộ kênh, tỉ lệ, model ảnh, model clip bắt buộc khi `max_clips > 0`, độ phân giải, số clip tối đa, nối cảnh) → Task 10. API: `GET /api/quick/{name}` → Task 4; `POST /api/quick`, `/settings`, `/pick`, `/redo`, `/clip`, `/prompt`, `/override`, `/chars/{id}/promote`, `/jobs` → Task 5; `/review` (hàng đợi riêng, chạy khi đang có job Flow) → Task 6; `/chars/{id}/image` → Task 7; `/media` cho `clips/ refs/ out/ presets/refs/` → Task 4. Kiểm thử spec "TestClient các API mới có bắt đăng nhập; sửa prompt xóa review; review chạy được khi đang có job Flow" → Task 5, 6, 7.
- **Không placeholder:** mọi bước code có code đầy đủ; bước kiểm tra tay có lệnh và điều cần thấy.
- **Nhất quán tên:** `quick_command_for(kind, project_root, instruction, options)` giống nhau ở `JobRunner` (Task 3) và `QuickFakeRunner` (Task 4); `quick_router(projects_root, runner)` (Task 4) → `quick_router(projects_root, runner, reviews)` (Task 6, sửa cả chỗ gọi trong `create_app`); `check_quick_job(kind, root, options)` (Task 3) dùng ở Task 5; `QSCREENS.board/chars/preview`, `qJob`, `qReload`, `qSceneList`, `QSTAGE`, `setCurrent`, `S.kind` khớp giữa Task 1, 8–11.
- **Review Focus:** 5 dòng đều có test ở task sở hữu (Task 3, 4, 4, 5, 7).
- **Phụ lục nguồn gen:** (a) chọn nguồn ảnh + clip ở Tạo video nhanh (Task 10) và Cài đặt video (Task 8) — API `POST /api/quick` và `/settings` nhận `image_provider`/`video_provider` (test Task 5); (b) nút Gen sheet/ảnh/clip gửi `provider` ghi đè (Task 8, 9) — `check_provider` + truyền vào `claude_cmd` (test Task 3), route ghi `Job.provider` thực dùng (test Task 5); (c) hết lượt: `Job.quota_exhausted` (mã 3 hoặc log "hết lượt ở", test Task 3 + Task 5), toast trong `startPolling` và băng cảnh báo trên Bảng mốc (Task 8); (d) nhãn nguồn trên thẻ mốc và khung chi tiết (Task 8).
