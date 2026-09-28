from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import BaseModel


class TtsResult(BaseModel):
    file: str
    duration_s: float
    input_hash: str


class Take(BaseModel):
    file: str
    input_hash: str
    cost_usd: float
    created_at: str
    source: str = "veo_api"  # veo_api | flow (gen tay/qua trình duyệt trong Google Flow)


class PendingOp(BaseModel):
    name: str
    input_hash: str
    seconds: int
    submitted_at: str


class SceneState(BaseModel):
    tts: TtsResult | None = None
    takes: list[Take] = []
    picked: int | None = None  # chỉ số 0-based trong takes
    pending: list[PendingOp] = []
    errors: list[str] = []


class ProjectState(BaseModel):
    scenes: dict[str, SceneState] = {}
    spent_usd: float = 0.0
    draft_path: str | None = None
    last_build_at: str | None = None

    def scene(self, scene_id: str) -> SceneState:
        return self.scenes.setdefault(scene_id, SceneState())


def atomic_write_text(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
