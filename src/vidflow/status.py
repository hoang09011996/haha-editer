from __future__ import annotations

from vidflow.config import Config
from vidflow.inputs import frame_input_hash, tts_hash, video_hash
from vidflow.project import Project
from vidflow.render import render_hash
from vidflow.schema import Script
from vidflow.state import ProjectState, SceneState


def _frame_stale(project: Project, script: Script, scene, st: SceneState) -> bool:
    """Có khung đã duyệt mà ảnh đang chọn được gen từ prompt cũ."""
    for f in scene.frames:
        fs = st.frames.get(f.id)
        if f.status == "approved" and fs and fs.picked is not None and 0 <= fs.picked < len(fs.images):
            if fs.images[fs.picked].input_hash != frame_input_hash(project, script, scene, f):
                return True
    return False


def scene_rows(project: Project, script: Script, state: ProjectState, cfg: Config) -> list[dict[str, str]]:
    rows = []
    for scene in script.scenes:
        st = state.scenes.get(scene.id) or SceneState()
        if not scene.narration.strip():
            tts = "-"
        elif st.tts is None:
            tts = "thiếu"
        else:
            tts = "ok" if st.tts.input_hash == tts_hash(script, scene, cfg) else "cũ"
        if scene.mode != "veo" and _frame_stale(project, script, scene, st):
            clip = "khung cũ"
        elif scene.mode != "veo" and scene.assemble == "capcut":
            clip = "ok" if render_hash(project, script, state, scene) else "thiếu ảnh"
        elif st.picked is None:
            clip = "thiếu"
        else:
            want = render_hash(project, script, state, scene) if scene.mode != "veo" else video_hash(project, script, scene, cfg)
            clip = "ok" if st.takes[st.picked].input_hash == want else "cũ"
        rows.append({
            "id": scene.id, "status": scene.status, "tts": tts, "takes": str(len(st.takes)),
            "picked": f"t{st.picked + 1}" if st.picked is not None else "-", "clip": clip,
            "pending": str(len(st.pending)), "error": st.errors[-1] if st.errors else "",
        })
    return rows
