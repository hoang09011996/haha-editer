# Onboarding — vidflow (haha-editer)

Tài liệu để mở phiên Claude Code mới trên một máy/server khác và làm tiếp ngay. Đọc kèm `CLAUDE.md` (luật làm việc).

## 1. Dự án là gì

`vidflow` là CLI + giao diện web dựng video doodle/hoạt hình tiếng Việt:

- **Quy trình đầy đủ** (`vidflow ...`): ý tưởng → kịch bản chi tiết từng cảnh → prompt → ảnh nhân vật / clip trong Google Flow → voice-over → draft CapCut.
- **Quy trình nhanh** (`vidflow quick ...`, trọng tâm hiện tại): bộ kênh (`presets/<id>.yaml`) → 5 ý tưởng → kịch bản tách thành ~100–200 **mốc** → prompt ảnh (+ clip động tùy chọn) → gen ảnh/clip qua trình duyệt (Flow / Gemini / AI Studio) → giọng đọc Gemini TTS → xuất MP4 bằng Remotion (hoặc draft CapCut).
- **Giao diện web** (`vidflow ui`): Bảng mốc, Nhân vật, Xem thử & Xuất, Tạo video nhanh; có đăng nhập.

Agent Claude làm phần nội dung (viết, kiểm duyệt, thao tác trình duyệt) qua các job `claude -p` mà CLI/UI khởi chạy; hướng dẫn agent ở `.claude/agents/*.md` và `.claude/guides/gen-providers.md`.

## 2. Luật bắt buộc (tóm tắt — đầy đủ trong CLAUDE.md)

- Chỉ dùng **gói Google AI qua phiên đăng nhập trình duyệt** (Flow / Gemini / AI Studio). **Không** chạy `vidflow gen`, `vidflow estimate`, `vidflow refimg` (API Veo/Imagen trả phí). TTS dùng Gemini API **free tier**.
- AI Studio: agent phải xác minh đang dùng miễn phí trước khi gen; không xác minh được → `quick limit ... --reason "không xác minh được miễn phí"` rồi dừng.
- Không sửa tay `state.json`, `quick.yaml`, `beats.json` — mọi thay đổi qua CLI / hàm `vidflow.quick.*` (có khóa `.vidflow.lock`).
- Giao diện mở công khai qua Tailscale Funnel → **không bao giờ** chạy `vidflow ui --no-auth`.
- Mặc định tải clip 720p; ở bước duyệt đầu luôn hỏi người dùng chọn model Flow.

## 3. Cài đặt trên máy mới

Yêu cầu: macOS hoặc Linux, Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), Node ≥ 20 (đang dùng v25), ffmpeg/ffprobe, Claude Code CLI (`claude`), Google Chrome + extension **Claude in Chrome** (đăng nhập cùng tài khoản Claude).

```bash
git clone <repo-url> haha-editer && cd haha-editer
uv sync                                   # môi trường Python
(cd remotion && npm ci)                   # Remotion 4.0.534 (khóa phiên bản)
cp vidflow.toml.example vidflow.toml      # điền giá trị (draft_folder/media_folder theo máy)
export GEMINI_API_KEY=...                 # bắt buộc cho giọng đọc (free tier)
uv run pytest -q                          # kỳ vọng: toàn bộ pass (523 tại thời điểm viết)
```

**Không có trong git — phải chép tay từ máy cũ** (`rsync -a`):

| Thư mục/file | Vì sao cần |
|---|---|
| `samples/` | `presets/doodle-giai-ma.yaml` trỏ brief tới `samples/doodle-brief.txt` — thiếu là job ý tưởng/kịch bản lỗi. Có cả 112 ảnh doodle mẫu. |
| `projects/` | Các video đang làm (vd `projects/doodle-giai-ma-1012-204851`, 161 mốc). |
| `presets/refs/` (nếu có) | Ảnh sheet nhân vật của bộ kênh. |
| `vidflow.toml` | Cấu hình máy. |
| `~/.vidflow/ui_password` | Mật khẩu giao diện (hoặc đặt biến `VIDFLOW_UI_PASSWORD`). |

Sau khi chép `projects/`, xóa file khóa cũ nếu có: `find projects -name .vidflow.lock -delete`.

## 4. Chạy

```bash
uv run vidflow ui --port 8777             # http://127.0.0.1:8777, bắt đăng nhập
tailscale funnel 8777                     # (tùy chọn) mở công khai — chỉ khi đã bật đăng nhập
uv run vidflow quick status -p projects/<tên>
uv run vidflow quick --help               # toàn bộ lệnh quy trình nhanh
```

Job gen ảnh/clip/sheet (`quick sheets|flow|clips`, hoặc nút Gen trên UI) chạy `claude -p --chrome`:

- **Chrome phải chạy trên CHÍNH máy chạy vidflow** (ảnh tải về `~/Downloads` của máy đó rồi mới nhập được).
- Chỉ để **một** trình duyệt kết nối Claude in Chrome. Nếu có nhiều (vd thêm Chrome trên laptop Windows cùng tài khoản), job chạy ngầm không chọn được và dừng ngay — tắt/đăng xuất extension ở các máy kia.
- Kiểm tra nhanh: `claude -p --chrome "Chỉ liệt kê các trình duyệt Chrome đang kết nối (tên, id, hệ điều hành). Không làm gì khác."`
- Server Linux không màn hình: cần Chrome có giao diện (VNC/desktop ảo) để đăng nhập Google và cài extension; nếu không, chỉ dùng được các bước không cần trình duyệt (ý tưởng, kịch bản, prompt, giọng đọc, xuất video).

