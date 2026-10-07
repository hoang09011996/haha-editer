from pathlib import Path

import pytest

from vidflow.quick.jobs import QUICK_KINDS, claude_cmd, claude_task
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


def test_chrome_only_for_flow(preset):
    for kind in QUICK_KINDS:
        cmd = claude_cmd(kind, ROOT, preset)
        assert cmd[:4] == ["claude", "-p", "--permission-mode", "bypassPermissions"]
        assert ("--chrome" in cmd) == (kind == "flow")
        assert cmd[-1] == claude_task(kind, ROOT, preset)


def test_unknown_kind(preset):
    with pytest.raises(ValueError):
        claude_task("video", ROOT, preset)
