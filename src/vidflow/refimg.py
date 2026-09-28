from __future__ import annotations

import time
from typing import Callable, Protocol

from vidflow.config import Config
from vidflow.errors import ConfigError
from vidflow.project import REF_EXTS, Project
from vidflow.retry import with_retry
from vidflow.schema import Character, Script


class ImageClient(Protocol):
    def generate(self, *, prompt: str, model: str) -> bytes: ...


def character_prompt(script: Script, character: Character) -> str:
    style = f" Visual style: {script.style}." if script.style else ""
    return ("Character reference sheet on a plain neutral background, one person, front view, "
            f"face and full outfit clearly visible: {character.description}.{style}")


def _ext(data: bytes) -> str:
    return ".jpg" if data[:3] == b"\xff\xd8\xff" else ".png"


def run_refimg(project: Project, cfg: Config, client: ImageClient, *, character_ids: list[str] | None = None,
               force: bool = False, sleep: Callable[[float], None] = time.sleep) -> list[str]:
    if not cfg.image_model:
        raise ConfigError("Chưa đặt image_model trong vidflow.toml.")
    script = project.load_script()
    chars = script.characters if not character_ids else [script.character(c) for c in character_ids]
    created: list[str] = []
    for c in chars:
        if not force and project.ref_image(c) is not None:
            continue
        data = with_retry(lambda: client.generate(prompt=character_prompt(script, c), model=cfg.image_model),
                          sleep=sleep)
        for ext in REF_EXTS:
            (project.refs_dir / f"{c.id}{ext}").unlink(missing_ok=True)
        out = project.refs_dir / f"{c.id}{_ext(data)}"
        out.write_bytes(data)
        created.append(project.rel(out))
    return created
