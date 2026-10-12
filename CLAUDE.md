# haha-editer — vidflow

Luồng: ý tưởng → kịch bản → prompt/ảnh nhân vật → voice-over → clip Veo → draft CapCut Desktop.

- Phiên Claude chính là **director**: dùng skill `vidflow-director` khi người dùng muốn làm video.
- CLI: `uv run vidflow <lệnh> -p projects/<tên>`; project nằm trong `projects/` (không commit).
- Người dùng chỉ dùng gói Google AI qua phiên đăng nhập: KHÔNG chạy `vidflow gen`, `vidflow estimate`, `vidflow refimg` (Veo/Imagen API trả phí). Ảnh nhân vật, ảnh mốc và clip tạo qua phiên Chrome đã đăng nhập của người dùng (Flow mặc định; quy trình nhanh có thể dùng Gemini / AI Studio) — không dùng API trả phí.
- Không sửa `state.json` bằng tay; mọi thay đổi trạng thái đi qua CLI.
- CapCut macOS bị sandbox (chỉ đọc `~/Movies`): `vidflow build` copy media vào `~/Movies/vidflow_media/<draft>/` và ghi cả `draft_info.json`. `build` từ chối chạy khi CapCut đang mở.
- Cấu hình: `vidflow.toml` (không commit, mẫu ở `vidflow.toml.example`); API key đọc từ `GEMINI_API_KEY`.
- Gen video: `vidflow prompts` → Google Flow → `vidflow import`. Cảnh ảnh (slideshow/stopmotion/comic): `vidflow frames` → Flow gen ảnh → `vidflow import-frame` → `vidflow render` (hoặc `assemble: capcut`). Prompt tiếng Việt, phải qua agent prompt-reviewer (`vidflow review-set`) mới được gen. TTS dùng Gemini API free tier.
- Quy trình nhanh (`vidflow quick`): nhân vật `@TÊN` (bộ kênh: `presets/refs/<preset>/<ID>.png`; video: `projects/<tên>/refs/<ID>.png`), mốc `cont` đính ảnh mốc trước, clip động tối đa `max_clips` (`quick settings`). Flow: `quick sheets` → `quick flow` → `quick clips`; lỗi Flow ghi bằng `quick fail`, gen lại bằng `quick retry`. Nguồn gen `flow|gemini|aistudio` (`quick settings --image-provider/--video-provider`, ghi đè `--provider`); hết lượt hoặc bị đòi phí → agent chạy `quick limit`, job thoát mã 3.
- Xuất MP4 quy trình nhanh: `vidflow quick render -p <project>` (Remotion trong `remotion/`, cần `npm ci` một lần; phiên bản `remotion`/`@remotion/cli` khóa 4.0.534) → `projects/<tên>/out/<tên>-vN.mp4`; `--props-only` chỉ sinh `tmp/render-props.json`. Draft CapCut (`quick build`) dùng clip `ok` thay ảnh ở mốc có clip.
- Giao diện: `uv run vidflow ui` (http://127.0.0.1:8777, mặc định bắt đăng nhập, mật khẩu ở `~/.vidflow/ui_password`) — đang mở công khai qua Tailscale Funnel, KHÔNG chạy `--no-auth`.
- Test: `uv run pytest`.
