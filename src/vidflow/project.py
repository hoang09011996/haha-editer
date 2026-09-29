from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from vidflow.errors import ScriptError
from vidflow.schema import Character, Script
from vidflow.state import ProjectState, atomic_write_text

SUBDIRS = ("audio", "clips", "refs", "music", "logs")
REF_EXTS = (".png", ".jpg", ".jpeg")

TEMPLATE = """\
title: "{title}"
aspect: "{aspect}"
style: ""
characters: []
voice: {{ name: "Kore", style: "", speed: 1.0 }}
music: null
subtitles: {{ enabled: true, max_chars_per_line: 32 }}
budget_usd: 20
scenes: []
"""


@dataclass(frozen=True)
class Project:
    root: Path

    @property
    def script_path(self) -> Path:
        return self.root / "script.yaml"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    @property
    def audio_dir(self) -> Path:
        return self.root / "audio"

    @property
    def clips_dir(self) -> Path:
        return self.root / "clips"

    @property
    def refs_dir(self) -> Path:
        return self.root / "refs"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    @classmethod
    def open(cls, root: Path) -> "Project":
        root = Path(root).resolve()
        if not (root / "script.yaml").is_file():
            raise ScriptError(f"Không thấy {root / 'script.yaml'}. Tạo bằng: vidflow new {root} --title \"...\"")
        return cls(root)

    def load_script(self) -> Script:
        try:
            data = yaml.safe_load(self.script_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ScriptError(f"script.yaml sai cú pháp YAML: {e}") from e
        try:
            return Script.model_validate(data)
        except ValidationError as e:
            raise ScriptError(f"script.yaml không hợp lệ:\n{e}") from e

    def save_script(self, script: Script) -> None:
        data = script.model_dump(mode="json", exclude_defaults=True)
        data.setdefault("title", script.title)
        atomic_write_text(self.script_path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000))

    def load_state(self) -> ProjectState:
        if not self.state_path.is_file():
            return ProjectState()
        return ProjectState.model_validate_json(self.state_path.read_text(encoding="utf-8"))

    def save_state(self, state: ProjectState) -> None:
        atomic_write_text(self.state_path, state.model_dump_json(indent=2))

    def path(self, rel: str) -> Path:
        return self.root / rel

    def rel(self, path: Path) -> str:
        return Path(path).resolve().relative_to(self.root).as_posix()

    def ref_image(self, character: Character) -> Path | None:
        if character.ref_image:
            p = self.path(character.ref_image)
            if not p.is_file():
                raise ScriptError(f"Nhân vật {character.id}: không thấy ảnh {character.ref_image}")
            return p
        for ext in REF_EXTS:
            p = self.refs_dir / f"{character.id}{ext}"
            if p.is_file():
                return p
        return None


def create_project(root: Path, title: str, aspect: str) -> Project:
    root = Path(root).resolve()
    if (root / "script.yaml").exists():
        raise ScriptError(f"{root} đã có script.yaml")
    if aspect not in ("9:16", "16:9"):
        raise ScriptError(f"aspect phải là 9:16 hoặc 16:9, nhận '{aspect}'")
    for d in SUBDIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    (root / "script.yaml").write_text(TEMPLATE.format(title=safe_title, aspect=aspect), encoding="utf-8")
    return Project(root)
