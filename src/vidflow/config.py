from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from vidflow.errors import ConfigError

DEFAULT_DRAFT_FOLDER = Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
# CapCut macOS bị sandbox, chỉ đọc được ~/Movies → media dựng draft phải nằm dưới đây
DEFAULT_MEDIA_FOLDER = Path.home() / "Movies" / "vidflow_media"
RESOLUTIONS = ("720p", "1080p", "4k")
PATH_KEYS = ("draft_folder", "media_folder", "comic_font")


@dataclass(frozen=True)
class Config:
    veo_model: str = "veo-3.1-generate-preview"
    veo_resolution: str = "720p"
    veo_price_per_second: float | None = None
    tts_model: str = "gemini-3.8-flash-tts"
    image_model: str | None = None
    draft_folder: Path = DEFAULT_DRAFT_FOLDER
    media_folder: Path = DEFAULT_MEDIA_FOLDER
    comic_font: Path = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")


def load_config(path: Path | None = None) -> Config:
    path = Path(path) if path else Path("vidflow.toml")
    if not path.is_file():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: sai cú pháp TOML: {e}") from e
    unknown = sorted(set(data) - {f.name for f in fields(Config)})
    if unknown:
        raise ConfigError(f"{path}: khóa không hỗ trợ {unknown}")
    if data.get("image_model") == "":
        data["image_model"] = None
    if data.get("veo_price_per_second") in (0, 0.0):
        data["veo_price_per_second"] = None
    for key in PATH_KEYS:
        if key in data:
            data[key] = Path(data[key]).expanduser()
    if data.get("veo_resolution", "720p") not in RESOLUTIONS:
        raise ConfigError(f"{path}: veo_resolution phải thuộc {RESOLUTIONS}")
    return Config(**data)
