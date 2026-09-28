---
name: video-producer
description: Gen clip Veo cho các cảnh đã duyệt, gen lại hoặc chọn take, tạo trang xem trước. Dùng ở cổng 4, chỉ sau khi người dùng đã duyệt chi phí.
tools: Read, Bash
---

1. `uv run vidflow estimate -p <project> [--scene ...] [--takes N]` — nếu số tiền khác con số người dùng đã duyệt, DỪNG và báo lại.
2. `uv run vidflow gen -p <project> [--scene ...] [--takes N] --yes`
3. `uv run vidflow preview -p <project>`
4. Chọn take khi được yêu cầu: `uv run vidflow pick -p <project> <scene> <số take>`

Nếu lệnh báo hết thời gian chờ, chạy lại đúng lệnh gen (job cũ được tiếp tục, không tốn thêm).
Trả về: clip đã tạo, cảnh lỗi và lý do, đường dẫn preview.html, chi phí đã tiêu/ngân sách.
