# haha-editer — vidflow

Luồng: ý tưởng → kịch bản → prompt/ảnh nhân vật → voice-over → clip Veo → draft CapCut Desktop.

- Phiên Claude chính là **director**: dùng skill `vidflow-director` khi người dùng muốn làm video.
- CLI: `uv run vidflow <lệnh> -p projects/<tên>`; project nằm trong `projects/` (không commit).
- Không bao giờ chạy `vidflow gen` khi người dùng chưa duyệt prompt và chi phí ở cổng 2; luôn chạy `vidflow estimate` trước.
- Không sửa `state.json` bằng tay; mọi thay đổi trạng thái đi qua CLI.
- CapCut macOS bị sandbox (chỉ đọc `~/Movies`): `vidflow build` copy media vào `~/Movies/vidflow_media/<draft>/` và ghi cả `draft_info.json`. `build` từ chối chạy khi CapCut đang mở.
- Cấu hình: `vidflow.toml` (không commit, mẫu ở `vidflow.toml.example`); API key đọc từ `GEMINI_API_KEY`.
- Test: `uv run pytest`.
