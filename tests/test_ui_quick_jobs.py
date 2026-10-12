import sys

import pytest

from vidflow.quick import ops
from vidflow.quick.model import load_quick

from vidflow.errors import VidflowError
from vidflow.quick.model import create_quick
from vidflow.ui.jobs import JobRunner
from vidflow.ui.quick_jobs import QUICK_UI_KINDS, build_quick_cmd, check_quick_job, option_args


def test_kinds():
    assert QUICK_UI_KINDS == ("ideas", "script", "prompts", "sheets", "flow", "clips", "voice", "render", "build")


def test_cli_kinds(qroot):
    assert build_quick_cmd("voice", qroot) == [sys.executable, "-m", "vidflow", "quick", "voice", "-p", str(qroot)]
    assert build_quick_cmd("build", qroot, options={"zoom": False, "subtitles": True})[-2:] == ["--no-zoom", "--subtitles"]


def test_render_options_become_flags(qroot):
    cmd = build_quick_cmd("render", qroot, options={"music": False, "resolution": "720p", "zoom": False, "transition": "cut",
                                                    "clip_fit": "speed", "subtitles": True, "clip_audio": True, "logo": False})
    assert cmd[3:7] == ["quick", "render", "-p", str(qroot)]
    assert cmd[7:] == ["--resolution", "720p", "--transition", "cut", "--clip-fit", "speed",
                       "--no-zoom", "--subtitles", "--clip-audio", "--no-logo", "--no-music"]


@pytest.mark.parametrize("kind,opts", [
    ("render", {"resolution": "4k"}),
    ("render", {"resolution": "1080p; rm -rf /"}),
    ("render", {"zoom": "yes"}),
    ("render", {"output": "/tmp/x.mp4"}),
    ("build", {"music": True}),
    ("flow", {"zoom": True}),
])
def test_bad_options_rejected(kind, opts):
    with pytest.raises(ValueError):
        option_args(kind, opts)


def test_claude_kinds(qroot):
    flow = build_quick_cmd("flow", qroot)
    assert flow[0] == "claude" and "--chrome" in flow and "flow-operator.md" in flow[-1]
    ideas = build_quick_cmd("ideas", qroot, instruction="chủ đề tổ tiên")
    assert "--chrome" not in ideas and "quick set-ideas" in ideas[-1]
    assert ideas[-1].endswith('"chủ đề tổ tiên".')
    assert build_quick_cmd("voice", qroot, instruction="bỏ qua") == build_quick_cmd("voice", qroot)


def test_check_quick_job(qroot, tmp_path):
    with pytest.raises(VidflowError, match="ý tưởng"):
        check_quick_job("script", qroot)
    with pytest.raises(VidflowError, match="model clip"):
        check_quick_job("clips", qroot)
    with pytest.raises(ValueError):
        check_quick_job("gen", qroot)
    with pytest.raises(ValueError):
        check_quick_job("render", qroot, {"resolution": "4k"})
    check_quick_job("voice", qroot)
    create_quick(tmp_path / "moi", preset="doodle-giai-ma")
    with pytest.raises(VidflowError, match="beats.json"):
        check_quick_job("voice", tmp_path / "moi")



class SleepRunner(JobRunner):
    def quick_command_for(self, kind, project_root, instruction="", options=None, provider=None):
        return [sys.executable, "-c", "import time; time.sleep(5)"]


def test_runner_quick_label_busy_and_stop(qroot):
    r = SleepRunner()
    job = r.start("flow", "vid", qroot, quick=True)
    assert job.to_dict(tail=0)["label"] == "Gen ảnh mốc"
    with pytest.raises(RuntimeError, match="Gen ảnh mốc"):
        r.start("voice", "vid", qroot, quick=True)
    assert r.stop() is True
    assert job.state == "stopped" and r.busy() is False
    assert job.to_dict(tail=0)["quota_exhausted"] is False
    assert r.stop() is False
    r.start("voice", "vid", qroot, quick=True)  # chạy được việc mới sau khi dừng
    assert r.current.to_dict(tail=0)["label"] == "Tạo giọng đọc (Gemini)"
    r.stop()


