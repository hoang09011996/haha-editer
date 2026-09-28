from __future__ import annotations

from html import escape
from pathlib import Path

from vidflow.project import Project
from vidflow.schema import Script
from vidflow.state import ProjectState, SceneState

CSS = """
body{font-family:Arial,sans-serif;margin:16px;background:#fff;color:#111}
h1{color:#000080} .scene{border:1px solid #ccd;border-radius:8px;padding:12px;margin:12px 0}
.takes{display:flex;gap:12px;flex-wrap:wrap} figure{margin:0}
video{max-width:280px;max-height:420px;background:#000} .picked figcaption{color:#1fba00;font-weight:bold}
.err{color:#b00} .meta{color:#0069ba}
"""


def _scene_html(scene, st: SceneState) -> str:
    parts = [f'<section class="scene"><h2>{escape(scene.id)} <span class="meta">[{scene.status}, {scene.duration}s]</span></h2>',
             f"<p><b>Lời dẫn:</b> {escape(scene.narration) or '<i>(không)</i>'}</p>",
             f"<p><b>Prompt:</b> {escape(scene.veo_prompt)}</p>"]
    if st.tts:
        parts.append(f'<audio controls src="{escape(st.tts.file)}"></audio> {st.tts.duration_s:.2f}s')
    parts.append('<div class="takes">')
    for i, t in enumerate(st.takes):
        picked = i == st.picked
        label = f"take {i + 1}" + (" (đang chọn)" if picked else "")
        parts.append(f'<figure class="{"picked" if picked else ""}"><video controls src="{escape(t.file)}"></video>'
                     f"<figcaption>{label}</figcaption></figure>")
    parts.append("</div>")
    parts.extend(f'<p class="err">{escape(e)}</p>' for e in st.errors[-3:])
    parts.append("</section>")
    return "\n".join(parts)


def render_preview(project: Project, script: Script, state: ProjectState) -> Path:
    body = "\n".join(_scene_html(s, state.scenes.get(s.id) or SceneState()) for s in script.scenes)
    html = (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{escape(script.title)}</title>'
            f"<style>{CSS}</style></head><body><h1>{escape(script.title)}</h1>"
            f"<p class=\"meta\">{script.aspect} · đã tiêu {state.spent_usd:.2f}/{script.budget_usd:.2f} USD</p>"
            f"{body}</body></html>")
    out = project.root / "preview.html"
    out.write_text(html, encoding="utf-8")
    return out
