from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from vidflow.config import Config
from vidflow.cost import check_budget, plan_gen
from vidflow.errors import ScriptError, VidflowError
from vidflow.inputs import compose_veo_prompt, scene_ref_images
from vidflow.project import Project
from vidflow.retry import with_retry
from vidflow.state import PendingOp, Take


@dataclass
class PollResult:
    done: bool
    video: Any = None
    error: str | None = None


class VideoClient(Protocol):
    def submit(self, *, prompt: str, aspect: str, duration: int, resolution: str, model: str,
               ref_images: list[Path]) -> str: ...

    def poll(self, op_name: str) -> PollResult: ...

    def download(self, video: Any, dest: Path) -> None: ...


@dataclass
class GenReport:
    created: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_gen(project: Project, cfg: Config, client: VideoClient, *, scene_ids: list[str] | None = None,
            takes: int = 1, force: bool = False, poll_interval: float = 10.0, timeout_s: float = 900.0,
            sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
            now: Callable[[], str] = _now_iso) -> GenReport:
    script, state = project.load_script(), project.load_state()
    est = plan_gen(project, script, state, cfg, scene_ids=scene_ids, takes=takes, force=force)
    check_budget(script, state, est)
    scenes = {s.id: s for s in script.scenes}
    report = GenReport()

    for job in est.jobs:
        scene = scenes[job.scene_id]
        op_name = with_retry(lambda: client.submit(
            prompt=compose_veo_prompt(script, scene), aspect=script.aspect, duration=scene.duration,
            resolution=cfg.veo_resolution, model=cfg.veo_model,
            ref_images=scene_ref_images(project, script, scene)), sleep=sleep)
        state.scene(job.scene_id).pending.append(
            PendingOp(name=op_name, input_hash=job.input_hash, seconds=job.seconds, submitted_at=now()))
        project.save_state(state)

    wanted = set(scene_ids) if scene_ids else set(scenes)
    deadline = clock() + timeout_s
    while True:
        open_ops = [(sid, op) for sid, st in state.scenes.items() if sid in wanted for op in list(st.pending)]
        if not open_ops:
            return report
        for sid, op in open_ops:
            res = with_retry(lambda: client.poll(op.name), sleep=sleep)
            if not res.done:
                continue
            st = state.scene(sid)
            st.pending.remove(op)
            if res.error:
                st.errors.append(f"{now()} {res.error}")
                report.failed[sid] = res.error
            else:
                dest = project.clips_dir / f"{sid}_t{len(st.takes) + 1}.mp4"
                with_retry(lambda: client.download(res.video, dest), sleep=sleep)
                cost = round(op.seconds * cfg.veo_price_per_second, 4)
                st.takes.append(Take(file=project.rel(dest), input_hash=op.input_hash, cost_usd=cost,
                                     created_at=now()))
                state.spent_usd = round(state.spent_usd + cost, 4)
                if st.picked is None or st.takes[st.picked].input_hash != op.input_hash:
                    st.picked = len(st.takes) - 1
                report.created.append(project.rel(dest))
            project.save_state(state)
        if any(st.pending for sid, st in state.scenes.items() if sid in wanted):
            if clock() > deadline:
                raise VidflowError("Hết thời gian chờ Veo; chạy lại `vidflow gen` để tiếp tục chờ (job không bị tạo lại).")
            sleep(poll_interval)


def pick_take(project: Project, scene_id: str, take_number: int) -> str:
    project.load_script().scene(scene_id)
    state = project.load_state()
    st = state.scene(scene_id)
    if not 1 <= take_number <= len(st.takes):
        raise ScriptError(f"Cảnh {scene_id} có take 1..{len(st.takes)}, nhận {take_number}")
    st.picked = take_number - 1
    project.save_state(state)
    return st.takes[st.picked].file
