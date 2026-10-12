"""API quy trình nhanh cho UI (spec 2026-10-12, Giai đoạn 3). Mọi ghi đi qua vidflow.quick.* (cùng luật với CLI)."""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from vidflow.errors import VidflowError
from vidflow.quick import chars, clips, ops
from vidflow.quick.chars import CharRef, char_rows, lookup
from vidflow.quick.model import CHAR_ID, create_quick, is_quick, load_beats, load_quick
from vidflow.quick.preset import ID_RE, channel_refs_dir, list_presets, load_preset
from vidflow.ui.jobs import JobRunner
from vidflow.ui.quick_jobs import check_quick_job

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
    return f"/media/{name}/{quote(rel)}?v={int(f.stat().st_mtime)}"


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


Provider = Literal["flow", "gemini", "aistudio"]


class NewQuick(BaseModel):
    name: str = ""
    preset: str
    topic: str = ""
    channel_chars: list[str] | None = None  # None = mọi nhân vật bộ kênh
    image_model: str = "Nano Banana 2"
    video_model: str = ""
    resolution: str = "720p"
    image_provider: Provider = "flow"
    video_provider: Provider = "flow"
    max_clips: int = Field(default=12, ge=0, le=200)
    allow_cont: bool = True
    start: bool = True  # chạy job đề xuất ý tưởng ngay


class SettingsReq(BaseModel):
    image_model: str | None = None
    video_model: str | None = None
    resolution: str | None = None
    image_provider: Provider | None = None
    video_provider: Provider | None = None
    max_clips: int | None = None
    allow_cont: bool | None = None
    channel_chars: list[str] | None = None


class PickReq(BaseModel):
    n: int


class BeatsReq(BaseModel):
    ns: list[int] = Field(min_length=1)
    clip: bool = False


class RetryReq(BaseModel):
    ns: list[int] | None = None
    clip: bool = False


class ClipReq(BaseModel):
    ns: list[int] = Field(min_length=1)
    on: bool


class PromptReq(BaseModel):
    n: int
    prompt: str
    clip: bool = False


class BeatReq(BaseModel):
    n: int
    clip: bool = False


class QuickJobReq(BaseModel):
    kind: str
    instruction: str = ""
    options: dict = Field(default_factory=dict)
    provider: str | None = None  # ghi đè nguồn gen một lần (sheets/flow/clips)


def default_name(preset: str) -> str:
    return f"{preset}-{datetime.now():%m%d-%H%M%S}"[:41]


def ideas_hint(topic: str) -> str:
    topic = topic.strip()
    return f"Chủ đề người dùng gợi ý: {topic} — cả 5 ý tưởng xoay quanh chủ đề này." if topic else ""


