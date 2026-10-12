"""Adapter thật tới Gemini API. Không unit test; xác minh bằng spike (Task 1) và E2E (Task 11)."""
from __future__ import annotations

import base64
import os
from pathlib import Path

from vidflow.errors import ConfigError, VidflowError
from vidflow.retry import call_with_deadline
from vidflow.video import PollResult


HTTP_TIMEOUT_MS = 90_000  # mỗi request Gemini tối đa 90 giây, quá thì báo lỗi để with_retry thử lại


def gemini_client():
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise ConfigError("Chưa có GEMINI_API_KEY trong biến môi trường.")
    from google import genai
    from google.genai import types

    # Không có thời gian chờ thì một kết nối bị máy chủ đóng ngang (CLOSE_WAIT) làm job treo mãi.
    return genai.Client(http_options=types.HttpOptions(timeout=HTTP_TIMEOUT_MS))


TTS_MAX_S = 300  # trần hạn chót: hết lượt thì Gemini treo, không để người dùng chờ quá 5 phút mỗi lần


def tts_deadline(text: str) -> float:
    """Hạn chót một lượt TTS: 90 giây, đoạn dài (đọc theo đoạn/cả bài) thêm thời gian theo số ký tự, tối đa 5 phút."""
    return min(TTS_MAX_S, max(HTTP_TIMEOUT_MS / 1000, 0.15 * len(text)))


class GeminiSpeechClient:
    def __init__(self, client=None):
        self._c = client or gemini_client()

    def synthesize(self, *, text: str, voice: str, style: str, model: str) -> bytes:
        content: dict = {"type": "text", "text": text}
        if style:
            content["annotations"] = [{"type": "speech_metadata", "style": style}]
        # SDK bỏ qua timeout ở chỗ này (đã thử) — chặn cứng bằng luồng có hạn chót.
        it = call_with_deadline(lambda: self._c.interactions.create(
            model=model,
            input=[{"type": "user_input", "content": [content]}],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice}]},
        ), tts_deadline(text))
        return base64.b64decode(it.output_audio.data)


class GeminiVideoClient:
    def __init__(self, client=None):
        self._c = client or gemini_client()

    def submit(self, *, prompt, aspect, duration, resolution, model, ref_images: list[Path]) -> str:
        from google.genai import types

        refs = [types.VideoGenerationReferenceImage(image=types.Image.from_file(location=str(p)),
                                                    reference_type="asset") for p in ref_images]
        op = self._c.models.generate_videos(
            model=model,
            prompt=prompt,
            config=types.GenerateVideosConfig(aspect_ratio=aspect, duration_seconds=duration,
                                              resolution=resolution, reference_images=refs or None),
        )
        return op.name

    def poll(self, op_name: str) -> PollResult:
        from google.genai import types

        op = self._c.operations.get(types.GenerateVideosOperation(name=op_name))
        if not op.done:
            return PollResult(done=False)
        if op.error:
            return PollResult(done=True, error=f"Veo lỗi: {op.error}")
        vids = (op.response.generated_videos if op.response else None) or []
        if not vids:
            reasons = getattr(op.response, "rai_media_filtered_reasons", None)
            return PollResult(done=True, error=f"Veo không trả video (có thể bị lọc an toàn): {reasons}")
        return PollResult(done=True, video=vids[0].video)

    def download(self, video, dest: Path) -> None:
        self._c.files.download(file=video)
        video.save(str(dest))


class GeminiImageClient:
    def __init__(self, client=None):
        self._c = client or gemini_client()

    def generate(self, *, prompt: str, model: str) -> bytes:
        resp = self._c.models.generate_content(model=model, contents=[prompt])
        for part in resp.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
        raise VidflowError("Model ảnh không trả về ảnh; thử lại hoặc đổi image_model.")
