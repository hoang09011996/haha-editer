from __future__ import annotations

import hashlib
import json
from pathlib import Path

from vidflow.config import Config
from vidflow.errors import ScriptError
from vidflow.project import Project
from vidflow.schema import Scene, Script

SCENE_PAD_S = 0.3
MIN_CLIP_SPEED = 0.8
MAX_REF_IMAGES = 3


def _digest(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def compose_veo_prompt(script: Script, scene: Scene) -> str:
    parts: list[str] = []
    if script.style:
        parts.append(f"Style: {script.style}.")
    for cid in scene.characters:
        parts.append(f"{cid}: {script.character(cid).description}.")
    for pid in scene.props:
        prop = script.prop(pid)
        if prop.description:
            parts.append(f"{prop.name or pid}: {prop.description}.")
    parts.append(scene.veo_prompt.strip())
    if not scene.veo_audio:
        parts.append("No dialogue, no narration, no music.")
    return " ".join(parts)


def scene_ref_images(project: Project, script: Script, scene: Scene) -> list[Path]:
    refs = [p for cid in scene.characters if (p := project.ref_image(script.character(cid))) is not None]
    if len(refs) > MAX_REF_IMAGES:
        raise ScriptError(f"Cảnh {scene.id}: Veo nhận tối đa 3 ảnh tham chiếu, đang có {len(refs)}")
    return refs


def tts_hash(script: Script, scene: Scene, cfg: Config) -> str:
    return _digest({"text": scene.narration, "voice": script.voice.name,
                    "style": script.voice.style, "model": cfg.tts_model})


def video_hash(project: Project, script: Script, scene: Scene, cfg: Config) -> str:
    return _digest({
        "prompt": compose_veo_prompt(script, scene),
        "duration": scene.duration,
        "aspect": script.aspect,
        "model": cfg.veo_model,
        "resolution": cfg.veo_resolution,
        "refs": [_file_digest(p) for p in scene_ref_images(project, script, scene)],
    })


PROMPT_EXCLUDED = {"veo_prompt", "veo_prompt_vi", "status", "locked", "notes", "prompt_fields_hash", "narration"}


def scene_fields_hash(script: Script, scene: Scene) -> str:
    """Hash các ô chi tiết (và hồ sơ nhân vật/bối cảnh/đạo cụ liên quan) mà prompt được viết từ đó."""
    loc = next((l.model_dump() for l in script.locations if l.id == scene.location), None)
    return _digest({
        "scene": scene.model_dump(exclude=PROMPT_EXCLUDED),
        "style": script.style, "profile": script.profile.model_dump(),
        "characters": [c.model_dump(exclude={"ref_image", "description"}) for c in script.characters if c.id in scene.characters],
        "location": loc,
        "props": [p.model_dump() for p in script.props if p.id in scene.props],
    })
