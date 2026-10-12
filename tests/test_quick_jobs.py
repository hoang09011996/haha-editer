from pathlib import Path

import pytest

from vidflow.quick.jobs import CHROME_KINDS, QUICK_KINDS, claude_cmd, claude_task, review_cmd, review_task
from vidflow.quick.preset import load_preset

ROOT = Path("projects/demo")


@pytest.fixture
def preset():
    return load_preset("doodle-giai-ma")


@pytest.mark.parametrize("kind", QUICK_KINDS)
def test_task_mentions_brief_and_rules(kind, preset):
    t = claude_task(kind, ROOT, preset)
    assert "samples/doodle-brief.txt" in t
    assert str(ROOT) in t
    assert "KHÔNG" in t and "vidflow gen" in t
    assert "beats.json" in t  # không sửa tay


def test_ideas_task(preset):
    t = claude_task("ideas", ROOT, preset)
    assert "quick-writer.md" in t
    assert "quick set-ideas" in t and "5" in t


def test_script_task(preset):
    t = claude_task("script", ROOT, preset)
    assert "quick set-beats" in t and "quick-writer.md" in t


def test_prompts_task(preset):
    t = claude_task("prompts", ROOT, preset)
    assert preset.style_anchor_start in t and preset.style_anchor_end in t
    assert "quick set-prompts" in t
    assert "2 lần" in t
    assert "20" in t


def test_flow_task(preset):
    t = claude_task("flow", ROOT, preset)
    assert "flow-operator.md" in t
    assert "20" in t and "NNN_MM-SS" in t
    assert "quick set-image" in t
    assert "quick beats" in t and "--todo" in t
    assert "16:9" in t


def test_chrome_only_for_flow_kinds(preset):
    assert CHROME_KINDS == ("sheets", "flow", "clips")
    for kind in QUICK_KINDS:
        cmd = claude_cmd(kind, ROOT, preset)
        assert cmd[:4] == ["claude", "-p", "--permission-mode", "bypassPermissions"]
        assert ("--chrome" in cmd) == (kind in CHROME_KINDS)
        assert cmd[-1] == claude_task(kind, ROOT, preset)


def test_script_task_proposes_characters(preset):
    t = claude_task("script", ROOT, preset)
    assert "quick set-chars" in t and "quick chars" in t


def test_prompts_task_mentions_refs_cont_and_clips(preset):
    t = claude_task("prompts", ROOT, preset)
    assert "@TÊN" in t and "cont" in t
    assert "quick set-clip-prompts" in t and "max_clips" in t


def test_flow_task_uses_attach(preset):
    t = claude_task("flow", ROOT, preset)
    assert "attach" in t and "blocked" in t and "quick fail" in t


def test_sheets_task(preset):
    t = claude_task("sheets", ROOT, preset)
    assert "quick chars" in t and "quick char-image" in t and "--channel" in t
    assert "flow-operator.md" in t


def test_clips_task(preset):
    t = claude_task("clips", ROOT, preset)
    assert "--todo-clips" in t and "quick set-clip" in t and "quick fail" in t and "--clip" in t


def test_review_task_and_cmd(preset):
    t = review_task(ROOT, preset, 7)
    assert "mốc 7" in t and "quick set-review" in t and "--clip" not in t
    assert "--clip" in review_task(ROOT, preset, 7, clip=True)
    cmd = review_cmd(ROOT, preset, 7)
    assert "--chrome" not in cmd and cmd[-1] == t


def test_unknown_kind(preset):
    with pytest.raises(ValueError):
        claude_task("video", ROOT, preset)


from vidflow.quick.jobs import PROVIDER_LABELS


@pytest.mark.parametrize("kind", ["sheets", "flow", "clips"])
@pytest.mark.parametrize("provider", ["flow", "gemini", "aistudio"])
def test_gen_tasks_follow_provider(kind, provider, preset):
    t = claude_task(kind, ROOT, preset, provider=provider)
    assert "gen-providers.md" in t and PROVIDER_LABELS[provider] in t
    assert f"--provider {provider}" in t
    assert "quick limit" in t and "DỪNG" in t
    assert "trả phí" in t
    other = [p for p in PROVIDER_LABELS if p != provider]
    for p in other:
        assert PROVIDER_LABELS[p] not in t
    cmd = claude_cmd(kind, ROOT, preset, provider=provider)
    assert "--chrome" in cmd and cmd[-1] == t


def test_flow_default_still_mentions_flow_operator(preset):
    assert "flow-operator.md" in claude_task("flow", ROOT, preset)


def test_unknown_provider_rejected(preset):
    with pytest.raises(ValueError):
        claude_task("flow", ROOT, preset, provider="midjourney")
