"""Bộ kênh (preset): file brief gốc + câu neo phong cách + giọng đọc."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Callable

import yaml
from pydantic import BaseModel, ValidationError

from vidflow.errors import VidflowError
from vidflow.state import atomic_write_text

REPO = Path(__file__).resolve().parents[3]
PRESETS_DIR = REPO / "presets"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class PresetVoice(BaseModel):
    name: str = "Charon"
    style: str = ""


class Preset(BaseModel):
    id: str
    name: str
    brief_file: str
    aspect: str = "16:9"
    style_anchor_start: str
    style_anchor_end: str
    voice: PresetVoice = PresetVoice()
    language: str = "vi"


def brief_path(p: Preset) -> Path:
    path = Path(p.brief_file).expanduser()
    return path if path.is_absolute() else REPO / path


def _dir(presets_dir: Path | None) -> Path:
    return Path(presets_dir) if presets_dir else PRESETS_DIR


def load_preset(preset_id: str, *, presets_dir: Path | None = None) -> Preset:
    path = _dir(presets_dir) / f"{preset_id}.yaml"
    if not path.is_file():
        raise VidflowError(f"Không có bộ kênh '{preset_id}' ({path}).")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.setdefault("id", preset_id)
        return Preset.model_validate(data)
    except (ValidationError, yaml.YAMLError) as e:
        raise VidflowError(f"{path} không hợp lệ: {e}") from e


def list_presets(*, presets_dir: Path | None = None) -> list[Preset]:
    d = _dir(presets_dir)
    return [load_preset(f.stem, presets_dir=d) for f in sorted(d.glob("*.yaml"))] if d.is_dir() else []


def save_preset(p: Preset, *, presets_dir: Path | None = None) -> Path:
    d = _dir(presets_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{p.id}.yaml"
    atomic_write_text(path, yaml.safe_dump(p.model_dump(), allow_unicode=True, sort_keys=False, width=1000))
    return path


def docx_to_text_textutil(path: Path) -> str:
    """macOS: `textutil -convert txt -stdout`."""
    try:
        r = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(path)], capture_output=True, text=True)
    except FileNotFoundError as e:
        raise VidflowError("Không có `textutil` (chỉ macOS) — hãy lưu brief thành .txt rồi import.") from e
    if r.returncode != 0:
        raise VidflowError(f"textutil không đọc được {path}: {r.stderr.strip()}")
    return r.stdout


EXTRACT_PROMPT = """Đọc file brief kênh video tại {path}. Trả về DUY NHẤT một object JSON (không markdown, không giải thích) với các khóa:
name (tên kênh ngắn, tiếng Việt), aspect ("16:9" hoặc "9:16"), language (mã ngôn ngữ lời dẫn, ví dụ "vi"),
style_anchor_start (câu neo phong cách MỞ ĐẦU mỗi image prompt — chép NGUYÊN VĂN từng ký tự từ brief, không thêm dấu ngoặc/dấu sao bao quanh),
style_anchor_end (câu khóa phong cách KẾT THÚC mỗi image prompt — chép NGUYÊN VĂN),
voice: {{"name": tên giọng Gemini TTS phù hợp người dẫn (một trong: Charon, Kore, Puck, Fenrir, Aoede, Leda, Orus, Zephyr, Sadaltager, Iapetus), "style": mô tả cách đọc ngắn bằng tiếng Việt theo brief}}."""


def extract_with_claude(text_path: Path) -> Callable[[str], dict]:
    def run(_text: str) -> dict:
        r = subprocess.run(["claude", "-p", "--output-format", "text", EXTRACT_PROMPT.format(path=text_path)],
                           capture_output=True, text=True, cwd=REPO)
        if r.returncode != 0:
            raise VidflowError(f"Claude trích preset lỗi: {r.stderr.strip() or r.stdout.strip()}")
        return parse_json_object(r.stdout)

    return run


def parse_json_object(out: str) -> dict:
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        raise VidflowError(f"Không tìm thấy JSON trong kết quả: {out[:300]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise VidflowError(f"JSON preset sai: {e}") from e


def _rel_to_repo(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def import_preset(src: Path, *, preset_id: str, extract: Callable[[str], dict] | None = None,
                  presets_dir: Path | None = None, docx_to_text: Callable[[Path], str] = docx_to_text_textutil,
                  force: bool = False) -> Preset:
    """Tạo preset từ brief .docx/.txt. `extract(text) -> dict` (mặc định: job `claude -p`) trích các trường;
    câu neo phải xuất hiện nguyên văn trong brief."""
    src = Path(src)
    if not ID_RE.match(preset_id):
        raise VidflowError("id bộ kênh chỉ gồm chữ thường, số, gạch ngang (ví dụ doodle-giai-ma).")
    if not src.is_file():
        raise VidflowError(f"Không thấy file {src}")
    d = _dir(presets_dir)
    if (d / f"{preset_id}.yaml").exists() and not force:
        raise VidflowError(f"Bộ kênh '{preset_id}' đã có — dùng --force để ghi đè.")
    if src.suffix.lower() in (".docx", ".doc", ".rtf"):
        text = docx_to_text(src)
        text_path = d / "briefs" / f"{preset_id}.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(text_path, text)
    else:
        text = src.read_text(encoding="utf-8")
        text_path = src
    data = dict((extract or extract_with_claude(text_path))(text))
    for key in ("style_anchor_start", "style_anchor_end"):
        val = str(data.get(key, "")).strip()
        if not val or val not in text:
            raise VidflowError(f"{key} không trích nguyên văn từ brief: {val!r}")
        data[key] = val
    data.update(id=preset_id, brief_file=_rel_to_repo(text_path))
    data.setdefault("name", preset_id)
    try:
        p = Preset.model_validate(data)
    except ValidationError as e:
        raise VidflowError(f"Dữ liệu preset trích được không hợp lệ: {e}") from e
    save_preset(p, presets_dir=d)
    return p
