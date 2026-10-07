"""Quy trình nhanh "1 ý tưởng → 1 draft" (spec 2026-10-07, bước 1–5).

Hàm cho UI:
- preset: `list_presets()`, `load_preset(id)`
- project: `create_quick(root, preset, title)`, `load_quick(root)`, `load_beats(root)`
- thao tác: `ops.set_ideas / pick_idea / set_beat_texts / set_prompt / set_image / mark_redo / list_beats / status_summary`
- việc nền: `jobs.claude_cmd(kind, root, preset)` (kind ∈ ideas|script|prompts|flow), `voice.run_voice`, `build.build_quick`
"""
