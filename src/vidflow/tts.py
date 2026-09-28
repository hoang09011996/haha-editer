from __future__ import annotations

import time
from typing import Callable, Protocol

from vidflow.config import Config
from vidflow.inputs import tts_hash
from vidflow.media import ensure_wav, floor_ms, wav_duration
from vidflow.project import Project
from vidflow.retry import with_retry
from vidflow.state import TtsResult


class SpeechClient(Protocol):
    def synthesize(self, *, text: str, voice: str, style: str, model: str) -> bytes: ...


def run_tts(project: Project, cfg: Config, client: SpeechClient, *, scene_ids: list[str] | None = None,
            force: bool = False, sleep: Callable[[float], None] = time.sleep) -> list[str]:
    script, state = project.load_script(), project.load_state()
    selected = script.scenes if not scene_ids else [script.scene(i) for i in scene_ids]
    done: list[str] = []
    for scene in selected:
        if not scene.narration.strip():
            continue
        h = tts_hash(script, scene, cfg)
        st = state.scene(scene.id)
        if not force and st.tts and st.tts.input_hash == h and project.path(st.tts.file).is_file():
            continue
        data = with_retry(lambda: client.synthesize(text=scene.narration, voice=script.voice.name,
                                                    style=script.voice.style, model=cfg.tts_model), sleep=sleep)
        out = project.audio_dir / f"{scene.id}.wav"
        out.write_bytes(ensure_wav(data))
        st.tts = TtsResult(file=project.rel(out), duration_s=floor_ms(wav_duration(out)), input_hash=h)
        project.save_state(state)
        done.append(scene.id)
    return done
