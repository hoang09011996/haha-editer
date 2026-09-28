from __future__ import annotations

from vidflow.config import Config
from vidflow.inputs import tts_hash, video_hash
from vidflow.project import Project
from vidflow.schema import Script
from vidflow.state import ProjectState, SceneState


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
        if st.picked is None:
            clip = "thiếu"
        else:
            clip = "ok" if st.takes[st.picked].input_hash == video_hash(project, script, scene, cfg) else "cũ"
        rows.append({
            "id": scene.id, "status": scene.status, "tts": tts, "takes": str(len(st.takes)),
            "picked": f"t{st.picked + 1}" if st.picked is not None else "-", "clip": clip,
            "pending": str(len(st.pending)), "error": st.errors[-1] if st.errors else "",
        })
    return rows
