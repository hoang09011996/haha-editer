"""API quy trình nhanh cho UI (spec 2026-10-12, Giai đoạn 3). Mọi ghi đi qua vidflow.quick.* (cùng luật với CLI)."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from vidflow.errors import VidflowError
from vidflow.quick import ops
from vidflow.quick.chars import CharRef, char_rows, lookup
from vidflow.quick.model import CHAR_ID, is_quick, load_beats, load_quick
from vidflow.quick.preset import ID_RE, channel_refs_dir, list_presets, load_preset
from vidflow.ui.jobs import JobRunner

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
CHAR_RE = re.compile(CHAR_ID)
SHEET_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,23}\.(png|jpg|webp)$")


def media_url(root: Path, name: str, rel: str | None) -> str | None:
    """URL /media của file trong project, kèm ?v=mtime để trình duyệt tải lại khi file đổi. None nếu chưa có file."""
    if not rel:
        return None
    f = Path(root) / rel
    if not f.is_file():
        return None
    return f"/media/{name}/{rel}?v={int(f.stat().st_mtime)}"


def char_url(name: str, preset_id: str, ref: CharRef | None) -> str | None:
    if ref is None or ref.image is None or not ref.image.is_file():
        return None
    v = int(ref.image.stat().st_mtime)
    if ref.scope == "channel":
        return f"/media/_presets/{preset_id}/{ref.image.name}?v={v}"
    return f"/media/{name}/refs/{ref.image.name}?v={v}"


def beat_state(row: dict, flow_running: bool) -> str:
    """Trạng thái hiển thị của mốc (UI luôn kèm chữ): ok | gen | error | blocked | redo | pending.
    "gen" = job Flow của video đang chạy và mốc gen được ngay; "blocked" = thiếu ảnh nhân vật."""
    if row["error"]:
        return "error"
    if row["status"] == "ok" and row["image"]:
        return "ok"
    reason = row.get("blocked") or ""
    if reason.startswith("thiếu ảnh"):
        return "blocked"
    review = row["review"]
    wants = (bool(row["prompt"]) and review is not None and review["verdict"] in ops.PASSING
             and row["start"] is not None and not reason)
    if flow_running and wants:
        return "gen"
    return "redo" if row["status"] == "redo" else "pending"


def beat_rows(root: Path, name: str, flow_running: bool) -> list[dict]:
    beats = load_beats(root)
    if beats is None or not beats.beats:
        return []
    q = load_quick(root)
    preset = load_preset(q.preset)
    known = lookup(root, q, preset)
    out: list[dict] = []
    prev: dict | None = None
    for r in ops.list_beats(root)["beats"]:
        attach = [{"kind": "char", "id": cid, "url": char_url(name, preset.id, known.get(cid))} for cid in r["refs"]]
        if r["cont"] and prev is not None:
            attach.append({"kind": "prev", "n": prev["n"], "url": media_url(root, name, prev["image"])})
        r.update(state=beat_state(r, flow_running), image_url=media_url(root, name, r["image"]),
                 clip_url=media_url(root, name, r["clip"]["file"]), attach=attach)
        out.append(r)
        prev = r
    return out


def char_list(root: Path, name: str) -> list[dict]:
    q = load_quick(root)
    preset = load_preset(q.preset)
    known = lookup(root, q, preset)
    rows = char_rows(root)
    for r in rows:
        r["image_url"] = char_url(name, preset.id, known.get(r["id"]))
        r.pop("image", None)  # đường dẫn tuyệt đối trên máy — không trả ra ngoài
    return rows


def renders(root: Path, name: str) -> list[dict]:
    out_dir = Path(root) / "out"
    files = sorted(out_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True) if out_dir.is_dir() else []
    return [{"file": f"out/{f.name}", "url": media_url(root, name, f"out/{f.name}"),
             "size_mb": round(f.stat().st_size / 1e6, 1),
             "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")} for f in files]


def quick_router(projects_root: Path, runner: JobRunner) -> APIRouter:
    router = APIRouter()
    projects_root = Path(projects_root)

    def qroot(name: str) -> Path:
        if not NAME_RE.match(name) or not is_quick(projects_root / name):
            raise HTTPException(404, f"Không có video nhanh '{name}'")
        return projects_root / name

    def job_of(name: str):
        cur = runner.current
        return cur if cur is not None and cur.project == name else None

    @router.get("/api/quick")
    def list_quick():
        out = []
        for d in sorted(projects_root.iterdir()):
            if not (d.is_dir() and NAME_RE.match(d.name) and is_quick(d)):
                continue
            try:
                q, b = load_quick(d), load_beats(d)
                out.append({"name": d.name, "title": q.title or d.name, "preset": q.preset, "stage": q.stage,
                            "beats": len(b.beats) if b else 0})
            except VidflowError as e:
                out.append({"name": d.name, "title": d.name, "error": str(e)})
        return out

    @router.get("/api/presets")
    def presets():
        try:
            return [{"id": p.id, "name": p.name, "aspect": p.aspect,
                     "characters": [c.model_dump() for c in p.characters]} for p in list_presets()]
        except VidflowError as e:
            raise HTTPException(422, str(e))

    @router.get("/api/quick/{name}")
    def get_quick(name: str):
        root = qroot(name)
        job = job_of(name)
        flow_running = job is not None and job.kind == "flow" and job.state == "running"
        try:
            q = load_quick(root)
            preset = load_preset(q.preset)
            beats = load_beats(root)
            return {"name": name, "quick": q.model_dump(mode="json"),
                    "preset": {"id": preset.id, "name": preset.name, "aspect": preset.aspect},
                    "aspect": beats.aspect if beats else preset.aspect,
                    "status": ops.status_summary(root),
                    "beats": beat_rows(root, name, flow_running),
                    "characters": char_list(root, name),
                    "renders": renders(root, name),
                    "voice_url": media_url(root, name, ops.VOICE_FILE),
                    "job": job.to_dict(tail=4000) if job else None}
        except VidflowError as e:
            raise HTTPException(422, str(e))

    @router.get("/media/_presets/{preset_id}/{filename}")
    def preset_media(preset_id: str, filename: str):
        if not ID_RE.match(preset_id) or not SHEET_RE.match(filename):
            raise HTTPException(404, "Không có file")
        try:
            folder = channel_refs_dir(load_preset(preset_id))
        except VidflowError:
            raise HTTPException(404, "Không có file")
        f = folder / filename
        if not f.is_file():
            raise HTTPException(404, "Không có file")
        return FileResponse(f)

    return router
