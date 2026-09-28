from __future__ import annotations

from dataclasses import dataclass, field

from vidflow.config import Config
from vidflow.errors import BudgetError, ConfigError, ScriptError
from vidflow.inputs import video_hash
from vidflow.project import Project
from vidflow.schema import Script
from vidflow.state import ProjectState, SceneState


@dataclass(frozen=True)
class GenJob:
    scene_id: str
    input_hash: str
    seconds: int


@dataclass(frozen=True)
class Estimate:
    jobs: list[GenJob]
    seconds: int
    usd: float
    skipped: dict[str, str] = field(default_factory=dict)


def plan_gen(project: Project, script: Script, state: ProjectState, cfg: Config, *,
             scene_ids: list[str] | None = None, takes: int = 1, force: bool = False) -> Estimate:
    if cfg.veo_price_per_second is None:
        raise ConfigError("Chưa đặt veo_price_per_second trong vidflow.toml "
                          "(USD/giây, lấy theo bảng giá Veo hiện hành của Google).")
    if takes < 1:
        raise ScriptError("--takes phải >= 1")
    selected = script.scenes if not scene_ids else [script.scene(i) for i in scene_ids]
    jobs: list[GenJob] = []
    skipped: dict[str, str] = {}
    for scene in selected:
        if scene.status != "approved":
            skipped[scene.id] = "chưa approved"
            continue
        if not scene.veo_prompt.strip():
            skipped[scene.id] = "veo_prompt trống"
            continue
        h = video_hash(project, script, scene, cfg)
        st = state.scenes.get(scene.id) or SceneState()
        have = sum(t.input_hash == h for t in st.takes) + sum(p.input_hash == h for p in st.pending)
        need = takes if force else max(0, takes - have)
        if need == 0:
            skipped[scene.id] = "đã có clip khớp prompt hiện tại"
            continue
        jobs.extend(GenJob(scene.id, h, scene.duration) for _ in range(need))
    seconds = sum(j.seconds for j in jobs)
    return Estimate(jobs=jobs, seconds=seconds, usd=round(seconds * cfg.veo_price_per_second, 2), skipped=skipped)


def check_budget(script: Script, state: ProjectState, est: Estimate) -> None:
    if state.spent_usd + est.usd > script.budget_usd:
        raise BudgetError(
            f"Vượt ngân sách: đã tiêu {state.spent_usd:.2f} + dự kiến {est.usd:.2f} > budget {script.budget_usd:.2f} USD. "
            "Tăng budget_usd trong script.yaml hoặc bớt cảnh."
        )
