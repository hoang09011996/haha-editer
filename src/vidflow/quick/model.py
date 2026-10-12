"""Mô hình dữ liệu project nhanh: quick.yaml + beats.json (hợp đồng với bước 6 `assemble`)."""
from __future__ import annotations

import fcntl
import functools
import math
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from vidflow.errors import VidflowError
from vidflow.state import atomic_write_text

QUICK_FILE = "quick.yaml"
BEATS_FILE = "beats.json"
LOCK_FILE = ".vidflow.lock"
LOCK_TIMEOUT = 10.0
SUBDIRS = ("images", "clips", "refs", "out", "audio", "audio/beats", "logs", "tmp")
IMAGE_EXTS = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png", ".webp": ".webp"}
VIDEO_EXTS = {".mp4": ".mp4", ".mov": ".mov", ".webm": ".webm"}
CHAR_ID = r"^[A-Z][A-Z0-9_]{1,23}$"
PROVIDERS = ("flow", "gemini", "aistudio")
Provider = Literal["flow", "gemini", "aistudio"]
Stage = Literal["new", "ideas", "picked", "script", "voiced", "prompted", "imaged", "built"]
STAGES: tuple[str, ...] = Stage.__args__


class Idea(BaseModel):
    title: str
    hook: str = ""
    why_viral: str = ""


class Character(BaseModel):
    """Nhân vật @ID. Ảnh sheet tìm theo quy ước: refs/<ID>.png|jpg|webp (xem quick/chars.py)."""
    id: str = Field(pattern=CHAR_ID)
    name: str = ""
    desc: str
    color: str = ""


class FlowSettings(BaseModel):
    image_model: str = "Nano Banana 2"
    video_model: str = ""  # bắt buộc chọn trước khi gen clip
    resolution: Literal["720p", "1080p"] = "720p"
    image_provider: Provider = "flow"  # nguồn gen ảnh + character sheet
    video_provider: Provider = "flow"  # nguồn gen clip


class LimitHit(BaseModel):
    """Một lần nguồn gen báo hết lượt (hoặc đòi trả phí) — agent ghi qua `quick limit`."""
    provider: Provider
    kind: Literal["image", "video"]
    reason: str = ""
    at: str  # ISO 8601, giờ máy


class QuickProject(BaseModel):
    preset: str
    title: str = ""
    ideas: list[Idea] = []
    picked: int | None = None  # 1-based
    stage: Stage = "new"
    characters: list[Character] = []
    channel_chars: list[str] | None = None  # None = dùng mọi nhân vật của bộ kênh
    flow: FlowSettings = Field(default_factory=FlowSettings)
    max_clips: int = Field(default=12, ge=0)
    allow_cont: bool = True
    limits: list[LimitHit] = []

    def picked_idea(self) -> Idea | None:
        if self.picked and 1 <= self.picked <= len(self.ideas):
            return self.ideas[self.picked - 1]
        return None


class Review(BaseModel):
    verdict: Literal["pass", "fail", "override"]
    score: float = 0
    issues: list[str] = []


class Clip(BaseModel):
    enabled: bool = False
    prompt: str = ""
    review: Review | None = None
    file: str | None = None  # clips/NNN_MM-SS.mp4
    status: Literal["pending", "ok", "redo", "error"] = "pending"
    error: str = ""
    provider: str = ""  # nguồn đã gen clip


class Beat(BaseModel):
    n: int
    start: float | None = None
    end: float | None = None
    text: str
    prompt: str = ""
    image: str | None = None
    review: Review | None = None
    status: Literal["pending", "ok", "redo"] = "pending"
    refs: list[str] = []  # @ID trong prompt ảnh — CLI tự tách, agent không khai
    cont: bool = False    # nối cảnh: đính ảnh mốc liền trước khi gen
    clip: Clip = Field(default_factory=Clip)
    error: str = ""       # lý do Flow từ chối ảnh gần nhất (rỗng = không lỗi)
    provider: str = ""  # nguồn đã gen ảnh


class Beats(BaseModel):
    aspect: str = "16:9"
    beats: list[Beat] = []

    def get(self, n: int) -> Beat:
        for b in self.beats:
            if b.n == n:
                return b
        raise VidflowError(f"Không có mốc {n} (có {len(self.beats)} mốc).")

    @property
    def timed(self) -> bool:
        return bool(self.beats) and all(b.start is not None and b.end is not None for b in self.beats)


def image_name(n: int, start: float) -> str:
    """`NNN_MM-SS` — NNN 3 chữ số, MM-SS = mốc bắt đầu làm tròn xuống giây."""
    secs = int(math.floor(round(start, 6)))
    return f"{n:03d}_{secs // 60:02d}-{secs % 60:02d}"


def create_quick(root: Path, *, preset: str, title: str = "") -> QuickProject:
    root = Path(root)
    if (root / QUICK_FILE).exists():
        raise VidflowError(f"{root / QUICK_FILE} đã tồn tại.")
    for d in SUBDIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
    q = QuickProject(preset=preset, title=title)
    save_quick(root, q)
    return q


def is_quick(root: Path) -> bool:
    return (Path(root) / QUICK_FILE).is_file()


def load_quick(root: Path) -> QuickProject:
    path = Path(root) / QUICK_FILE
    if not path.is_file():
        raise VidflowError(f"Không thấy {path} — tạo bằng `vidflow quick new`.")
    try:
        return QuickProject.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    except (ValidationError, yaml.YAMLError) as e:
        raise VidflowError(f"{path} không hợp lệ: {e}") from e


def save_quick(root: Path, q: QuickProject) -> None:
    atomic_write_text(Path(root) / QUICK_FILE,
                      yaml.safe_dump(q.model_dump(), allow_unicode=True, sort_keys=False, width=1000))


def load_beats(root: Path) -> Beats | None:
    path = Path(root) / BEATS_FILE
    if not path.is_file():
        return None
    try:
        return Beats.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as e:
        raise VidflowError(f"{path} không hợp lệ: {e}") from e


def require_beats(root: Path) -> Beats:
    b = load_beats(root)
    if b is None or not b.beats:
        raise VidflowError("Chưa có beats.json — chạy `vidflow quick script` trước.")
    return b


def save_beats(root: Path, beats: Beats) -> None:
    atomic_write_text(Path(root) / BEATS_FILE, beats.model_dump_json(indent=1))


@contextmanager
def project_lock(root: Path):
    """Khóa ghi cấp project (flock trên <root>/.vidflow.lock) — UI, CLI và job Claude là các tiến trình riêng
    cùng load → sửa → ghi beats.json/quick.yaml. KHÔNG lồng nhau: hàm đã giữ khóa chỉ gọi helper không khóa."""
    root = Path(root)
    if not root.is_dir():  # chưa có project: không có gì để bảo vệ, để hàm gọi tự báo lỗi
        yield
        return
    fd = os.open(root / LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = time.monotonic() + LOCK_TIMEOUT
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise VidflowError("Project đang bận ghi, thử lại.") from None
                time.sleep(0.02)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def locked(fn):
    """Bọc hàm public (tham số đầu là root) để cả chuỗi load → sửa → ghi chạy dưới `project_lock`."""
    @functools.wraps(fn)
    def wrapper(root, *args, **kwargs):
        with project_lock(root):
            return fn(root, *args, **kwargs)
    return wrapper
