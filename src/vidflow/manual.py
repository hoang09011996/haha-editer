"""Gen clip ngoài API (Google Flow, dùng tín dụng gói): xuất prompt và nhập clip đã tải về."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from vidflow.config import Config
from vidflow.errors import VidflowError
from vidflow.inputs import compose_veo_prompt, review_ok, scene_ref_images, video_hash
from vidflow.media import video_duration
from vidflow.project import Project
from vidflow.state import SceneState, Take
from vidflow.video import _now_iso

VIDEO_EXTS = (".mp4", ".mov")


def pending_prompts(project: Project, cfg: Config) -> list[dict]:
    script, state = project.load_script(), project.load_state()
    items = []
    for scene in script.scenes:
        if scene.mode != "veo" or scene.status != "approved" or not scene.veo_prompt.strip():
            continue
        if not review_ok(scene.review, compose_veo_prompt(script, scene)):
            continue
        h = video_hash(project, script, scene, cfg)
        st = state.scenes.get(scene.id) or SceneState()
        if any(t.input_hash == h for t in st.takes):
            continue
        items.append({
            "id": scene.id, "aspect": script.aspect, "duration": scene.duration,
            "prompt": compose_veo_prompt(script, scene),
            "prompt_vi": scene.veo_prompt_vi,
            "flow_video_model": script.flow.video_model,
            "flow_resolution": script.flow.resolution,
            "ref_images": [str(p) for p in scene_ref_images(project, script, scene)],
        })
    return items


def write_prompts_md(project: Project, items: list[dict]) -> Path:
    lines = ["# Prompt cho Google Flow", ""]
    for i in items:
        lines += [f"## {i['id']} · {i['aspect']} · {i['duration']}s", "", i["prompt"], ""]
        if i.get("prompt_vi"):
            lines.append(f"- Bản dịch (chỉ để đọc, không dán vào Flow): {i['prompt_vi']}")
        lines += [f"- Ảnh tham chiếu: {r}" for r in i["ref_images"]]
        lines += [f"- Tải về rồi: `uv run vidflow import -p {project.root} {i['id']} <file.mp4>`", ""]
    out = project.root / "prompts.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def import_clip(project: Project, cfg: Config, scene_id: str, src: Path, *,
                now: Callable[[], str] = _now_iso) -> str:
    script = project.load_script()
    scene = script.scene(scene_id)
    src = Path(src).expanduser()
    if not src.is_file():
        raise VidflowError(f"Không thấy file {src}")
    video_duration(src)  # báo lỗi rõ nếu không phải video đọc được
    state = project.load_state()
    st = state.scene(scene_id)
    dest = project.clips_dir / f"{scene_id}_t{len(st.takes) + 1}{src.suffix.lower()}"
    shutil.copy2(src, dest)
    st.takes.append(Take(file=project.rel(dest), input_hash=video_hash(project, script, scene, cfg),
                         cost_usd=0.0, created_at=now(), source="flow"))
    st.picked = len(st.takes) - 1
    project.save_state(state)
    return project.rel(dest)


def import_inbox(project: Project, cfg: Config, *,
                 now: Callable[[], str] = _now_iso) -> tuple[dict[str, str], list[str]]:
    inbox = project.root / "inbox"
    ids = sorted((s.id for s in project.load_script().scenes), key=len, reverse=True)
    imported: dict[str, str] = {}
    unmatched: list[str] = []
    if not inbox.is_dir():
        return imported, unmatched
    for f in sorted(p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS):
        sid = next((i for i in ids if f.stem == i or f.stem.startswith(f"{i}_") or f.stem.startswith(f"{i}-")), None)
        if sid is None:
            unmatched.append(f.name)
            continue
        imported[f.name] = import_clip(project, cfg, sid, f, now=now)
        done = inbox / "imported"
        done.mkdir(exist_ok=True)
        shutil.move(str(f), done / f.name)
    return imported, unmatched
