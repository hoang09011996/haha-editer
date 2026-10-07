# vidflow image modes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. TDD mọi task. Kế hoạch dạng gọn theo yêu cầu "làm thử luôn" của người dùng: mỗi task liệt kê interface và test bắt buộc; code viết theo TDD khi thực thi.

**Goal:** Cảnh dựng từ ảnh (slideshow/stopmotion/comic) render bằng ffmpeg thành take; prompt tổng tiếng Việt; agent kiểm duyệt chặn prompt trượt.

**Architecture:** Mở rộng schema (Frame, Review), module `frames.py` (liệt kê/nhập/chọn ảnh khung + review), `render.py` (ffmpeg → mp4 → Take source="render"), cập nhật status/manual/UI/agents. Timeline/build không đổi.

**Spec:** `docs/superpowers/specs/2026-10-07-vidflow-image-modes-design.md`

## Global Constraints
- Chỉ tín dụng gói Google Flow; không gọi API ảnh/video trả phí.
- `prompt_language` mặc định `vi`; tiếng Việt cho mọi chữ người dùng thấy.
- Font bong bóng: `/System/Library/Fonts/Supplemental/Arial Unicode.ttf` (Config `comic_font`).
- fps stop-motion 6–12; seconds khung 0.5–10; tối đa 60 khung/cảnh.
- Render output `projects/<p>/clips/<scene>_r<n>.mp4`, H.264 yuv420p, 30fps, canvas theo aspect (1080x1920 / 1920x1080).

## Review Focus
1. Ảnh khác tỉ lệ/kích thước → phủ kín canvas, không méo (test: render ảnh 400x300 vào 9:16, kiểm tra kích thước output 1080x1920).
2. Khung chưa có ảnh chọn → render bỏ qua cảnh, báo khung thiếu (test_render_skips_missing_frames).
3. Prompt sửa sau khi đã review → review cũ, bị chặn gen (test_review_stale_after_prompt_edit).
4. Caption tiếng Việt có dấu, dài → xuống dòng, không tràn (test_comic_caption_wraps).
5. Cảnh ảnh trong status: clip "ok" khi take render khớp ảnh chọn hiện tại, "cũ" khi đổi ảnh (test_status_render_take).

---

### Task 1: Schema + state
Files: `schema.py`, `state.py`, `tests/test_schema_frames.py`.
Produces: `Frame(id, description, prompt, seconds, motion, caption, status, locked, review, prompt_fields_hash)`, `Review(verdict: pass|fail|override, score, issues, suggestion, prompt_hash)`, `Scene.mode/frames/fps/transition/review`, `Script.prompt_language`; `ImageTake(file, input_hash, created_at)`, `FrameState(images, picked)`, `SceneState.frames: dict[str, FrameState]`, `SceneState.frame(fid)`; `Scene.frame(fid)`.
Tests: defaults (mode veo, fps 8, transition fade, prompt_language vi); frame id trùng → lỗi; mode ảnh cần ≥1 khung khi status approved; fps ngoài 6–12 lỗi; seconds ngoài 0.5–10 lỗi; >60 khung lỗi.

### Task 2: Prompt compose + hash + review gating
Files: `inputs.py`, `tests/test_inputs_frames.py`.
Produces: `compose_veo_prompt` theo `prompt_language` (vi: "Không thoại, không lời dẫn, không nhạc." và nhãn tiếng Việt), `compose_frame_prompt(script, scene, frame) -> str` (Phong cách/Nhân vật/Đạo cụ + frame.prompt; comic thêm "chừa khoảng trống phía trên cho bong bóng thoại"), `prompt_text_hash(text) -> str`, `review_ok(review, text) -> bool` (pass/override và prompt_hash khớp), `frame_input_hash(project, script, scene, frame) -> str` (prompt ghép + ref ảnh + aspect).
Tests: vi/en compose; frame compose chứa mô tả nhân vật & đạo cụ; review_ok pass/fail/override/stale.

### Task 3: frames.py + CLI frames/import-frame/pick-frame/review-set; veo prompts gating
Files: `frames.py`, `manual.py`, `cli.py`, `tests/test_frames.py`.
Produces: `pending_frames(project, cfg) -> list[dict]` (scene/frame approved, review_ok, chưa có ảnh khớp hash; trả `{scene, frame, aspect, prompt, ref_images, outputs}` + `blocked: list[{scene,frame,reason}]`), `import_frame(project, cfg, scene_id, frame_id, src, now) -> str` (copy vào `frames/<scene>/<frame>_<n>.<ext>`, kiểm tra là ảnh bằng ffprobe, chọn bản mới), `pick_frame(project, scene_id, frame_id, n) -> str`, `set_review(project, scene_id, frame_id|None, verdict, score, issues, suggestion)` (lưu prompt_hash hiện tại). `pending_prompts` chỉ lấy cảnh `mode == veo` và review_ok; trả thêm `blocked`.
Tests: pending lọc đúng + blocked lý do; import ảnh hợp lệ/không phải ảnh/khung không tồn tại; pick; review-set rồi sửa prompt → blocked "kiểm duyệt cũ"; veo prompts bị chặn khi review fail.

### Task 4: render.py + CLI render + status
Files: `render.py`, `status.py`, `cli.py`, `config.py`, `tests/test_render.py`.
Produces: `render_hash(project, script, state, scene) -> str|None`, `plan_frames(scene, state) -> list[(Path, seconds, frame)]`, `render_scene(project, cfg, script, state, scene, target_s) -> Path` (ffmpeg), `run_render(project, cfg, scene_ids=None, now) -> dict(created, skipped)`; Take(source="render", input_hash=render_hash) + picked. `scene_rows` clip cho mode ảnh so với render_hash.
Tests (ffmpeg thật): slideshow độ dài ≈ max(tổng seconds, voice+0.3) ±0.05; stopmotion lặp đủ độ dài; comic có bong bóng (vùng trên khung sáng hơn ảnh đen gốc); ảnh 400x300 → 1080x1920; thiếu ảnh → skip; status ok/cũ; build dựng được take render.

### Task 5: UI API + frontend
Files: `ui/server.py`, `ui/jobs.py`, `ui/static/app.js`, `style.css`, `tests/test_ui_frames.py`.
Produces: POST `/api/projects/{p}/pick-frame`, POST `/api/projects/{p}/review-override {scene, frame?}`, job kinds `review` (claude prompt-reviewer), `frames_flow` (claude --chrome gen ảnh khung), `render` (CLI). GET project trả `frames_pending/blocked`. Frontend: chọn mode, editor khung, ảnh thu nhỏ + chọn bản, huy hiệu review + bỏ qua, nút Viết prompt/Kiểm duyệt/Gen ảnh/Render.
Tests: pick-frame, override ghi verdict override + prompt_hash, job cmd shapes cho review/frames_flow/render.

### Task 6: Agents + director
Files: `.claude/agents/prompt-reviewer.md` (mới), `scriptwriter.md`, `prompt-artist.md`, `flow-operator.md`, `.claude/skills/vidflow-director/SKILL.md`, `CLAUDE.md`.
Nội dung theo spec §4, §5, §7. Kiểm tra: `ls .claude/agents`, validate project mẫu.

### Task 7: Chạy thử thật
Project `test-anh` 1 cảnh slideshow 3 khung + 1 cảnh comic 2 khung: script → prompts → review → (Flow gen ảnh nếu người dùng mở --chrome; nếu không, dùng ảnh refs có sẵn để render thử) → render → build.
