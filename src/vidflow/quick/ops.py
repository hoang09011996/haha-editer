"""Thao tác trên project nhanh — CLI, job Claude và UI cùng gọi (không ai sửa tay JSON/YAML)."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from vidflow.errors import VidflowError
from vidflow.media import wav_duration
from vidflow.quick.chars import CharRef, check_known, lookup, parse_refs
from vidflow.quick.model import (IMAGE_EXTS, PROVIDERS, STAGES, Beat, Beats, Idea, LimitHit, QuickProject, Review, image_name,
                                 load_beats, load_quick, require_beats, save_beats, save_quick)
from vidflow.quick.preset import Preset, load_preset

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


def _check_cont(beat: Beat, cont: bool, q: QuickProject) -> bool:
    if cont and beat.n == 1:
        raise VidflowError("Mốc 1 không nối cảnh được (không có mốc trước).")
    if cont and not q.allow_cont:
        raise VidflowError("Video này tắt nối cảnh (allow_cont=false) — bật bằng `vidflow quick settings --allow-cont`.")
    return cont


def set_prompts(root: Path, items: list[dict]) -> Beats:
    """items: [{n, prompt, verdict, score, issues?, cont?}] — ghi prompt + kết quả tự kiểm duyệt.
    `refs` tự tách từ @TÊN trong prompt; tên chưa khai báo → từ chối cả lô."""
    q = load_quick(root)
    preset = load_preset(q.preset)
    beats = require_beats(root)
    known = lookup(root, q, preset)
    for it in items:
        beat = beats.get(int(it["n"]))
        prompt = str(it.get("prompt", "")).strip()
        check_anchors(prompt, preset)
        refs = parse_refs(prompt)
        check_known(refs, known)
        verdict = it.get("verdict", "pass")
        if verdict not in ("pass", "fail"):
            raise VidflowError("verdict phải là pass hoặc fail")
        if "cont" in it:
            beat.cont = _check_cont(beat, bool(it["cont"]), q)
        if prompt != beat.prompt:
            beat.error = ""
        beat.prompt, beat.refs = prompt, refs
        beat.review = Review(verdict=verdict, score=float(it.get("score", 0)), issues=list(it.get("issues") or []))
    save_beats(root, beats)
    if all(b.review and b.review.verdict in PASSING for b in beats.beats):
        advance(root, "prompted", q)
    return beats


def set_prompt(root: Path, n: int, prompt: str, *, verdict: str = "pass", score: float = 0,
               issues: list[str] | None = None, cont: bool | None = None) -> Beat:
    item = {"n": n, "prompt": prompt, "verdict": verdict, "score": score, "issues": issues or []}
    if cont is not None:
        item["cont"] = cont
    return set_prompts(root, [item]).get(n)


def edit_prompt(root: Path, n: int, prompt: str, *, clip: bool = False) -> Beat:
    """Người dùng sửa tay prompt ảnh/clip: lưu và xóa kết quả kiểm duyệt (phải kiểm duyệt lại mới gen)."""
    q = load_quick(root)
    preset = load_preset(q.preset)
    beats = require_beats(root)
    beat = beats.get(n)
    prompt = prompt.strip()
    if not prompt:
        raise VidflowError("Prompt rỗng.")
    refs = parse_refs(prompt)
    check_known(refs, lookup(root, q, preset))
    if clip:
        beat.clip.prompt, beat.clip.review = prompt, None
    else:
        check_anchors(prompt, preset)
        beat.prompt, beat.refs, beat.review = prompt, refs, None
    save_beats(root, beats)
    return beat


def set_review(root: Path, n: int, verdict: str, *, score: float = 0, issues: list[str] | None = None,
               clip: bool = False) -> Beat:
    """Ghi kết quả kiểm duyệt một mốc (prompt-reviewer, hoặc người dùng duyệt tay = override)."""
    if verdict not in ("pass", "fail", "override"):
        raise VidflowError("verdict phải là pass, fail hoặc override")
    beats = require_beats(root)
    beat = beats.get(n)
    if not (beat.clip.prompt if clip else beat.prompt):
        raise VidflowError(f"Mốc {n} chưa có prompt {'clip' if clip else 'ảnh'} để kiểm duyệt.")
    review = Review(verdict=verdict, score=float(score), issues=list(issues or []))
    if clip:
        beat.clip.review = review
    else:
        beat.review = review
    save_beats(root, beats)
    if not clip and all(b.review and b.review.verdict in PASSING for b in beats.beats):
        advance(root, "prompted")
    return beat


def record_fail(root: Path, n: int, reason: str, *, clip: bool = False) -> Beat:
    """Flow từ chối/lỗi: ghi lý do. Mốc lỗi bị loại khỏi danh sách việc tới khi `clear_errors`."""
    reason = reason.strip()
    if not reason:
        raise VidflowError("Cần ghi lý do lỗi (nguyên văn thông báo của Flow).")
    beats = require_beats(root)
    beat = beats.get(n)
    if clip:
        beat.clip.status, beat.clip.error = "error", reason
    else:
        beat.error = reason
    save_beats(root, beats)
    return beat


def clear_errors(root: Path, ns: list[int] | None = None, *, clip: bool = False) -> int:
    """Đưa mốc lỗi trở lại danh sách việc. ns rỗng/None = mọi mốc lỗi. Trả số mốc đã xóa lỗi."""
    beats = require_beats(root)
    targets = [beats.get(n) for n in ns] if ns else beats.beats
    count = 0
    for b in targets:
        if clip and b.clip.status == "error":
            b.clip.status, b.clip.error = "redo", ""
            count += 1
        elif not clip and b.error:
            b.error = ""
            count += 1
    save_beats(root, beats)
    return count


def check_provider(name: str) -> str:
    if name not in PROVIDERS:
        raise VidflowError(f"Nguồn gen không hợp lệ: {name!r} (chọn: {', '.join(PROVIDERS)}).")
    return name


def record_limit(root: Path, provider: str, kind: str, reason: str = "") -> QuickProject:
    """Agent báo nguồn hết lượt / đòi trả phí. Job đang chạy sẽ kết thúc mã 3."""
    check_provider(provider)
    if kind not in ("image", "video"):
        raise VidflowError("kind phải là image hoặc video.")
    q = load_quick(root)
    q.limits.append(LimitHit(provider=provider, kind=kind, reason=reason.strip(),
                             at=datetime.now().isoformat(timespec="seconds")))
    save_quick(root, q)
    return q


def clear_limits(root: Path, provider: str, kind: str | None = None) -> int:
    """Xóa các mốc hết lượt của một nguồn (khi bắt đầu job mới với nguồn đó); `kind` (image|video) chỉ xóa loại đó.
    Trả số mục đã xóa."""
    check_provider(provider)
    if kind is not None and kind not in ("image", "video"):
        raise VidflowError("kind phải là image hoặc video.")
    q = load_quick(root)
    before = len(q.limits)
    q.limits = [x for x in q.limits if not (x.provider == provider and (kind is None or x.kind == kind))]
    if len(q.limits) != before:
        save_quick(root, q)
    return before - len(q.limits)


def set_image(root: Path, n: int, src: Path, *, provider: str = "") -> Beat:
    if provider:
        check_provider(provider)
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
    beat.image, beat.status, beat.error, beat.provider = rel, "ok", "", provider
    if beat.clip.status == "ok":
        beat.clip.status = "redo"  # clip cũ dựng từ ảnh cũ
    save_beats(root, beats)
    if all(b.status == "ok" and b.image for b in beats.beats):
        advance(root, "imaged")
    return beat


def mark_redo(root: Path, ns: list[int], *, clip: bool = False) -> Beats:
    beats = require_beats(root)
    targets = [beats.get(n) for n in ns]  # báo lỗi trước khi ghi nếu có số sai
    for b in targets:
        if clip:
            if not b.clip.enabled:
                raise VidflowError(f"Mốc {b.n} chưa bật clip.")
            b.clip.status = "redo"
        else:
            b.status = "redo"
    save_beats(root, beats)
    return beats


def update_settings(root: Path, *, image_model: str | None = None, video_model: str | None = None,
                    resolution: str | None = None, max_clips: int | None = None, allow_cont: bool | None = None,
                    channel_chars: list[str] | None = None, image_provider: str | None = None,
                    video_provider: str | None = None) -> QuickProject:
    """Cài đặt Flow + giới hạn clip + nối cảnh + nhân vật bộ kênh dùng trong video."""
    q = load_quick(root)
    if max_clips is not None:
        if max_clips < 0:
            raise VidflowError("max_clips phải ≥ 0.")
        beats = load_beats(root)
        on = sum(1 for b in beats.beats if b.clip.enabled) if beats else 0
        if max_clips < on:
            raise VidflowError(f"Đang bật {on} clip — tắt bớt trước khi giảm tối đa xuống {max_clips}.")
        q.max_clips = max_clips
    if resolution is not None:
        if resolution not in ("720p", "1080p"):
            raise VidflowError("Độ phân giải chỉ 720p hoặc 1080p.")
        q.flow.resolution = resolution
    if video_model is not None:
        q.flow.video_model = video_model.strip()
    if image_model is not None:
        q.flow.image_model = image_model.strip()
    if allow_cont is not None:
        q.allow_cont = allow_cont
    if channel_chars is not None:
        have = {c.id for c in load_preset(q.preset).characters}
        unknown = [c for c in channel_chars if c not in have]
        if unknown:
            raise VidflowError(f"Bộ kênh không có: {', '.join('@' + u for u in unknown)}")
        dropped = {c for c in have if q.channel_chars is None or c in q.channel_chars} - set(channel_chars)
        dropped -= {c.id for c in q.characters}
        beats = load_beats(root)
        used = {r for b in (beats.beats if beats else []) for r in [*b.refs, *parse_refs(b.clip.prompt)]}
        stranded = sorted(dropped & used)
        if stranded:
            raise VidflowError(f"Không bỏ được nhân vật bộ kênh đang dùng trong prompt: "
                               f"{', '.join('@' + i for i in stranded)}")
        q.channel_chars = list(channel_chars)
    if image_provider is not None:
        q.flow.image_provider = check_provider(image_provider)
    if video_provider is not None:
        q.flow.video_provider = check_provider(video_provider)
    save_quick(root, q)
    return q


def beat_file(beat: Beat) -> str | None:
    return None if beat.start is None else f"images/{image_name(beat.n, beat.start)}.jpg"


def image_block(beat: Beat, prev: Beat | None, known: dict[str, CharRef]) -> str | None:
    """Lý do mốc chưa gen ảnh được (None = được): thiếu ảnh nhân vật, hoặc nối cảnh mà mốc trước chưa có ảnh."""
    missing = [r for r in beat.refs if r not in known or known[r].image is None]
    if missing:
        return "thiếu ảnh " + ", ".join("@" + r for r in missing)
    if beat.cont and not (prev and prev.image and prev.status == "ok"):
        return f"chờ ảnh mốc {prev.n if prev else beat.n - 1}"
    return None


def _wants_image(b: Beat) -> bool:
    return (b.status in ("pending", "redo") and bool(b.prompt) and b.review is not None
            and b.review.verdict in PASSING and b.start is not None and not b.error)


def list_beats(root: Path, *, todo: bool = False) -> dict:
    """todo=True: chỉ mốc cần gen ảnh và gen được ngay; mốc bị chặn vào `blocked`; kèm `attach` (ảnh đính khi gen)."""
    root = Path(root)
    beats = require_beats(root)
    known = lookup(root)
    rows, blocked = [], []
    prev: Beat | None = None
    for b in beats.beats:
        reason = None if b.status == "ok" else image_block(b, prev, known)
        before, prev = prev, b
        if todo:
            if not _wants_image(b):
                continue
            if reason:
                blocked.append({"n": b.n, "reason": reason})
                continue
        row = {**b.model_dump(), "file": beat_file(b), "blocked": reason}
        if todo:
            row["attach"] = ([str(known[r].image.resolve()) for r in b.refs]
                             + ([str((root / before.image).resolve())] if b.cont else []))
        rows.append(row)
    out = {"aspect": beats.aspect, "beats": rows}
    if todo:
        out["blocked"] = blocked
    return out


def status_summary(root: Path) -> dict:
    from vidflow.quick.voice import voiced_count

    root = Path(root)
    q = load_quick(root)
    beats = load_beats(root)
    bl = beats.beats if beats else []
    known = lookup(root, q) if bl else {}
    blocked, prev = 0, None
    for b in bl:
        if _wants_image(b) and image_block(b, prev, known):
            blocked += 1
        prev = b
    referenced = {r for b in bl for r in b.refs}
    chars_missing = sorted(r for r in referenced if r not in known or known[r].image is None)
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
        "blocked": blocked,
        "errors": sum(1 for b in bl if b.error),
        "chars_missing": chars_missing,
        "allow_cont": q.allow_cont,
        "providers": {"image": q.flow.image_provider, "video": q.flow.video_provider},
        "limits": [x.model_dump() for x in q.limits],
        "clips": {"max": q.max_clips, "enabled": sum(1 for b in bl if b.clip.enabled),
                  "ok": sum(1 for b in bl if b.clip.status == "ok"),
                  "error": sum(1 for b in bl if b.clip.status == "error")},
    }


def format_status(s: dict) -> str:
    b = s["beats"]
    lines = [f"{s['title'] or '(chưa có tựa)'} · bộ kênh {s['preset']} · bước: {s['stage']}",
             f"Ý tưởng: {s['ideas']}" + (f" · đã chọn #{s['picked']}: {s['picked_title']}" if s["picked"] else ""),
             f"{b['total']} mốc · đã đọc {b['voiced']} · prompt đạt {b['prompted']} (trượt {b['prompt_fail']}) · "
             f"có ảnh {b['imaged']} · gen lại {b['redo']}"]
    if s["blocked"] or s["errors"]:
        miss = f" · thiếu ảnh nhân vật: {', '.join('@' + c for c in s['chars_missing'])}" if s["chars_missing"] else ""
        lines.append(f"Bị chặn: {s['blocked']} mốc · lỗi Flow: {s['errors']} mốc{miss}")
    c = s["clips"]
    if c["enabled"]:
        lines.append(f"Clip: {c['ok']}/{c['enabled']} xong (tối đa {c['max']}) · lỗi {c['error']}")
    for x in s.get("limits", []):
        what = "ảnh" if x["kind"] == "image" else "clip"
        lines.append(f"Hết lượt {what} ở {x['provider']} ({x['at']})" + (f": {x['reason']}" if x["reason"] else ""))
    if s["voice_s"] is not None:
        m, sec = divmod(s["voice_s"], 60)
        lines.append(f"Giọng đọc: {int(m)}:{sec:05.2f}")
    return "\n".join(lines)
