import pytest

from vidflow.errors import BudgetError, ScriptError, VidflowError
from vidflow.video import PollResult, pick_take, run_gen


class FakeVeo:
    """Mỗi job cần `polls_needed` lần poll; scene nào có trong `filtered` trả lỗi."""

    def __init__(self, polls_needed=2, filtered=()):
        self.polls_needed = polls_needed
        self.filtered = set(filtered)
        self.submitted = []
        self.poll_count = {}

    def submit(self, *, prompt, aspect, duration, resolution, model, ref_images):
        name = f"op{len(self.submitted) + 1}"
        self.submitted.append({"name": name, "prompt": prompt, "duration": duration, "aspect": aspect})
        return name

    def _scene_of(self, op_name):
        prompt = next(s["prompt"] for s in self.submitted if s["name"] == op_name)
        return "s01" if "Close-up" in prompt else "s02"

    def poll(self, op_name):
        self.poll_count[op_name] = self.poll_count.get(op_name, 0) + 1
        if self.poll_count[op_name] < self.polls_needed:
            return PollResult(done=False)
        if self._scene_of(op_name) in self.filtered:
            return PollResult(done=True, error="Veo không trả video (lọc an toàn)")
        return PollResult(done=True, video=op_name)

    def download(self, video, dest):
        dest.write_bytes(f"video {video}".encode())


def run(project, cfg, fake, **kw):
    return run_gen(project, cfg, fake, poll_interval=0, sleep=lambda s: None, now=lambda: "T", **kw)


def test_generates_all_approved(project, cfg):
    fake = FakeVeo()
    rep = run(project, cfg, fake)
    assert rep.created == ["clips/s01_t1.mp4", "clips/s02_t1.mp4"]
    assert rep.failed == {}
    assert [s["duration"] for s in fake.submitted] == [8, 4]
    st = project.load_state()
    assert st.spent_usd == 6.0
    assert st.scenes["s01"].picked == 0
    assert st.scenes["s01"].pending == []
    assert (project.root / "clips/s01_t1.mp4").read_bytes() == b"video op1"


def test_second_run_is_noop(project, cfg):
    run(project, cfg, FakeVeo())
    fake = FakeVeo()
    rep = run(project, cfg, fake)
    assert fake.submitted == [] and rep.created == []


def test_resume_pending_without_resubmit(project, cfg):
    class Crash(Exception):
        pass

    class CrashingVeo(FakeVeo):
        def poll(self, op_name):
            raise Crash()

    with pytest.raises(Crash):
        run(project, cfg, CrashingVeo())
    st = project.load_state()
    assert [p.name for p in st.scenes["s01"].pending] == ["op1"]
    fake = FakeVeo(polls_needed=1)
    fake.submitted = [{"name": "op1", "prompt": "Close-up", "duration": 8, "aspect": "9:16"},
                      {"name": "op2", "prompt": "Wide", "duration": 4, "aspect": "9:16"}]
    rep = run(project, cfg, fake)
    assert len(fake.submitted) == 2  # không submit thêm
    assert sorted(rep.created) == ["clips/s01_t1.mp4", "clips/s02_t1.mp4"]
    assert project.load_state().spent_usd == 6.0


def test_filtered_scene_records_error_and_others_continue(project, cfg):
    rep = run(project, cfg, FakeVeo(filtered={"s01"}))
    assert rep.created == ["clips/s02_t1.mp4"]
    assert "lọc an toàn" in rep.failed["s01"]
    st = project.load_state()
    assert st.scenes["s01"].takes == []
    assert "lọc an toàn" in st.scenes["s01"].errors[-1]
    assert st.spent_usd == 2.0


def test_budget_blocks_before_submit(project, cfg):
    text = project.script_path.read_text(encoding="utf-8").replace("budget_usd: 10", "budget_usd: 5")
    project.script_path.write_text(text, encoding="utf-8")
    fake = FakeVeo()
    with pytest.raises(BudgetError):
        run(project, cfg, fake)
    assert fake.submitted == []


def test_regen_after_prompt_change_moves_pick(project, cfg):
    run(project, cfg, FakeVeo(), scene_ids=["s01"])
    text = project.script_path.read_text(encoding="utf-8").replace("sipping coffee", "reading a book")
    project.script_path.write_text(text, encoding="utf-8")
    fake = FakeVeo()
    rep = run(project, cfg, fake, scene_ids=["s01"])
    assert rep.created == ["clips/s01_t2.mp4"]
    assert project.load_state().scenes["s01"].picked == 1


def test_timeout_keeps_pending(project, cfg):
    ticks = iter(range(0, 10_000, 100))
    with pytest.raises(VidflowError, match="Hết thời gian"):
        run_gen(project, cfg, FakeVeo(polls_needed=99), poll_interval=0, sleep=lambda s: None,
                now=lambda: "T", timeout_s=250, clock=lambda: next(ticks))
    assert project.load_state().scenes["s01"].pending


def test_pick_take(project, cfg):
    run(project, cfg, FakeVeo(), scene_ids=["s01"], takes=2)
    assert pick_take(project, "s01", 2) == "clips/s01_t2.mp4"
    assert project.load_state().scenes["s01"].picked == 1
    with pytest.raises(ScriptError, match="1..2"):
        pick_take(project, "s01", 3)