def test_provider_override_passed_and_validated(qroot, monkeypatch):
    import vidflow.quick.jobs as qj

    seen = {}

    def fake_claude_cmd(kind, root, preset, provider=None):
        seen[kind] = provider
        return ["claude", "-p", "task"]

    monkeypatch.setattr(qj, "claude_cmd", fake_claude_cmd)
    build_quick_cmd("flow", qroot, provider="gemini")
    build_quick_cmd("clips", qroot)
    build_quick_cmd("sheets", qroot, provider="aistudio")
    assert seen == {"flow": "gemini", "clips": None, "sheets": "aistudio"}
    for kind, prov in (("voice", "gemini"), ("ideas", "flow"), ("flow", "midjourney"), ("flow", "")):
        with pytest.raises(ValueError):
            build_quick_cmd(kind, qroot, provider=prov)
        with pytest.raises(ValueError):
            check_quick_job(kind, qroot, provider=prov)


class CmdRunner(JobRunner):
    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd
        self.seen = []

    def quick_command_for(self, kind, project_root, instruction="", options=None, provider=None):
        self.seen.append((kind, provider))
        return self.cmd


def test_start_gen_resolves_provider_and_clears_limits(qroot):
    ops.update_settings(qroot, video_provider="aistudio")
    ops.record_limit(qroot, "gemini", "image")
    ops.record_limit(qroot, "gemini", "video")
    ops.record_limit(qroot, "aistudio", "video")
    r = CmdRunner([sys.executable, "-c", "pass"])
    job = r.start("flow", "vid", qroot, quick=True, provider="gemini")
    job.proc.wait()
    assert job.provider == "gemini" and r.seen[-1] == ("flow", "gemini")
    assert [(x.provider, x.kind) for x in load_quick(qroot).limits] == [("gemini", "video"), ("aistudio", "video")]
    job = r.start("clips", "vid", qroot, quick=True)  # không ghi đè → theo cài đặt video
    job.proc.wait()
    assert job.provider == "aistudio" and r.seen[-1] == ("clips", "aistudio")
    assert [(x.provider, x.kind) for x in load_quick(qroot).limits] == [("gemini", "video")]
    job = r.start("voice", "vid", qroot, quick=True)  # không phải job gen → không chọn nguồn
    job.proc.wait()
    assert job.provider == "" and r.seen[-1] == ("voice", None)
    assert job.to_dict()["quota_exhausted"] is False


def test_start_rejects_bad_provider(qroot):
    r = CmdRunner([sys.executable, "-c", "pass"])
    for kind, prov in (("voice", "gemini"), ("flow", "midjourney")):
        with pytest.raises(ValueError):
            r.start(kind, "vid", qroot, quick=True, provider=prov)
    assert r.current is None


LIMIT = "from vidflow.quick import ops; ops.record_limit({root!r}, {prov!r}, {media!r})"


@pytest.mark.parametrize("kind,code,want", [
    ("flow", "import sys; sys.exit(3)", True),
    ("flow", LIMIT.format(root="{root}", prov="gemini", media="image"), True),
    ("clips", LIMIT.format(root="{root}", prov="gemini", media="video"), True),
    ("flow", LIMIT.format(root="{root}", prov="gemini", media="video"), False),  # khác loại media
    ("flow", LIMIT.format(root="{root}", prov="flow", media="image"), False),  # khác nguồn
    ("flow", "print('Báo cáo: hết lượt ở gemini, đã gen 12 ảnh')", False),  # không đọc chữ trong log
    ("flow", "print('xong')", False),
    ("flow", "import sys; sys.exit(1)", False),
])
def test_quota_exhausted_flag(qroot, kind, code, want):
    r = CmdRunner([sys.executable, "-c", code.replace("{root}", str(qroot))])
    job = r.start(kind, "vid", qroot, quick=True, provider="gemini")
    job.proc.wait()
    d = job.to_dict()
    assert d["quota_exhausted"] is want and d["provider"] == "gemini"