def _do(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except VidflowError as e:
        raise HTTPException(422, str(e))


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

    def start_quick_job(name: str, root: Path, kind: str, **kw):
        """JobRunner.start cho job nhanh, đổi lỗi thành HTTP: tham số/điều kiện sai → 400 (mất project → 404),
        đang bận → 409."""
        try:
            return runner.start(kind, name, root, quick=True, **kw)
        except RuntimeError as e:
            raise HTTPException(409, str(e))
        except (ValueError, VidflowError) as e:
            if not is_quick(root):
                raise HTTPException(404, f"Không có video nhanh '{name}'")
            raise HTTPException(400, str(e))

    @router.post("/api/quick", status_code=201)
    def create(req: NewQuick):
        if not ID_RE.match(req.preset):
            raise HTTPException(422, f"Không có bộ kênh '{req.preset}'")
        name = req.name.strip() or default_name(req.preset)
        if not NAME_RE.match(name):
            raise HTTPException(422, "Tên thư mục chỉ gồm chữ thường không dấu, số, '-' hoặc '_'")
        root = projects_root / name
        if root.exists():
            raise HTTPException(409, f"'{name}' đã tồn tại")
        if req.max_clips > 0 and not req.video_model.strip():
            raise HTTPException(422, "Chọn model clip động (bắt buộc khi số clip tối đa > 0).")
        try:
            load_preset(req.preset)
            create_quick(root, preset=req.preset, title=req.topic.strip())
            ops.update_settings(root, image_model=req.image_model, video_model=req.video_model,
                                resolution=req.resolution, image_provider=req.image_provider,
                                video_provider=req.video_provider, max_clips=req.max_clips, allow_cont=req.allow_cont,
                                channel_chars=req.channel_chars)
        except VidflowError as e:
            shutil.rmtree(root, ignore_errors=True)
            raise HTTPException(422, str(e))
        out = {"name": name, "job": None, "warning": None}
        if req.start:
            try:  # video đã tạo xong: không chạy được việc ý tưởng chỉ là cảnh báo, không phải lỗi
                job = start_quick_job(name, root, "ideas", instruction=ideas_hint(req.topic))
                out["job"] = job.to_dict(tail=0)
            except HTTPException as e:
                out["warning"] = f"{e.detail} — bấm “Đề xuất 5 ý tưởng” sau."
        return out

    @router.post("/api/quick/{name}/settings")
    def settings(name: str, req: SettingsReq):
        q = _do(ops.update_settings, qroot(name), **req.model_dump(exclude_unset=True))
        return {"quick": q.model_dump(mode="json")}

    @router.post("/api/quick/{name}/pick")
    def pick(name: str, req: PickReq):
        return {"title": _do(ops.pick_idea, qroot(name), req.n).title}

    @router.post("/api/quick/{name}/redo")
    def redo(name: str, req: BeatsReq):
        _do(ops.mark_redo, qroot(name), req.ns, clip=req.clip)
        return {"ok": True}

    @router.post("/api/quick/{name}/retry")
    def retry(name: str, req: RetryReq):
        return {"count": _do(ops.clear_errors, qroot(name), req.ns, clip=req.clip)}

    @router.post("/api/quick/{name}/clip")
    def clip_toggle(name: str, req: ClipReq):
        _do(clips.set_clip_enabled, qroot(name), req.ns, req.on)
        return {"ok": True}

    @router.post("/api/quick/{name}/prompt")
    def prompt_ep(name: str, req: PromptReq):
        beat = _do(ops.edit_prompt, qroot(name), req.n, req.prompt, clip=req.clip)
        return {"beat": beat.model_dump(mode="json")}

    @router.post("/api/quick/{name}/override")
    def override(name: str, req: BeatReq):
        _do(ops.set_review, qroot(name), req.n, "override", score=0, issues=["người dùng duyệt tay"], clip=req.clip)
        return {"ok": True}

    @router.post("/api/quick/{name}/chars/{char_id}/promote")
    def promote(name: str, char_id: str):
        root = qroot(name)
        if not CHAR_RE.match(char_id):
            raise HTTPException(404, f"Không có nhân vật @{char_id}")
        _do(chars.promote, root, char_id)
        return {"ok": True}

    @router.post("/api/quick/{name}/jobs", status_code=202)
    def start_job(name: str, req: QuickJobReq):
        root = qroot(name)
        try:
            check_quick_job(req.kind, root, req.options, req.provider)
        except (VidflowError, ValueError) as e:
            raise HTTPException(400, str(e))
        # Job.provider = nguồn thực dùng (ghi đè, hoặc theo cài đặt) do JobRunner.start chọn qua begin_gen
        job = start_quick_job(name, root, req.kind, instruction=req.instruction, options=req.options,
                              provider=req.provider)
        return job.to_dict(tail=0)

    @router.post("/api/quick/{name}/jobs/stop")
    def stop_job(name: str):
        qroot(name)
        cur = runner.current
        if cur is None or cur.project != name or not runner.stop():
            raise HTTPException(409, "Không có việc đang chạy của video này")
        return {"stopped": True}

    return router
