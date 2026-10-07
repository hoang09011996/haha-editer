# vidflow — Cảnh dựng từ ảnh (slideshow · stop-motion · truyện tranh) + prompt tiếng Việt có kiểm duyệt

Ngày: 2026-10-07 · Trạng thái: người dùng duyệt hướng A (render ảnh thành clip bằng ffmpeg)

## 1. Mục tiêu

Thêm cách làm cảnh bằng **nhiều ảnh** thay vì video Veo, để: có phong cách riêng, tiết kiệm tín dụng Flow (ảnh rẻ), kiểm soát từng khung hình. Mỗi cảnh chọn một cách làm; cảnh ảnh và cảnh Veo trộn trong cùng một video.

Đồng thời: **toàn bộ bằng tiếng Việt** (kể cả prompt gửi Google Flow), **prompt tổng cực kỳ chi tiết** theo mẫu cố định, và **agent kiểm duyệt độc lập** chấm từng prompt trước khi được gen.

Ngoài phạm vi: tạo ảnh/video bằng API trả phí; dựng từng ảnh trực tiếp trong CapCut (hướng B/C); tự động chọn bản ảnh đẹp nhất.

## 2. Cách làm mỗi cảnh (`scene.mode`)

| mode | Nội dung | Render |
|---|---|---|
| `veo` (mặc định) | như hiện tại | clip Veo từ Flow |
| `slideshow` | 2–8 khung; mỗi khung có `seconds`, `motion`, chuyển ảnh `transition` của cảnh | ffmpeg: Ken Burns (zoompan) + xfade |
| `stopmotion` | chuỗi khung liên tiếp của một hành động; `fps` 6–12 của cảnh | ffmpeg: mỗi khung 1/fps giây, lặp chuỗi cho đủ thời lượng |
| `comic` | các khung truyện hiện lần lượt; mỗi khung có `caption` (bong bóng thoại tiếng Việt) | ffmpeg: ảnh + bong bóng (drawbox + drawtext, font hỗ trợ tiếng Việt) |

## 3. Dữ liệu

`Scene` thêm: `mode`, `frames: list[Frame]`, `fps: int = 8` (6–12), `transition: cut|fade|slide = fade`.

`Frame`: `id` (f01…), `description` (tiếng Việt: trong khung có gì), `prompt` (prompt tổng, AI viết), `seconds: float = 2.0` (slideshow/comic), `motion: zoom_in|zoom_out|pan_left|pan_right|pan_up|pan_down|static = zoom_in`, `caption` (comic), `status: draft|approved`, `locked`, `review` (xem §5), `prompt_fields_hash`.

`SceneState` thêm `frames: dict[frame_id, FrameState]`; `FrameState`: `images: list[ImageTake{file, input_hash, created_at}]`, `picked`.

Clip render được ghi thành `Take(source="render")` của cảnh, `input_hash` = hash(các ảnh đã chọn + thông số render + độ dài đích). Timeline/build hiện tại không đổi.

`Script` thêm `prompt_language: vi|en = vi`.

## 4. Prompt tổng (tiếng Việt, cực kỳ chi tiết)

Một mẫu cố định, áp dụng cho cảnh `veo` (`veo_prompt`) và mọi khung ảnh (`frame.prompt`), các mục theo thứ tự, mỗi mục một dòng có nhãn:

`Phong cách` · `Nhân vật` (mô tả cố định, lặp nguyên văn) · `Trang phục/đạo cụ` (trạng thái trong cảnh) · `Bối cảnh` (nơi, giờ, đồ vật đời thường) · `Hành động` (MỘT; với khung: tư thế/khoảnh khắc đóng băng) · `Máy quay` (cỡ cảnh, góc, ống kính mm + khẩu độ, bố cục; video thêm MỘT chuyển động) · `Ánh sáng` (nguồn có thật, chất sáng, nhiệt màu, không khí) · `Chất ảnh` (hạt phim, texture, theo ô chống chất AI) · `Âm thanh` (chỉ video: SFX, âm nền) · `Liên tục` (giữ gì giống khung/cảnh trước) · `Tránh` (không chữ, không phụ đề, không watermark, không biến dạng tay…).

`vidflow` tự ghép phần chung (phong cách, nhân vật, đạo cụ) khi `compose`; prompt-artist chỉ viết phần riêng của cảnh/khung. Với `prompt_language: en`, prompt-artist viết tiếng Anh và kèm `*_vi` như trước.