## 5. Bản đồ mã nguồn

| Đường dẫn | Nội dung |
|---|---|
| `src/vidflow/cli.py` | CLI quy trình đầy đủ; gắn `quick` và `preset` |
| `src/vidflow/quick/model.py` | Mô hình `quick.yaml` / `beats.json`, `project_lock` |
| `src/vidflow/quick/ops.py` | Thao tác mốc: prompt, kiểm duyệt, ảnh, lỗi/retry, cài đặt, nguồn gen, hết lượt, luật được gen |
| `src/vidflow/quick/chars.py` | Nhân vật `@TÊN` (bộ kênh + riêng video), ảnh sheet |
| `src/vidflow/quick/clips.py` | Clip động (Veo) cho mốc |
| `src/vidflow/quick/voice.py` | Giọng đọc: `per_beat` / `chunk` (mặc định, ~20 câu/lượt) / `full` (≤ 3000 ký tự); căn mốc theo khoảng lặng |
| `src/vidflow/quick/render.py` | Xuất MP4 qua Remotion (`remotion/src/DoodleVideo.tsx`) |
| `src/vidflow/quick/jobs.py` | Lời giao việc cho agent; `provider_for`, `begin_gen`, `limit_hit` |
| `src/vidflow/assemble.py`, `capcut_draft.py` | Draft CapCut |
| `src/vidflow/ui/` | FastAPI: `server.py`, `quick_api.py`, `jobs.py` (JobRunner, ReviewRunner), `static/` (`app.js`, `quick.js`, `style.css`) |
| `.claude/agents/`, `.claude/guides/gen-providers.md` | Hướng dẫn các agent |
| `docs/superpowers/specs/2026-10-12-quick-refs-clips-ui-design.md` | Spec hiện hành (+ phụ lục nguồn gen) |
| `docs/superpowers/plans/2026-10-12-*.md` | Kế hoạch giai đoạn 1, 1b, 2, 3 (đã làm xong) |
| `docs/superpowers/mockups/quick/` | Mockup giao diện đã duyệt |
| `scripts/seed_quick_demo.py` | Tạo project demo `ui-demo` (ảnh giả màu trơn — chỉ để thử UI) |

## 6. Trạng thái hiện tại (2026-10-14)

Đã xong và merge vào `feat/vidflow`: nhân vật `@TÊN`, nối cảnh, clip động, nguồn gen flow/gemini/aistudio + hết lượt (mã 3), xuất Remotion + CapCut nhận clip, giao diện mới 4 màn, kiểm duyệt song song, khóa ghi, đọc giọng theo đoạn, gen ảnh không cần chờ giọng (tên tạm `NNN`, tự đổi `NNN_MM-SS` sau khi đọc).

Video đang làm: `projects/doodle-giai-ma-1012-204851` (161 mốc, prompt đã đạt kiểm duyệt):

1. **Chưa có sheet 4 nhân vật** YOU, BRAIN, GOLDFISH, RESEARCHER → 131 mốc bị chặn. Prompt sheet viết sẵn ở `tmp/sheet_<ID>.txt`. Việc tiếp: kết nối Chrome đúng máy (mục 4) → "Gen sheet" (màn Nhân vật).
2. **Chưa có giọng đọc**: Gemini TTS free tier từng treo/hết lượt. Chế độ mặc định `chunk` (~9 lượt). Bấm "Tạo giọng đọc" khi có lượt; các đoạn đã đọc được giữ.
3. Sau đó: Gen ảnh → (tùy chọn) clip → Xem thử → Xuất MP4.

Chưa kiểm chứng thật: thao tác giao diện Gemini/AI Studio của agent (hướng dẫn viết theo hiểu biết chung — lần chạy đầu cần đối chiếu và cập nhật `gen-providers.md`); căn mốc giọng đọc theo khoảng lặng trên giọng Gemini thật; kiểm tra giao diện bằng trình duyệt thật.

Việc còn để sau: khóa ghi chưa phủ `presets/` (promote / ảnh sheet bộ kênh); khóa đăng nhập dựa vào `X-Forwarded-For` cần kiểm tra với Tailscale Funnel; dọn `audio/chunks/` cũ; một số điểm nhỏ ghi trong lịch sử commit/review.

## 7. Cách làm việc với Claude trong repo này

- Muốn làm video: dùng skill `vidflow-director` (luồng đầy đủ) hoặc giao diện quy trình nhanh.
- Tính năng mới: quy trình superpowers — brainstorming → spec (`docs/superpowers/specs/`) → plan (`docs/superpowers/plans/`) → subagent-driven-development (người dùng muốn ưu tiên Sonnet/Haiku cho task, Opus chỉ cho review cuối).
- Ghi chú người dùng: trả lời tiếng Việt; 720p mặc định; luôn hỏi model Flow ở bước duyệt đầu; chỉ dùng tín dụng gói.
