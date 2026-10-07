"""Khung ảnh của cảnh dựng từ ảnh: liệt kê khung cần gen, nhập/chọn ảnh, ghi kết quả kiểm duyệt."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

from vidflow.config import Config
from vidflow.errors import ScriptError, VidflowError
from vidflow.inputs import (compose_frame_prompt, compose_veo_prompt, frame_input_hash, prompt_text_hash, review_ok,
                            scene_ref_images)
from vidflow.project import Project
from vidflow.schema import Review
from vidflow.state import ImageTake, SceneState
from vidflow.video import _now_iso

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def review_reason(review: Review | None, text: str) -> str | None:
    """None nếu được gen; ngược lại là lý do (tiếng Việt)."""
    if review is None:
        return "chưa kiểm duyệt"
    if review.prompt_hash != prompt_text_hash(text):
        return "kiểm duyệt cũ (prompt đã sửa)"
    if review.verdict == "fail":
        issues = "; ".join(review.issues) or "không rõ"
        return f"kiểm duyệt trượt ({review.score:g}/10): {issues}"
    return None


def pending_frames(project: Project, cfg: Config) -> tuple[list[dict], list[dict]]:
    script, state = project.load_script(), project.load_state()
    items, blocked = [], []
    for scene in script.scenes:
        if scene.mode == "veo" or scene.status != "approved":
            continue
        refs = [str(p) for p in scene_ref_images(project, script, scene)]
        st = state.scenes.get(scene.id) or SceneState()
        for frame in scene.frames:
            if frame.status != "approved":
                continue
            text = compose_frame_prompt(script, scene, frame)
            reason = review_reason(frame.review, text) if frame.prompt.strip() else "prompt trống"
            if reason:
                blocked.append({"scene": scene.id, "frame": frame.id, "reason": reason})
                continue
            h = frame_input_hash(project, script, scene, frame)
            fs = st.frames.get(frame.id)
            if fs and any(i.input_hash == h for i in fs.images):
                continue
            items.append({"scene": scene.id, "frame": frame.id, "mode": scene.mode, "aspect": script.aspect,
                          "prompt": text, "description": frame.description, "ref_images": refs,
                          "resolution": script.flow.resolution})
    return items, blocked


def veo_blocked(project: Project) -> list[dict]:
    script = project.load_script()
    out = []
    for scene in script.scenes:
        if scene.mode != "veo" or scene.status != "approved" or not scene.veo_prompt.strip():
            continue
        reason = review_reason(scene.review, compose_veo_prompt(script, scene))
        if reason:
            out.append({"scene": scene.id, "frame": None, "reason": reason})
    return out


def _is_image(path: Path) -> bool:
    """Giải mã thử 1 khung: ffprobe vẫn báo codec png với file hỏng nên phải decode thật."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-f", "null", "-"],
                       capture_output=True, text=True)
    return r.returncode == 0 and not r.stderr.strip()


def import_frame(project: Project, cfg: Config, scene_id: str, frame_id: str, src: Path, *,
                 now: Callable[[], str] = _now_iso) -> str:
    script = project.load_script()
    scene = script.scene(scene_id)
    frame = scene.frame(frame_id)
    src = Path(src).expanduser()
    if not src.is_file():
        raise VidflowError(f"Không thấy file {src}")
    if src.suffix.lower() not in IMAGE_EXTS or not _is_image(src):
        raise VidflowError(f"{src.name} không phải ảnh png/jpg/webp đọc được")
    state = project.load_state()
    fs = state.scene(scene_id).frame(frame_id)
    dest_dir = project.root / "frames" / scene_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{frame_id}_{len(fs.images) + 1}{src.suffix.lower()}"
    shutil.copy2(src, dest)
    fs.images.append(ImageTake(file=project.rel(dest), input_hash=frame_input_hash(project, script, scene, frame),
                               created_at=now()))
    fs.picked = len(fs.images) - 1
    project.save_state(state)
    return project.rel(dest)


def pick_frame(project: Project, scene_id: str, frame_id: str, n: int) -> str:
    project.load_script().scene(scene_id).frame(frame_id)
    state = project.load_state()
    fs = state.scene(scene_id).frame(frame_id)
    if not 1 <= n <= len(fs.images):
        raise ScriptError(f"Khung {scene_id}/{frame_id} có bản 1..{len(fs.images)}, nhận {n}")
    fs.picked = n - 1
    project.save_state(state)
    return fs.images[fs.picked].file


def set_review(project: Project, scene_id: str, frame_id: str | None, *, verdict: str, score: float,
               issues: list[str], suggestion: str) -> None:
    """Ghi kết quả kiểm duyệt cho prompt hiện tại (cảnh veo khi frame_id None, hoặc một khung)."""
    script = project.load_script()
    scene = script.scene(scene_id)
    if frame_id:
        target = scene.frame(frame_id)
        text = compose_frame_prompt(script, scene, target)
    else:
        target = scene
        text = compose_veo_prompt(script, scene)
    target.review = Review(verdict=verdict, score=score, issues=issues, suggestion=suggestion,
                           prompt_hash=prompt_text_hash(text))
    project.save_script(script)
