"""Quy trình nhanh "1 ý tưởng → 1 video" (spec 2026-10-07, mở rộng 2026-10-12).

Hàm cho UI:
- preset: `list_presets()`, `load_preset(id)`, `channel_refs_dir(preset)`
- project: `create_quick(root, preset, title)`, `load_quick(root)`, `load_beats(root)`
- thao tác: `ops.set_ideas / pick_idea / set_beat_texts / set_prompt(s) / edit_prompt / set_review / set_image /
  mark_redo / record_fail / clear_errors / update_settings / list_beats / status_summary`
- nhân vật: `chars.lookup / char_rows / set_chars / set_char_image / promote / parse_refs`
- clip: `clips.set_clip_enabled / set_clip_prompts / set_clip / clip_todo`
- việc nền: `jobs.claude_cmd(kind, root, preset)` (kind ∈ jobs.QUICK_KINDS; jobs.CHROME_KINDS cần Chrome),
  `jobs.review_cmd(root, preset, n, clip=)`, `voice.run_voice`, `build.build_quick`
"""
