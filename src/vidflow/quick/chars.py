"""Nhân vật @TÊN (spec 2026-10-12): bộ kênh + riêng video, ảnh sheet theo quy ước tên file, tách @TÊN từ prompt."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vidflow.errors import VidflowError
from vidflow.quick.model import IMAGE_EXTS, Character, QuickProject, load_beats, load_quick, locked, save_quick
from vidflow.quick.preset import Preset, channel_refs_dir, load_preset, save_preset

REF_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_]*)")
VIDEO_REFS = "refs"
COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}")


@dataclass
class CharRef:
    char: Character
    scope: Literal["channel", "video"]
    image: Path | None


def find_image(folder: Path, char_id: str) -> Path | None:
    for ext in (".png", ".jpg", ".webp"):
        f = Path(folder) / f"{char_id}{ext}"
        if f.is_file():
            return f
    return None


def parse_refs(text: str) -> list[str]:
    """Các @TÊN theo thứ tự xuất hiện, không trùng. @tên có chữ thường → lỗi (phải IN HOA)."""
    out: list[str] = []
    for m in REF_RE.finditer(text or ""):
        name = m.group(1)
        if name != name.upper():
            raise VidflowError(f"@{name}: tên nhân vật phải viết IN HOA (@{name.upper()}).")
        if name not in out:
            out.append(name)
    return out


def lookup(root: Path, q: QuickProject | None = None, preset: Preset | None = None) -> dict[str, CharRef]:
    root = Path(root)
    q = q or load_quick(root)
    preset = preset or load_preset(q.preset)
    out: dict[str, CharRef] = {}
    cdir = channel_refs_dir(preset)
    for c in preset.characters:
        if q.channel_chars is None or c.id in q.channel_chars:
            out[c.id] = CharRef(c, "channel", find_image(cdir, c.id))
    for c in q.characters:
        if c.id in out:  # đã được đưa vào bộ kênh (promote từ video khác) — bộ kênh thắng
            continue
        out[c.id] = CharRef(c, "video", find_image(root / VIDEO_REFS, c.id))
    return out


def check_known(names: list[str], known: dict[str, CharRef]) -> None:
    unknown = [n for n in names if n not in known]
    if unknown:
        have = ", ".join("@" + k for k in known) or "(chưa có nhân vật nào)"
        raise VidflowError(f"Prompt nhắc nhân vật chưa khai báo: {', '.join('@' + u for u in unknown)}. Có: {have}")


def _used_ids(root: Path) -> set[str]:
    beats = load_beats(root)
    used: set[str] = set()
    for b in beats.beats if beats else []:
        used.update(b.refs)
        used.update(parse_refs(b.clip.prompt))
    return used


@locked
def set_chars(root: Path, items: list[dict]) -> QuickProject:
    """Ghi toàn bộ nhân vật riêng của video (quick-writer đề xuất, người dùng sửa)."""
    root = Path(root)
    q = load_quick(root)
    preset = load_preset(q.preset)
    try:
        new = [Character.model_validate(i) for i in items]
    except Exception as e:
        raise VidflowError(f"Nhân vật không hợp lệ (id IN HOA 2–24 ký tự A-Z0-9_, cần desc): {e}") from e
    bad = [c.id for c in new if c.color and not COLOR_RE.fullmatch(c.color)]
    if bad:  # màu đi thẳng vào style của UI: chỉ nhận #RRGGBB
        raise VidflowError(f"Màu nhân vật phải dạng #RRGGBB hoặc để trống: {', '.join('@' + i for i in bad)}")
    ids = [c.id for c in new]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise VidflowError(f"Trùng id nhân vật: {', '.join(dup)}")
    clash = sorted(set(ids) & {c.id for c in preset.characters})
    if clash:
        raise VidflowError(f"Trùng nhân vật của bộ kênh: {', '.join(clash)}")
    via_channel = {c.id for c in preset.characters if q.channel_chars is None or c.id in q.channel_chars}
    in_use = sorted(({c.id for c in q.characters} - set(ids) - via_channel) & _used_ids(root))
    if in_use:
        raise VidflowError(f"Không xóa được nhân vật đang dùng trong prompt: {', '.join('@' + i for i in in_use)}")
    q.characters = new
    save_quick(root, q)
    return q


@locked
def set_char_image(root: Path, char_id: str, src: Path, *, channel: bool = False) -> Path:
    """Gắn ảnh sheet: video → <project>/refs/<ID>.<ext>; channel → presets/refs/<preset>/<ID>.<ext>."""
    root, src = Path(root), Path(src)
    if not src.is_file():
        raise VidflowError(f"Không thấy file ảnh {src}")
    ext = IMAGE_EXTS.get(src.suffix.lower())
    if not ext:
        raise VidflowError(f"Định dạng ảnh không hỗ trợ: {src.suffix} (dùng jpg/png/webp)")
    q = load_quick(root)
    preset = load_preset(q.preset)
    channel_ids = {c.id for c in preset.characters}
    if channel:
        if char_id not in channel_ids:
            raise VidflowError(f"Bộ kênh {preset.id} không có nhân vật @{char_id}.")
        folder = channel_refs_dir(preset)
    else:
        if char_id not in {c.id for c in q.characters}:
            hint = " (là nhân vật bộ kênh — thêm --channel)" if char_id in channel_ids else ""
            raise VidflowError(f"Video không có nhân vật @{char_id}{hint}.")
        folder = root / VIDEO_REFS
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{char_id}{ext}"
    old = find_image(folder, char_id)
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    if old and old.resolve() != dest.resolve():
        old.unlink()
    return dest


@locked
def promote(root: Path, char_id: str) -> Preset:
    """Chuyển nhân vật riêng của video vào bộ kênh (kèm ảnh). Ghi lại YAML bộ kênh."""
    root = Path(root)
    q = load_quick(root)
    preset = load_preset(q.preset)
    c = next((x for x in q.characters if x.id == char_id), None)
    if c is None:
        raise VidflowError(f"Video không có nhân vật riêng @{char_id}.")
    if char_id in {x.id for x in preset.characters}:
        raise VidflowError(f"Bộ kênh {preset.id} đã có nhân vật @{char_id}.")
    preset.characters.append(c)
    save_preset(preset)
    img = find_image(root / VIDEO_REFS, char_id)
    if img:
        folder = channel_refs_dir(preset)
        folder.mkdir(parents=True, exist_ok=True)
        shutil.move(str(img), str(folder / img.name))
    q.characters = [x for x in q.characters if x.id != char_id]
    if q.channel_chars is not None and char_id not in q.channel_chars:
        q.channel_chars.append(char_id)
    save_quick(root, q)
    return preset


def char_rows(root: Path) -> list[dict]:
    """Cho `quick chars` và UI: mỗi nhân vật + ảnh + số mốc dùng + số mốc chờ ảnh bị chặn vì thiếu sheet."""
    root = Path(root)
    beats = load_beats(root)
    bl = beats.beats if beats else []
    rows = []
    for cid, ref in lookup(root).items():
        uses = [b for b in bl if cid in b.refs or cid in parse_refs(b.clip.prompt)]
        rows.append({**ref.char.model_dump(), "scope": ref.scope,
                     "image": str(ref.image) if ref.image else None,
                     "uses": len(uses),
                     "blocked": 0 if ref.image else sum(1 for b in uses if b.status in ("pending", "redo"))})
    return rows
