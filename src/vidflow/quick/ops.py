"""Thao tác trên project nhanh — CLI, job Claude và UI cùng gọi (không ai sửa tay JSON/YAML)."""
from __future__ import annotations

import shutil
from pathlib import Path

from vidflow.errors import VidflowError
from vidflow.media import wav_duration
from vidflow.quick.model import (STAGES, Beat, Beats, Idea, QuickProject, Review, image_name, load_beats,
                                 load_quick, require_beats, save_beats, save_quick)
from vidflow.quick.preset import Preset, load_preset

IMAGE_EXTS = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png", ".webp": ".webp"}
PASSING = ("pass", "override")
VOICE_FILE = "audio/voice.wav"


def advance(root: Path, stage: str, q: QuickProject | None = None) -> QuickProject:
    """Chuyển stage tiến lên (không lùi)."""
    q = q or load_quick(root)
    if STAGES.index(stage) > STAGES.index(q.stage):
        q.stage = stage
        save_quick(root, q)
    return q


def set_ideas(root: Path, ideas: list[dict]) -> QuickProject:
    if not 1 <= len(ideas) <= 10:
        raise VidflowError(f"Cần 1–10 ý tưởng, nhận {len(ideas)}.")
    q = load_quick(root)
    try:
        q.ideas = [Idea.model_validate(i) for i in ideas]
    except Exception as e:
        raise VidflowError(f"Ý tưởng không hợp lệ: {e}") from e
    q.picked, q.stage = None, "ideas"
    save_quick(root, q)
    return q


def pick_idea(root: Path, n: int) -> QuickProject:
    q = load_quick(root)
    if not 1 <= n <= len(q.ideas):
        raise VidflowError(f"Chọn số 1–{len(q.ideas)} (hiện có {len(q.ideas)} ý tưởng).")
    q.picked, q.stage = n, "picked"
    q.title = q.ideas[n - 1].title
    save_quick(root, q)
    return q


def set_beat_texts(root: Path, items: list, *, aspect: str | None = None) -> Beats:
    """Thay toàn bộ beats bằng danh sách câu (chuỗi hoặc {"text": ...}); bỏ dòng trống."""
    texts = []
    for it in items:
        t = it.get("text", "") if isinstance(it, dict) else str(it)
        if t.strip():
            texts.append(t.strip())
    if not texts:
        raise VidflowError("Danh sách câu rỗng.")
    q = load_quick(root)
    aspect = aspect or load_preset(q.preset).aspect
    beats = Beats(aspect=aspect, beats=[Beat(n=i, text=t) for i, t in enumerate(texts, 1)])
    save_beats(root, beats)
    q.stage = "script"
    save_quick(root, q)
    return beats


def check_anchors(prompt: str, preset: Preset) -> None:
    p = prompt.strip()
    if not p.startswith(preset.style_anchor_start) or not p.endswith(preset.style_anchor_end):
        raise VidflowError("Prompt phải mở đầu bằng câu neo đầu và kết thúc bằng câu neo cuối của bộ kênh "
                           f"(nguyên văn): «{preset.style_anchor_start}» … «{preset.style_anchor_end}»")


def set_prompts(root: Path, items: list[dict]) -> Beats:
    """items: [{n, prompt, verdict, score, issues?}] — ghi prompt + kết quả tự kiểm duyệt."""
    q = load_quick(root)
    preset = load_preset(q.preset)
    beats = require_beats(root)
    for it in items:
        beat = beats.get(int(it["n"]))
        prompt = str(it.get("prompt", "")).strip()
        check_anchors(prompt, preset)
        verdict = it.get("verdict", "pass")
        if verdict not in ("pass", "fail"):
            raise VidflowError("verdict phải là pass hoặc fail")
        beat.prompt = prompt
        beat.review = Review(verdict=verdict, score=float(it.get("score", 0)), issues=list(it.get("issues") or []))
    save_beats(root, beats)
    if all(b.review and b.review.verdict in PASSING for b in beats.beats):
        advance(root, "prompted", q)
    return beats


