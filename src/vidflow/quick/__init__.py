"""Quy trình nhanh "1 ý tưởng → 1 video" (spec 2026-10-07, mở rộng 2026-10-12).

Hàm cho UI:
- preset: `list_presets()`, `load_preset(id)`, `channel_refs_dir(preset)`
- project: `create_quick(root, preset, title)`, `load_quick(root)`, `load_beats(root)`
- thao tác: `ops.set_ideas / pick_idea / set_beat_texts / set_prompt(s) / edit_prompt / set_review / set_image /
  mark_redo / record_fail / clear_errors / update_settings / list_beats / status_summary`
- nhân vật: `chars.lookup / char_rows / set_chars / set_char_image / promote / parse_refs`
- clip: `clips.set_clip_enabled / set_clip_prompts / set_clip / clip_todo / ready_clips`
- xuất MP4: `render.RenderOptions`, `render.build_render_props(root, opts)` (props thuần),
  `render.write_render_props`, `render.render_quick(root, opts)` → out/<tên>-vN.mp4
- việc nền: `jobs.claude_cmd(kind, root, preset, provider=None)` (kind ∈ jobs.QUICK_KINDS; jobs.CHROME_KINDS cần
  Chrome; provider None → theo cài đặt), `jobs.review_cmd(root, preset, n, clip=)`, `voice.run_voice`,
  `build.build_quick` (draft CapCut, nhận clip)
- nguồn gen: `jobs.PROVIDER_LABELS`, `jobs.provider_for(kind, q)`, `jobs.begin_gen(root, kind, provider=None)`
  (chọn nguồn + xóa hết lượt cũ cùng nguồn/loại, gọi trước job gen), `jobs.limit_hit(root, provider, kind)`
  (sau job: có → báo hết lượt, CLI thoát mã 3), `ops.check_provider / record_limit / clear_limits`
"""
