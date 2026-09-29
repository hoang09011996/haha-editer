# vidflow UI — Web app cục bộ để làm video (v1)

Ngày: 2026-09-29 · Trạng thái: người dùng duyệt kiến trúc (phần 1) và các ô (phần 2), yêu cầu làm luôn rồi góp ý trên UI.

## Mục tiêu
Một trang web chạy trên máy (`uv run vidflow ui`, http://127.0.0.1:8777) thay cho việc chat với director: tạo video mới từ ý tưởng, sửa kịch bản cực kỳ chi tiết bằng ô/ô tích, xem và chọn media, bấm chạy từng bước (Claude viết kịch bản/prompt, TTS, gen trong Google Flow, dựng CapCut).

## Quyết định
- Server FastAPI chỉ nghe 127.0.0.1; frontend HTML + JS thuần (không build), màu #000080/#0069ba/#1fba00, font Arial.
- Dữ liệu vẫn là `projects/<tên>/script.yaml` + `state.json`; UI đọc/ghi qua API, validate bằng schema Pydantic.
- Mỗi lúc chỉ chạy 1 job; log ghi `projects/<tên>/logs/job-*.log`, UI hiển thị trực tiếp.
- Job Claude chạy `claude -p --permission-mode bypassPermissions` với hướng dẫn trong `.claude/agents/*.md`; job Flow thêm `--chrome`.
- Chỉ dùng tín dụng gói Google Flow; UI không có nút Veo API trả phí.
- Người dùng điền tiếng Việt; job "Viết prompt chi tiết" viết `veo_prompt` tiếng Anh + `veo_prompt_vi`, lưu `prompt_fields_hash`; UI báo prompt "cũ" khi các ô của cảnh đổi sau đó.

## Schema mở rộng (tương thích ngược)
- `profile`: idea, audience, platform, style_type (live_action | anim_3d | anim_2d | ugc), palette, mood, film_look, reference.
- `characters[]`: + name, age, build, face, hair, accessories, wardrobe, expressions, voice_note, locked. `description` (EN) do job prompt viết từ các ô, được ghép vào mọi prompt.
- `locations[]`: id, name, place, time_of_day, details, light_sources, ambience.
- `props[]`: id, name, description (EN, cố định giữa các cảnh).
- `scenes[]`: + purpose, dialogue, location, props, prop_state, action, beats, expression, shot_size, angle, camera_move, lens, dof, composition, light, light_quality, color_temp, atmosphere, sfx, ambient, avoid[], anti_ai[], locked, notes, prompt_fields_hash.

## Chống "chất AI" (nguồn: hướng dẫn Veo 3.1 của Google Cloud/Vertex/DeepMind, Replicate, DesignHero)
Mỗi cảnh một hành động; ống kính/khẩu độ cụ thể; nguồn sáng có thật; hạt phim nhẹ; chi tiết không hoàn hảo; luôn mô tả âm nền; chặn chữ/phụ đề; mô tả nhân vật/đạo cụ lặp nguyên văn + ảnh tham chiếu; không mâu thuẫn với ảnh tham chiếu.

## Kiểm thử
API bằng FastAPI TestClient (tạo project, đọc/ghi script, validate lỗi, chọn take, media không thoát khỏi thư mục project, job chạy/ghi log/chặn job thứ hai); schema mới có test; UI kiểm tra thủ công.