def set_prompt(root: Path, n: int, prompt: str, *, verdict: str = "pass", score: float = 0,
               issues: list[str] | None = None) -> Beat:
    return set_prompts(root, [{"n": n, "prompt": prompt, "verdict": verdict, "score": score,
                               "issues": issues or []}]).get(n)


def set_image(root: Path, n: int, src: Path) -> Beat:
    root, src = Path(root), Path(src)
    if not src.is_file():
        raise VidflowError(f"Không thấy file ảnh {src}")
    ext = IMAGE_EXTS.get(src.suffix.lower())
    if not ext:
        raise VidflowError(f"Định dạng ảnh không hỗ trợ: {src.suffix} (dùng jpg/png/webp)")
    beats = require_beats(root)
    beat = beats.get(n)
    if beat.start is None:
        raise VidflowError("Mốc chưa có thời gian — chạy `vidflow quick voice` trước khi gắn ảnh.")
    rel = f"images/{image_name(n, beat.start)}{ext}"
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    if beat.image and beat.image != rel and beat.image.startswith("images/"):
        (root / beat.image).unlink(missing_ok=True)
    beat.image, beat.status = rel, "ok"
    save_beats(root, beats)
    if all(b.status == "ok" and b.image for b in beats.beats):
        advance(root, "imaged")
    return beat


def mark_redo(root: Path, ns: list[int]) -> Beats:
    beats = require_beats(root)
    targets = [beats.get(n) for n in ns]  # báo lỗi trước khi ghi nếu có số sai
    for b in targets:
        b.status = "redo"
    save_beats(root, beats)
    return beats


def beat_file(beat: Beat) -> str | None:
    return None if beat.start is None else f"images/{image_name(beat.n, beat.start)}.jpg"


def list_beats(root: Path, *, todo: bool = False) -> dict:
    """todo=True: chỉ mốc cần gen ảnh (pending/redo, prompt đã đạt kiểm duyệt, đã có thời gian)."""
    beats = require_beats(root)
    rows = []
    for b in beats.beats:
        if todo and not (b.status in ("pending", "redo") and b.prompt and b.review
                         and b.review.verdict in PASSING and b.start is not None):
            continue
        rows.append({**b.model_dump(), "file": beat_file(b)})
    return {"aspect": beats.aspect, "beats": rows}


def status_summary(root: Path) -> dict:
    from vidflow.quick.voice import voiced_count

    root = Path(root)
    q = load_quick(root)
    beats = load_beats(root)
    bl = beats.beats if beats else []
    voice = root / VOICE_FILE
    try:
        voice_s = round(wav_duration(voice), 3) if voice.is_file() else None
    except Exception:
        voice_s = None
    idea = q.picked_idea()
    return {
        "stage": q.stage, "title": q.title, "preset": q.preset,
        "ideas": len(q.ideas), "picked": q.picked, "picked_title": idea.title if idea else None,
        "beats": {
            "total": len(bl),
            "voiced": voiced_count(root, bl),
            "timed": beats.timed if beats else False,
            "prompted": sum(1 for b in bl if b.review and b.review.verdict in PASSING),
            "prompt_fail": sum(1 for b in bl if b.review and b.review.verdict == "fail"),
            "imaged": sum(1 for b in bl if b.image and b.status == "ok"),
            "redo": sum(1 for b in bl if b.status == "redo"),
            "pending": sum(1 for b in bl if b.status == "pending"),
        },
        "voice_s": voice_s,
    }


def format_status(s: dict) -> str:
    b = s["beats"]
    lines = [f"{s['title'] or '(chưa có tựa)'} · bộ kênh {s['preset']} · bước: {s['stage']}",
             f"Ý tưởng: {s['ideas']}" + (f" · đã chọn #{s['picked']}: {s['picked_title']}" if s["picked"] else ""),
             f"{b['total']} mốc · đã đọc {b['voiced']} · prompt đạt {b['prompted']} (trượt {b['prompt_fail']}) · "
             f"có ảnh {b['imaged']} · gen lại {b['redo']}"]
    if s["voice_s"] is not None:
        m, sec = divmod(s["voice_s"], 60)
        lines.append(f"Giọng đọc: {int(m)}:{sec:05.2f}")
    return "\n".join(lines)
