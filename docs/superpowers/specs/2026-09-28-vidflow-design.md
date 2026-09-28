# vidflow — Luồng tạo video: Claude → Gemini (Veo/TTS) → CapCut Desktop

Ngày: 2026-09-28 · Tác giả: anhnh · Trạng thái: chờ duyệt

## 1. Mục tiêu

Tự động hóa quy trình hiện tại (Claude viết kịch bản → Google Flow gen video → CapCut ghép/edit) thành một luồng nhiều agent chạy trong Claude Code, người dùng review và sửa được ở mọi bước.

**Đầu vào:** một ý tưởng/chủ đề + tỉ lệ khung hình (9:16 hoặc 16:9).
**Đầu ra:** một draft CapCut Desktop đã ghép sẵn clip, voice-over tiếng Việt, phụ đề, nhạc nền; người dùng mở CapCut, chỉnh nhẹ và export tay.

**Tiêu chí thành công**
- Từ ý tưởng đến draft CapCut mở được, không cần thao tác file thủ công.
- Mỗi bước dừng chờ duyệt; sửa một cảnh chỉ chạy lại phần phụ thuộc cảnh đó.
- Chi phí Veo được ước tính trước và không vượt trần đã đặt.

**Ngoài phạm vi (v1)**
- Export video tự động (CapCut macOS không hỗ trợ qua file draft).
- Tự động hóa web Google Flow.
- CapCut Web / MCP chính thức của CapCut.
- Transition, effect, filter nâng cao (chỉ cắt ghép, phụ đề, nhạc, voice-over).

## 2. Quyết định đã chốt

| Chủ đề | Quyết định |
|---|---|
| Gen video | Veo 3.1 qua Gemini API (API key), không dùng giao diện Flow |
| Tỉ lệ | 9:16 và 16:9, chọn theo từng project |
| Âm thanh | Voice-over tiếng Việt bằng Gemini TTS + nhạc nền từ thư mục nhạc của người dùng; clip Veo giữ ambient nhỏ hoặc tắt tiếng |
| Dựng | Ghi draft CapCut Desktop trên macOS qua pyCapCut |
| Tổ chức | Custom agents của Claude Code + CLI Python `vidflow` làm phần xác định |

## 3. Kiến trúc

```
Người dùng
   │  (chat, @agent, sửa file)
   ▼
director ──┬── scriptwriter    → script.yaml (cảnh, lời dẫn, nhân vật)
           ├── prompt-artist   → veo_prompt, ảnh tham chiếu nhân vật
           ├── voice-agent     → vidflow tts   → Gemini TTS
           ├── video-producer  → vidflow gen   → Veo API
           └── editor          → vidflow build → pyCapCut → thư mục draft CapCut
                     ▲
                     └── tất cả đọc/ghi projects/<tên>/ (script.yaml, state.json, assets)
```

### 3.1 Agents (`.claude/agents/*.md`)

| Agent | Trách nhiệm | Công cụ |
|---|---|---|
| director | Là phiên Claude Code chính chạy skill `vidflow-director` (subagent không gọi được subagent khác): nhận ý tưởng, điều phối, chuyển yêu cầu giữa agent, dừng ở các cổng duyệt, báo tiến độ và chi phí | Agent, Read, Bash |
| scriptwriter | Viết/sửa `scenes`, `narration`, `duration`, `characters`, `style` trong `script.yaml` | Read, Edit, Write |
| prompt-artist | Viết `veo_prompt` từng cảnh (góc máy, ánh sáng, chuyển động, mô tả nhân vật nhất quán); tạo ảnh tham chiếu nhân vật; đề xuất prompt thay thế khi Veo từ chối | Read, Edit, Bash (`vidflow refimg`) |
| voice-agent | Chạy TTS, kiểm tra thời lượng lời dẫn so với `duration` cảnh, báo lệch | Bash (`vidflow tts`), Read |
| video-producer | Chạy gen Veo, xem kết quả, gen lại theo yêu cầu, chọn take | Bash (`vidflow gen/pick/preview/estimate`), Read |
| editor | Dựng draft CapCut, căn clip theo lời dẫn, phụ đề, nhạc; báo cảnh thiếu/thừa thời lượng | Bash (`vidflow build`), Read |

Người dùng có thể nói chuyện với director hoặc gọi thẳng từng agent (`@scriptwriter ...`). Mỗi agent chỉ ghi vào phần dữ liệu thuộc trách nhiệm của mình.

### 3.2 CLI `vidflow` (Python 3.11+, `uv`)

