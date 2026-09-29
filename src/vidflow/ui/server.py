"""API + trang web cục bộ cho vidflow (chỉ nghe 127.0.0.1)."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from vidflow.config import load_config
from vidflow.errors import VidflowError
from vidflow.inputs import scene_fields_hash
from vidflow.project import Project, create_project
from vidflow.schema import FlowSettings, Script
from vidflow.status import scene_rows
from vidflow.ui.jobs import KINDS, JobRunner
from vidflow.ui.suggest import Suggester

STATIC = Path(__file__).parent / "static"
MEDIA_DIRS = ("audio", "clips", "refs", "music", "inbox")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


class NewProject(BaseModel):
    name: str
    title: str
    idea: str = ""
    aspect: str = "9:16"
    video_model: str = ""
    resolution: str = "720p"


class JobRequest(BaseModel):
    kind: str
    scenes: list[str] | None = None
    instruction: str = ""


class SuggestRequest(BaseModel):
    field: str
    label: str
    current: str = ""
    project: str | None = None
    scene_id: str | None = None


class PickRequest(BaseModel):
    scene: str
    take: int


def create_app(projects_root: Path, runner: JobRunner | None = None, config_path: Path | None = None,
               suggester: Suggester | None = None) -> FastAPI:
    projects_root = Path(projects_root).resolve()
    projects_root.mkdir(parents=True, exist_ok=True)
    runner = runner or JobRunner()
    suggester = suggester or Suggester()
    app = FastAPI(title="vidflow")

    def open_project(name: str) -> Project:
        if not NAME_RE.match(name) or not (projects_root / name / "script.yaml").is_file():
            raise HTTPException(404, f"Không có project '{name}'")
        return Project.open(projects_root / name)

    def load(p: Project) -> Script:
        try:
            return p.load_script()
        except VidflowError as e:
            raise HTTPException(422, str(e))

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC / "index.html").read_text(encoding="utf-8")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/api/projects")
    def list_projects():
        out = []
        for d in sorted(projects_root.iterdir()):
            if (d / "script.yaml").is_file():
                try:
                    s = Project(d).load_script()
                    out.append({"name": d.name, "title": s.title, "scenes": len(s.scenes),
                                "approved": sum(x.status == "approved" for x in s.scenes), "aspect": s.aspect})
                except VidflowError as e:
                    out.append({"name": d.name, "title": d.name, "error": str(e)})
        return out

    @app.post("/api/projects", status_code=201)
    def new_project(req: NewProject):
        if not NAME_RE.match(req.name):
            raise HTTPException(422, "Tên project chỉ gồm chữ thường không dấu, số, '-' hoặc '_'")
        if (projects_root / req.name).exists():
            raise HTTPException(409, f"Project '{req.name}' đã tồn tại")
        try:
            p = create_project(projects_root / req.name, title=req.title, aspect=req.aspect)
            script = p.load_script()
            script.profile.idea = req.idea
            script.flow = FlowSettings(video_model=req.video_model, resolution=req.resolution)
            p.save_script(script)
        except (VidflowError, ValidationError) as e:
            raise HTTPException(422, str(e))
        return {"name": req.name}

    @app.get("/api/projects/{name}")
    def get_project(name: str):
        p = open_project(name)
        script = load(p)
        state = p.load_state()
        cfg = load_config(config_path)
        try:
            status = scene_rows(p, script, state, cfg)
        except VidflowError as e:
            status = [{"id": "-", "error": str(e)}]
        refs = sorted(f.name for f in p.refs_dir.iterdir() if f.is_file()) if p.refs_dir.is_dir() else []
        job = runner.current.to_dict(tail=4000) if runner.current and runner.current.project == name else None
        return {
            "name": name,
            "script": script.model_dump(mode="json"),
            "state": state.model_dump(mode="json"),
            "status": status,
            "prompt_stale": {s.id: (not s.veo_prompt.strip()) or s.prompt_fields_hash != scene_fields_hash(script, s)
                             for s in script.scenes},
            "refs": refs,
            "job": job,
        }

    @app.put("/api/projects/{name}/script")
    def put_script(name: str, data: dict):
        p = open_project(name)
        try:
            script = Script.model_validate(data)
        except ValidationError as e:
            raise HTTPException(422, "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()))
        p.save_script(script)
        return {"ok": True}

    @app.post("/api/projects/{name}/pick")
    def pick(name: str, req: PickRequest):
        from vidflow.video import pick_take
        try:
            return {"file": pick_take(open_project(name), req.scene, req.take)}
        except VidflowError as e:
            raise HTTPException(422, str(e))

    @app.post("/api/projects/{name}/jobs", status_code=202)
    def start_job(name: str, req: JobRequest):
        p = open_project(name)
        if req.kind not in KINDS:
            raise HTTPException(422, f"Việc không hỗ trợ: {req.kind}")
        try:
            job = runner.start(req.kind, name, p.root, req.scenes, req.instruction)
        except RuntimeError as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            raise HTTPException(422, str(e))
        return job.to_dict(tail=0)

    @app.post("/api/suggest")
    def suggest(req: SuggestRequest):
        context: dict = {}
        if req.project:
            script = load(open_project(req.project))
            context = {"title": script.title, "profile": script.profile.model_dump(), "aspect": script.aspect,
                       "characters": [c.model_dump(exclude={"description", "ref_image"}) for c in script.characters],
                       "locations": [l.model_dump() for l in script.locations],
                       "scenes": [{"id": s.id, "purpose": s.purpose, "narration": s.narration, "action": s.action,
                                   "duration": s.duration} for s in script.scenes]}
            if req.scene_id:
                sc = next((s for s in script.scenes if s.id == req.scene_id), None)
                if sc:
                    context["current_scene"] = sc.model_dump(exclude={"veo_prompt", "veo_prompt_vi", "prompt_fields_hash"})
        try:
            return {"suggestions": suggester.suggest(req.label, req.field, req.current, context)}
        except Exception as e:  # LLM lỗi / trả sai định dạng
            raise HTTPException(502, f"AI gợi ý lỗi: {e}")

    @app.get("/api/jobs/current")
    def current_job():
        return runner.current.to_dict() if runner.current else {"state": "idle"}

    @app.get("/media/{name}/{path:path}")
    def media(name: str, path: str):
        p = open_project(name)
        target = (p.root / path).resolve()
        allowed = [(p.root / d).resolve() for d in MEDIA_DIRS]
        if not any(d in target.parents for d in allowed) or not target.is_file():
            raise HTTPException(404, "Không có file")
        return FileResponse(target)

    return app


def serve(projects_root: Path, host: str = "127.0.0.1", port: int = 8777, config_path: Path | None = None) -> None:
    import uvicorn

    uvicorn.run(create_app(projects_root, config_path=config_path), host=host, port=port, log_level="warning")
