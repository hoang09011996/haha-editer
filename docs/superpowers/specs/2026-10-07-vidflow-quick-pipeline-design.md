# vidflow — Quy trình nhanh "1 ý tưởng → 1 draft"

Ngày: 2026-10-07 · Trạng thái: người dùng duyệt hướng, yêu cầu làm song song 2 agent.

## Mục tiêu

Giảm tối đa chữ phải đọc/duyệt. Người dùng chỉ: (1) bấm chọn 1 trong 5 ý tưởng, (2) xem lưới ảnh theo dòng thời gian, bấm ảnh không ưng để gen lại. Mọi thứ còn lại tự chạy. Mô phỏng đúng quy trình thật của người dùng (file `samples/doodle-brief.txt`, 112 ảnh `samples/doodle-112/NNN_MM-SS.jpg`, video 7–12 phút, doodle 2D, 16:9, một ảnh mỗi mốc lời dẫn).

Quy trình chi tiết cũ (scenes/frames/review từng khung) giữ nguyên, chỉ ẩn vào chế độ "Nâng cao" trên UI.

## Định dạng dùng chung (hợp đồng giữa bước 1–5 và bước 6)

Thư mục project nhanh `projects/<tên>/`:

```
quick.yaml          # trạng thái project nhanh (bước 1–5 ghi)
beats.json          # danh sách mốc (bước 1–5 ghi, bước 6 đọc nếu có)
images/NNN_MM-SS.<jpg|png>   # ảnh mỗi mốc (Flow gen; hoặc người dùng thả vào)
audio/voice.wav     # giọng đọc toàn bài (ghép từ TTS từng câu) — hoặc file người dùng (mp3/wav)
```

Tên ảnh: `NNN` = số thứ tự 3 chữ số (001…), `MM-SS` = mốc bắt đầu (phút-giây). Ví dụ `029_02-05.jpg` bắt đầu ở 125s. Đúng quy ước người dùng đang dùng.

`beats.json`:
```json
{"aspect": "16:9", "beats": [
  {"n": 1, "start": 0.0, "end": 2.31, "text": "Bạn bước vào bếp.", "prompt": "Hand-drawn 2D doodle ...", "image": "images/001_00-00.jpg",
   "review": {"verdict": "pass", "score": 8, "issues": []}, "status": "ok"}
]}
```
`start`/`end` tính bằng giây (float, ms). `image` có thể null khi chưa gen. `status`: `pending` (chưa ảnh) | `ok` | `redo` (người dùng yêu cầu gen lại).

## Bước 6 — `vidflow assemble` (agent "Dựng CapCut")

`vidflow assemble --images <dir> [--audio <file>] [--beats <beats.json>] [--name <draft>] [--aspect auto|16:9|9:16] [--zoom/--no-zoom] [--subtitles/--no-subtitles]`
- Đọc ảnh theo tên `NNN_MM-SS`, sắp theo NNN (bỏ qua file không đúng mẫu, báo tên). Mốc bắt đầu = MM-SS (hoặc `beats.json` start nếu có, chính xác ms). Ảnh i kéo dài đến mốc ảnh i+1; ảnh cuối kéo đến hết audio (hoặc +4s nếu không có audio).
- Mốc trùng/giảm dần → báo lỗi rõ tên file.
- Canvas: `auto` theo kích thước ảnh đa số (1376×768 → 16:9 1920×1080). Ảnh khác tỉ lệ phủ kín không méo.
- Zoom nhẹ xen kẽ (zoom vào / zoom ra 1.0↔1.08) để bớt tĩnh; `--no-zoom` tắt.
- Audio: một track voice từ file. Phụ đề: từ `beats.json` text nếu có.
- Copy media vào `~/Movies/vidflow_media/<draft>/` (CapCut sandbox), ghi cả `draft_info.json`, backup draft cũ, từ chối khi CapCut đang chạy — tái dùng `capcut_draft.py` (`_MediaStage`, `canvas_size`, `capcut_running`, cơ chế ghi draft).
- 112 ảnh / 8 phút phải dựng < 30s.

## Bước 1–5 — quy trình nhanh (agent "Quy trình nhanh")

- **Bộ kênh** `presets/<id>.yaml`: `name`, `brief_file` (đường dẫn file prompt gốc người dùng, ví dụ `samples/doodle-brief.txt`), `aspect`, `style_anchor_start`, `style_anchor_end` (câu neo đầu/cuối prompt ảnh, trích nguyên văn từ brief), `voice` (tên + cách đọc), `language`. `vidflow preset import <docx|txt>` tạo preset (Claude trích các trường; câu neo trích nguyên văn).
- `vidflow quick new <tên> --preset <id>` → tạo project nhanh.
- `vidflow quick ideas -p` (job Claude): ghi 5 ý tưởng vào `quick.yaml.ideas[]` (title, hook một câu, why_viral). UI hiện thẻ.
- `vidflow quick pick -p <n>` chọn ý tưởng.
- `vidflow quick script -p` (job Claude): viết kịch bản đầy đủ theo brief, tách thành câu (mỗi mốc 1 câu/cụm ~2–6s), ghi `beats.json` (text, chưa có thời gian).
- `vidflow quick voice -p`: TTS từng beat (Gemini free tier, retry/giới hạn tốc độ), đo thời lượng, ghép `audio/voice.wav` (khoảng lặng 0.15s giữa câu), điền `start/end`. Lỗi quota → dừng giữa chừng, chạy lại tiếp từ beat chưa có.
- `vidflow quick prompts -p` (job Claude): viết prompt ảnh từng beat theo brief (câu neo đầu + mô tả cảnh tiếng Anh + câu neo cuối; giữ cảnh qua các mốc liên tiếp), tự gọi prompt-reviewer, prompt trượt được viết lại tối đa 2 lần, kết quả ghi `review`.
- `vidflow quick flow -p` (job Claude --chrome): gen ảnh cho beat `pending|redo` theo lô 20, lưu `images/NNN_MM-SS.jpg`, cập nhật `image/status`.
- `vidflow quick redo -p <n…>`: đánh dấu gen lại.
- `vidflow quick build -p`: gọi `assemble` với `images/`, `audio/voice.wav`, `beats.json`.

## UI (tôi tích hợp)

Trang chủ: "Tạo video nhanh" (chọn bộ kênh, đặt tên) và "Ghép thư mục ảnh có sẵn". Trang project nhanh: 3 khối — Ý tưởng (5 thẻ, bấm chọn) · Tiến độ (thanh bước tự chạy) · Lưới ảnh (thumbnail theo thời gian + câu lời dẫn khi rê chuột, bấm → gen lại, nút Dựng CapCut). Chế độ "Nâng cao" mở giao diện cũ.

## Kiểm thử

- Bước 6: test với ảnh nhỏ tạo bằng ffmpeg; test tích hợp với `samples/doodle-112` (112 ảnh, không audio) — đủ 112 segment đúng mốc, không chồng lấn, dựng < 30s; với audio giả 487s.
- Bước 1–5: test schema preset/quick/beats, ghép voice + mốc thời gian (TTS giả), đặt tên ảnh, redo, import preset từ `samples/doodle-brief.txt` (Claude giả trong test).