| Lệnh | Chức năng |
|---|---|
| `vidflow new <tên> --aspect 9:16` | Tạo thư mục project và `script.yaml` mẫu |
| `vidflow validate` | Kiểm tra schema `script.yaml` |
| `vidflow estimate` | Tổng giây video cần gen × đơn giá (cấu hình) → chi phí dự kiến |
| `vidflow refimg [--character id]` | Tạo ảnh tham chiếu nhân vật (Gemini image) |
| `vidflow tts [--scene id]` | Tạo voice-over từng cảnh, ghi thời lượng thực tế |
| `vidflow gen [--scene id] [--takes N]` | Gửi job Veo, poll đến khi xong, tải clip về |
| `vidflow pick <scene> <take>` | Chọn take dùng cho cảnh |
| `vidflow preview` | Sinh `preview.html` xem toàn bộ cảnh, lời dẫn, clip |
| `vidflow build` | Dựng draft CapCut Desktop |
| `vidflow status` | Trạng thái từng cảnh, chi phí đã tiêu |

Mọi lệnh idempotent: bỏ qua cảnh đã có kết quả khớp hash đầu vào, trừ khi có `--force`.

**Module**
- `schema.py` — model Pydantic cho `script.yaml`, `state.json`.
- `state.py` — đọc/ghi `state.json` (ghi atomic), tính hash đầu vào từng bước.
- `gemini_video.py` — client Veo (tạo job, poll, tải file, map lỗi).
- `gemini_tts.py` — client TTS, xuất wav/mp3, đo thời lượng (ffprobe).
- `gemini_image.py` — ảnh tham chiếu.
- `capcut_draft.py` — dựng draft qua pyCapCut, backup, kiểm tra CapCut đang chạy.
- `cost.py` — bảng đơn giá cấu hình, ước tính, kiểm tra trần.
- `preview.py` — sinh HTML xem trước.
- `cli.py` — Typer entrypoint.

## 4. Dữ liệu

### 4.1 Thư mục project
```
projects/<tên>/
  script.yaml     # nguồn sự thật do người dùng + agent sửa
  state.json      # do vidflow ghi: kết quả, hash, chi phí
  refs/           # ảnh tham chiếu nhân vật
  audio/          # s01.wav ...
  clips/          # s01_t1.mp4, s01_t2.mp4 ...
  music/          # nhạc nền (người dùng thả vào)
  preview.html
  logs/
```

### 4.2 `script.yaml`
```yaml
title: "Buổi sáng của An"
aspect: "9:16"
style: "cinematic, warm tone, soft morning light"
characters:
  - id: an
    description: "cô gái 25 tuổi, tóc ngắn đen, áo sơ mi trắng"
    ref_image: refs/an.png        # tùy chọn
voice: { name: "<tên giọng Gemini TTS>", speed: 1.0 }
music: { file: music/upbeat.mp3, volume: 0.15 }
subtitles: { enabled: true, max_chars_per_line: 32 }
budget_usd: 20
scenes:
  - id: s01
    narration: "Mỗi sáng, An bắt đầu ngày mới bằng một tách cà phê."
    veo_prompt: "Close-up of a young woman ... morning light ..."
    characters: [an]
    duration: 8                   # giây, theo giới hạn Veo
    veo_audio: false              # tắt tiếng clip Veo, dùng voice-over
    status: draft                 # draft | approved
```

### 4.3 `state.json` (mỗi cảnh)
`tts: {file, duration_s, input_hash}`, `takes: [{file, input_hash, cost_usd, created_at}]`, `picked: <index>`, `errors: [...]`; cấp project: `spent_usd`, `draft_path`, `last_build_at`.

## 5. Luồng và cổng duyệt

| Bước | Agent | Cổng duyệt (dừng chờ người dùng "OK") |
|---|---|---|
| 1. Kịch bản | scriptwriter | Duyệt danh sách cảnh, lời dẫn, thời lượng |
| 2. Prompt + ảnh nhân vật | prompt-artist | Duyệt prompt, ảnh tham chiếu, **chi phí ước tính** |
| 3. Voice-over | voice-agent | Nghe từng câu, xem tổng thời lượng |
| 4. Gen video | video-producer | Xem `preview.html`, gen lại/chọn take |
| 5. Dựng draft | editor | Mở CapCut kiểm tra; yêu cầu sửa → dựng lại |

- Chỉ cảnh `status: approved` mới được gen video.
- Bước 4 luôn cần duyệt; bước 1, 3, 5 có thể bật chế độ tự chạy.
- Sửa một cảnh → hash đổi → chỉ bước phụ thuộc cảnh đó chạy lại.
- Phản hồi giữa agent đi qua director (vd editor báo lời dẫn s04 dài hơn clip 2s → director đề xuất: rút lời dẫn, hoặc gen thêm clip nối tiếp; người dùng chọn).

