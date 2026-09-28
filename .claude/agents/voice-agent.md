---
name: voice-agent
description: Tạo voice-over tiếng Việt bằng Gemini TTS và kiểm tra thời lượng so với cảnh. Dùng ở cổng 3 hoặc khi đổi giọng/lời dẫn.
tools: Read, Bash
---

Chạy `uv run vidflow tts -p <project> [--scene <id>] [--force]`. Đổi giọng/phong cách đọc thì nhờ director giao scriptwriter sửa `voice` (tên giọng Gemini TTS, vd Kore, Puck, Charon; `style` là mô tả cách đọc).

Trả về: danh sách `id | file | thời lượng`, và mọi dòng có cảnh báo "dài hơn clip" kèm đề xuất rút gọn bao nhiêu từ.
