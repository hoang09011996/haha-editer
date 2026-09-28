from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_DRAFT_FOLDER = Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
# CapCut macOS bị sandbox, chỉ đọc được ~/Movies → media dựng draft phải nằm dưới đây
DEFAULT_MEDIA_FOLDER = Path.home() / "Movies" / "vidflow_media"


@dataclass(frozen=True)
class Config:
    veo_model: str = "veo-3.1-generate-preview"
    veo_resolution: str = "720p"
    veo_price_per_second: float | None = None
    tts_model: str = "gemini-3.8-flash-tts"
    image_model: str | None = None
    draft_folder: Path = DEFAULT_DRAFT_FOLDER
    media_folder: Path = DEFAULT_MEDIA_FOLDER
