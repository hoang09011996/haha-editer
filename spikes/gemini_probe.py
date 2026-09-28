"""Xác minh Gemini: liệt kê model, TTS tiếng Việt, (tùy chọn) Veo lite 4s."""
import base64
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
client = genai.Client()

print("== Models")
for m in client.models.list():
    name = m.name or ""
    if any(k in name for k in ("veo", "tts", "image")):
        print(name)

print("== TTS")
print("has interactions API:", hasattr(client, "interactions"))
it = client.interactions.create(
    model="gemini-3.8-flash-tts",
    input=[{"type": "user_input", "content": [{"type": "text", "text": "Mỗi sáng, An bắt đầu ngày mới bằng một tách cà phê."}]}],
    response_format={"type": "audio"},
    generation_config={"speech_config": [{"voice": "Kore"}]},
)
audio = base64.b64decode(it.output_audio.data)
print("audio header:", audio[:4])
(OUT / "tts.wav").write_bytes(audio)

if "--veo" in sys.argv:
    print("== Veo lite 4s (TỐN PHÍ)")
    op = client.models.generate_videos(
        model="veo-3.1-lite-generate-preview",
        prompt="A cup of coffee on a wooden table, morning light, slow push-in.",
        config=types.GenerateVideosConfig(aspect_ratio="9:16", duration_seconds=4, resolution="720p"),
    )
    print("operation name:", op.name)
    while not op.done:
        time.sleep(10)
        op = client.operations.get(types.GenerateVideosOperation(name=op.name))
    vids = op.response.generated_videos or []
    print("videos:", len(vids), "filtered:", getattr(op.response, "rai_media_filtered_reasons", None))
    client.files.download(file=vids[0].video)
    vids[0].video.save(str(OUT / "veo.mp4"))
    print("saved", OUT / "veo.mp4")