## 5. Agent kiểm duyệt `prompt-reviewer`

Chạy độc lập (subagent riêng, không phải agent viết prompt) sau bước viết prompt. Với mỗi prompt (cảnh veo và từng khung) chấm theo bảng kiểm:

1. Đủ 11 mục của mẫu, không mục nào chung chung ("đẹp", "cinematic") khi có thể cụ thể.
2. Đúng MỘT hành động / một khoảnh khắc.
3. Nhất quán với hồ sơ nhân vật, đạo cụ, bối cảnh và với khung/cảnh liền trước (trang phục, đạo cụ, ánh sáng, giờ).
4. Có ít nhất 3 kỹ thuật chống "chất AI" theo ô đã tích.
5. Không yêu cầu chữ trên hình (trừ bong bóng comic do vidflow vẽ), không người nổi tiếng/thương hiệu, không nội dung nhạy cảm.
6. Khớp mode: khung stop-motion chỉ khác khung trước một chút; slideshow mỗi khung một ý; comic để chừa khoảng trống cho bong bóng.

Kết quả ghi vào `review: {verdict: pass|fail, score 0–10, issues[], suggestion, prompt_hash}` của cảnh/khung qua lệnh `vidflow review-set`. Prompt `fail` hoặc review cũ (prompt đã đổi) → **không được gen**: `vidflow prompts/frames --json` bỏ qua và báo lý do. Người dùng có thể bấm "Bỏ qua kiểm duyệt" cho từng prompt trên UI (ghi `verdict: override`).

## 6. Lệnh CLI mới

- `vidflow frames -p P [--json]` — khung đã duyệt, prompt đã qua kiểm duyệt, chưa có ảnh khớp prompt hiện tại.
- `vidflow import-frame -p P <scene> <frame> <file>` — nhận ảnh (png/jpg/webp) làm bản của khung, tự chọn bản mới.
- `vidflow pick-frame -p P <scene> <frame> <n>`.
- `vidflow render -p P [-s …]` — render cảnh mode ảnh có đủ ảnh đã chọn; độ dài đích = max(tổng `seconds`, giọng đọc + 0.3s), giãn đều thời lượng khung; stop-motion lặp chuỗi.
- `vidflow review-set -p P <scene> [<frame>] --verdict … --score … --issue … --suggestion …`.

## 7. Agents & UI

- scriptwriter: chọn `mode` từng cảnh, viết `frames[].description/caption/seconds/motion` (tiếng Việt).
- prompt-artist: viết prompt tổng tiếng Việt theo §4 cho cảnh và khung; chạy `mark-prompts`.
- **prompt-reviewer (mới)**: §5.
- flow-operator: thêm phần gen ảnh khung (x1–x4 bản/khung, tải về, `import-frame`).
- UI: thẻ cảnh có chọn cách làm; mode ảnh hiện danh sách khung (thêm/xóa/đổi thứ tự, mô tả, chuyển động, thời lượng, lời thoại, ảnh thu nhỏ + chọn bản, huy hiệu kiểm duyệt đạt/trượt + lý do + "Bỏ qua kiểm duyệt"); nút "✨ Viết prompt", "🛡️ Kiểm duyệt prompt", "Gen ảnh (Flow)", "Render cảnh". Bước 6 đổi tên "Hình & Video (Flow)".

## 8. Lỗi & giới hạn

- Thiếu ảnh đã chọn cho khung đã duyệt → `render` bỏ qua cảnh đó, nêu khung thiếu.
- Ảnh khác tỉ lệ khung hình → scale + crop phủ kín canvas (không viền đen).
- Font tiếng Việt cho bong bóng: `/System/Library/Fonts/Supplemental/Arial Unicode.ttf`, cấu hình được.
- Ảnh Flow đặt vào `projects/<p>/frames/<scene>/`; media dựng copy sang `~/Movies/vidflow_media/` như cũ.

## 9. Kiểm thử

Schema + validate (frame id trùng, mode cần ≥1 khung); hash khung; frames/import-frame/pick-frame; review-set và chặn gen khi fail/cũ; render thật bằng ffmpeg với ảnh nhỏ cho cả 3 mode (độ dài đúng ±0.05s, stop-motion lặp, comic có bong bóng — so pixel vùng bong bóng); take render được build dựng vào draft; API UI cho các nút mới.
