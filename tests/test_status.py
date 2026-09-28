from vidflow.inputs import tts_hash, video_hash
from vidflow.state import PendingOp, Take, TtsResult
from vidflow.status import scene_rows


def test_rows(project, cfg):
    script = project.load_script()
    state = project.load_state()
    s1 = state.scene("s01")
    s1.tts = TtsResult(file="audio/s01.wav", duration_s=2, input_hash=tts_hash(script, script.scene("s01"), cfg))
    s1.takes = [Take(file="clips/s01_t1.mp4", input_hash="old", cost_usd=4, created_at="t")]
    s1.picked = 0
    s1.errors = ["T bị lọc"]
    state.scene("s02").pending = [PendingOp(name="op", input_hash="h", seconds=4, submitted_at="t")]
    state.scene("s03").tts = TtsResult(file="audio/s03.wav", duration_s=2, input_hash="stale")
    rows = {r["id"]: r for r in scene_rows(project, script, state, cfg)}
    assert rows["s01"] == {"id": "s01", "status": "approved", "tts": "ok", "takes": "1", "picked": "t1",
                           "clip": "cũ", "pending": "0", "error": "T bị lọc"}
    assert rows["s02"]["tts"] == "-"
    assert rows["s02"]["clip"] == "thiếu"
    assert rows["s02"]["pending"] == "1"
    assert rows["s03"]["tts"] == "cũ"
    h = video_hash(project, script, script.scene("s01"), cfg)
    s1.takes[0] = s1.takes[0].model_copy(update={"input_hash": h})
    assert scene_rows(project, script, state, cfg)[0]["clip"] == "ok"
