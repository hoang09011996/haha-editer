from vidflow.preview import render_preview
from vidflow.state import Take, TtsResult


def test_preview_lists_scenes_takes_and_escapes(project):
    script = project.load_script()
    script.scenes[0].narration = "<b>An</b> & cà phê"
    state = project.load_state()
    st = state.scene("s01")
    st.tts = TtsResult(file="audio/s01.wav", duration_s=2.0, input_hash="h")
    st.takes = [Take(file="clips/s01_t1.mp4", input_hash="h", cost_usd=4, created_at="t"),
                Take(file="clips/s01_t2.mp4", input_hash="h", cost_usd=4, created_at="t")]
    st.picked = 1
    st.errors = ["T lỗi cũ"]
    out = render_preview(project, script, state)
    html = out.read_text(encoding="utf-8")
    assert out == project.root / "preview.html"
    assert "&lt;b&gt;An&lt;/b&gt; &amp; cà phê" in html
    assert 'src="clips/s01_t1.mp4"' in html and 'src="clips/s01_t2.mp4"' in html
    assert "take 2 (đang chọn)" in html
    assert 'src="audio/s01.wav"' in html
    assert "T lỗi cũ" in html
    assert "s03" in html
