"""Adapter thật tới Gemini API. Không unit test; xác minh bằng spike (Task 1) và E2E (Task 11)."""
from __future__ import annotations

import base64
import os

from vidflow.errors import ConfigError


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
