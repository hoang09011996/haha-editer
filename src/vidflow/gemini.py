"""Adapter thật tới Gemini API. Không unit test; xác minh bằng spike (Task 1) và E2E (Task 11)."""
from __future__ import annotations

import base64
import os
from pathlib import Path

from vidflow.errors import ConfigError
from vidflow.video import PollResult


def gemini_client():
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise ConfigError("Chưa có GEMINI_API_KEY trong biến môi trường.")
    from google import genai

    return genai.Client()


class GeminiSpeechClient:
    def __init__(self, client=None):
        self._c = client or gemini_client()

    def synthesize(self, *, text: str, voice: str, style: str, model: str) -> bytes:
        content: dict = {"type": "text", "text": text}
        if style:
            content["annotations"] = [{"type": "speech_metadata", "style": style}]
        it = self._c.interactions.create(
            model=model,
            input=[{"type": "user_input", "content": [content]}],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice}]},
        )
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
