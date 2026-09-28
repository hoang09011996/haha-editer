import dataclasses

import pytest

from vidflow.cost import check_budget, plan_gen
from vidflow.errors import BudgetError, ConfigError
from vidflow.inputs import video_hash
from vidflow.state import PendingOp, Take


def test_only_approved_scenes_with_prompt(project, cfg):
    script = project.load_script()
    est = plan_gen(project, script, project.load_state(), cfg)
    assert [j.scene_id for j in est.jobs] == ["s01", "s02"]
    assert est.seconds == 12
    assert est.usd == 6.0
    assert est.skipped == {"s03": "chưa approved"}


def test_empty_prompt_skipped(project, cfg):
    script = project.load_script()
    script.scenes[0].veo_prompt = "  "
    est = plan_gen(project, script, project.load_state(), cfg)
    assert est.skipped["s01"] == "veo_prompt trống"


def test_existing_matching_take_and_pending_count(project, cfg):
    script = project.load_script()
    state = project.load_state()
    h1 = video_hash(project, script, script.scene("s01"), cfg)
    h2 = video_hash(project, script, script.scene("s02"), cfg)
    state.scene("s01").takes.append(Take(file="clips/a.mp4", input_hash=h1, cost_usd=4, created_at="t"))
    state.scene("s02").pending.append(PendingOp(name="op", input_hash=h2, seconds=4, submitted_at="t"))
    est = plan_gen(project, script, state, cfg)
    assert est.jobs == []
    assert est.skipped["s01"] == "đã có clip khớp prompt hiện tại"
    est2 = plan_gen(project, script, state, cfg, scene_ids=["s01"], takes=2)
    assert len(est2.jobs) == 1
    est3 = plan_gen(project, script, state, cfg, scene_ids=["s01"], force=True)
    assert len(est3.jobs) == 1


def test_stale_take_needs_regen(project, cfg):
    script = project.load_script()
    state = project.load_state()
    state.scene("s01").takes.append(Take(file="clips/a.mp4", input_hash="old", cost_usd=4, created_at="t"))
    est = plan_gen(project, script, state, cfg, scene_ids=["s01"])
    assert len(est.jobs) == 1


def test_price_required(project, cfg):
    script = project.load_script()
    with pytest.raises(ConfigError, match="veo_price_per_second"):
        plan_gen(project, script, project.load_state(), dataclasses.replace(cfg, veo_price_per_second=None))


def test_budget(project, cfg):
    script = project.load_script()
    state = project.load_state()
    est = plan_gen(project, script, state, cfg)
    check_budget(script, state, est)
    state.spent_usd = 5.0
    with pytest.raises(BudgetError, match="Vượt ngân sách"):
        check_budget(script, state, est)