## 6. Dựng draft CapCut

- Track video: clip đã chọn của từng cảnh theo thứ tự. Độ dài cảnh = độ dài lời dẫn + 0.3s đệm. Clip dài hơn → cắt bớt cuối; clip ngắn hơn → giảm tốc độ tối đa 0.8x; vẫn thiếu → không dựng cảnh đó, báo director để người dùng chọn cách xử lý.
- Track audio 1: voice-over đặt đầu mỗi cảnh.
- Track audio 2: nhạc nền, lặp/cắt theo tổng thời lượng, âm lượng theo `music.volume`.
- Track text: phụ đề từ `narration`, chia dòng theo `max_chars_per_line`, phân bổ thời gian theo tỉ lệ số ký tự trong câu.
- Canvas theo `aspect`.
- An toàn: từ chối ghi nếu CapCut đang chạy; backup draft cũ trước khi ghi đè; tên draft `vidflow_<tên project>`.

## 7. Lỗi và chi phí

- Đơn giá Veo/TTS lấy từ file cấu hình `vidflow.toml`, người dùng cập nhật theo bảng giá Google hiện hành; `estimate` và `gen` từ chối chạy nếu `spent + dự kiến > budget_usd`.
- Lỗi mạng / 429 / 5xx: retry lùi dần, tối đa 3 lần; job Veo đã tạo được lưu id để resume poll, không tạo job trùng.
- Veo từ chối vì safety: ghi lỗi vào `state.json`, prompt-artist đề xuất prompt khác, chờ duyệt.
- API key đọc từ biến môi trường `GEMINI_API_KEY`, không ghi vào project.

## 8. Kiểm thử

- Unit test: schema, hash/idempotency, ước tính chi phí, chia phụ đề, tính timeline.
- Client Gemini: test với response giả (không gọi API thật trong CI).
- `capcut_draft`: test sinh draft từ clip/audio mẫu ngắn; kiểm tra thủ công bằng cách mở trong CapCut 9.5.
- End-to-end thủ công: 1 project 3 cảnh 9:16, ngân sách nhỏ.

## 9. Rủi ro và việc cần xác minh trước khi code

1. **Định dạng draft CapCut 9.5 macOS** — chưa có draft trên máy để kiểm tra mã hóa và độ tương thích pyCapCut. Người dùng tạo 1 project test (video + text + nhạc) rồi thoát CapCut; nếu draft bị mã hóa hoặc pyCapCut không mở được → xem lại phương án dựng.
2. **Veo 3.1 qua Gemini API** — xác nhận quota, đơn giá hiện hành, giới hạn thời lượng clip và hỗ trợ ảnh tham chiếu cho tài khoản của người dùng.
3. **Gemini TTS tiếng Việt** — nghe thử chất lượng giọng trước khi chốt.
4. **Nhất quán nhân vật** giữa các clip Veo không được đảm bảo tuyệt đối; giảm thiểu bằng mô tả cố định + ảnh tham chiếu.

## 10. Kết quả spike (2026-09-28)

- CapCut 9.5 macOS mở draft do pyCapCut tạo: **có** — hiển thị video (speed 0.9x), 2 track audio có tiếng, text tiếng Việt, canvas 9:16.
- CapCut 9.5 macOS đọc/ghi **`draft_info.json`** (JSON rõ, không mã hóa), không dùng `draft_content.json`. vidflow ghi cả hai file cùng nội dung.
- CapCut chạy trong **sandbox macOS**: chỉ đọc được `~/Movies` (entitlement `assets.movies.read-write`). Media nằm ngoài `~/Movies` báo "File not accessible". → `vidflow build` copy clip/voice/nhạc vào `~/Movies/vidflow_media/<tên draft>/` và draft trỏ tới đó.
- pycapcut 0.0.3 trên PyPI thiếu `trange_seconds` → dùng bản GitHub commit `3e8209a`.
- TTS: interactions API có trong google-genai 2.25.0; `gemini-3.8-flash-tts` trả WAV (`RIFF`). Chất lượng giọng tiếng Việt: chờ người dùng nghe `spikes/out/tts.wav`.
- Model ảnh cho refimg: `gemini-3.1-flash-image` (có trong danh sách model của key).
- Veo: có `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`, `veo-3.1-lite-generate-preview`; chưa gen thử (tốn phí, chưa được duyệt) — chữ ký `operations.get`/`files.download` xác minh ở E2E.
- Credit Google Flow không dùng cho Gemini API; Veo qua API tính theo billing của API key.
- Director: là phiên Claude chính (skill vidflow-director), vì subagent không gọi được subagent.
