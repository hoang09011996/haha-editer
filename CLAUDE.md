# haha-editer — vidflow

Luồng: ý tưởng → kịch bản → prompt/ảnh nhân vật → voice-over → clip Veo → draft CapCut Desktop.

- Phiên Claude chính là **director**: dùng skill `vidflow-director` khi người dùng muốn làm video.
- CLI: `uv run vidflow <lệnh> -p projects/<tên>`; project nằm trong `projects/` (không commit).
- Người dùng chỉ dùng tín dụng gói Google Flow: KHÔNG chạy `vidflow gen`, `vidflow estimate`, `vidflow refimg` (Veo/Imagen API trả phí). Ảnh nhân vật và video tạo trong Flow qua agent flow-operator (cần `claude --chrome`).
- Không sửa `state.json` bằng tay; mọi thay đổi trạng thái đi qua CLI.
- CapCut macOS bị sandbox (chỉ đọc `~/Movies`): `vidflow build` copy media vào `~/Movies/vidflow_media/<draft>/` và ghi cả `draft_info.json`. `build` từ chối chạy khi CapCut đang mở.
- Cấu hình: `vidflow.toml` (không commit, mẫu ở `vidflow.toml.example`); API key đọc từ `GEMINI_API_KEY`.
- Gen video: `vidflow prompts` → Google Flow → `vidflow import`. Cảnh ảnh (slideshow/stopmotion/comic): `vidflow frames` → Flow gen ảnh → `vidflow import-frame` → `vidflow render` (hoặc `assemble: capcut`). Prompt tiếng Việt, phải qua agent prompt-reviewer (`vidflow review-set`) mới được gen. TTS dùng Gemini API free tier.
- Giao diện: `uv run vidflow ui` (http://127.0.0.1:8777, mặc định bắt đăng nhập, mật khẩu ở `~/.vidflow/ui_password`) — đang mở công khai qua Tailscale Funnel, KHÔNG chạy `--no-auth`.
- Test: `uv run pytest`.
