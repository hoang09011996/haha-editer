from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from vidflow.errors import ScriptError

Aspect = Literal["9:16", "16:9"]


class Character(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    description: str
    ref_image: str | None = None


class Voice(BaseModel):
    name: str = "Kore"
    style: str = ""
    speed: float = Field(1.0, gt=0.5, le=2.0)


class Music(BaseModel):
    file: str
    volume: float = Field(0.15, ge=0, le=1)


class Subtitles(BaseModel):
    enabled: bool = True
    max_chars_per_line: int = Field(32, ge=8)


class Scene(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    narration: str = ""
    veo_prompt: str = ""
    characters: list[str] = []
    duration: Literal[4, 6, 8] = 8
    veo_audio: bool = False
    status: Literal["draft", "approved"] = "draft"


class Script(BaseModel):
    title: str
    aspect: Aspect = "9:16"
    style: str = ""
    characters: list[Character] = []
    voice: Voice = Voice()
    music: Music | None = None
    subtitles: Subtitles = Subtitles()
    budget_usd: float = Field(20, gt=0)
    scenes: list[Scene] = []

    @model_validator(mode="after")
    def _check_refs(self) -> "Script":
        ids = [s.id for s in self.scenes]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"scene id trùng: {dup}")
        char_ids = {c.id for c in self.characters}
        for s in self.scenes:
            unknown = sorted(set(s.characters) - char_ids)
            if unknown:
                raise ValueError(f"scene {s.id}: nhân vật không tồn tại {unknown}")
        return self

    def scene(self, scene_id: str) -> Scene:
        for s in self.scenes:
            if s.id == scene_id:
                return s
        raise ScriptError(f"Không có cảnh '{scene_id}' trong script.yaml")

    def character(self, char_id: str) -> Character:
        for c in self.characters:
            if c.id == char_id:
                return c
        raise ScriptError(f"Không có nhân vật '{char_id}' trong script.yaml")
