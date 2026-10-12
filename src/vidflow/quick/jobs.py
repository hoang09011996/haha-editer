"""Job Claude (`claude -p`) cho quy trình nhanh: ideas | script | prompts | sheets | flow | clips."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import IO

from vidflow.errors import VidflowError
from vidflow.quick.model import LimitHit, load_quick
from vidflow.quick.preset import REPO, Preset, brief_path

AGENTS = REPO / ".claude" / "agents"
GUIDES = REPO / ".claude" / "guides"
QUICK_KINDS = ("ideas", "script", "prompts", "sheets", "flow", "clips")
CHROME_KINDS = ("sheets", "flow", "clips")
PROVIDER_LABELS = {
    "flow": "Google Flow",
    "gemini": "Gemini (gemini.google.com)",
    "aistudio": "Google AI Studio (aistudio.google.com)",
}
GEN_KINDS = ("sheets", "flow", "clips")
BATCH = 20
LABELS = {
    "ideas": "Claude đề xuất 5 ý tưởng",
    "script": "Claude viết kịch bản + tách mốc + đề xuất nhân vật",
    "prompts": "Claude viết prompt ảnh + clip từng mốc",
    "sheets": "Gen character sheet",
    "flow": "Gen ảnh mốc",
    "clips": "Gen clip động",
}
CLI = "uv run vidflow quick"


def _common(root: Path, preset: Preset) -> str:
    brief = brief_path(preset)
    return (f"Thư mục làm việc: {REPO}. Project nhanh: {root} (quick.yaml, beats.json). "
            f"Bộ kênh: {preset.id} — brief gốc: {brief} (đọc TOÀN BỘ, tuân thủ nội dung/giọng/phong cách; "
            "BỎ QUA các chỉ dẫn tương tác trong brief như chờ người dùng trả lời, xuất code block, tạo file tải về). "
            f"Xem trạng thái: `{CLI} status -p {root}`. KHÔNG sửa tay quick.yaml, beats.json — mọi ghi đều qua CLI "
            f"`{CLI} ...`; file JSON tạm đặt trong {root}/tmp/. Người dùng chỉ dùng gói Google AI qua phiên đăng nhập "
            "(không API trả phí): KHÔNG chạy `vidflow gen`, `vidflow estimate`, `vidflow refimg`. Báo cáo bằng tiếng Việt, ngắn gọn.")


def provider_for(kind: str, q) -> str:
    """Nguồn mặc định cho job gen theo cài đặt video (q: QuickProject)."""
    return q.flow.video_provider if kind == "clips" else q.flow.image_provider


def media_kind(kind: str) -> str:
    """Loại media của job gen: clips → video, sheets/flow → image."""
    return "video" if kind == "clips" else "image"


def resolve_provider(kind: str, project_root: Path, provider: str | None = None) -> str:
    """Nguồn cho job: `provider` nếu có, không thì theo cài đặt project (không đọc được → flow)."""
    if provider is not None or kind not in GEN_KINDS:
        return provider or "flow"
    try:
        return provider_for(kind, load_quick(project_root))
    except (VidflowError, OSError):
        return "flow"


def begin_gen(root: Path, kind: str, provider: str | None = None) -> str:
    """Bắt đầu job gen: chọn nguồn (kiểm tra `provider` nếu truyền, không thì theo cài đặt) và xóa các mốc hết lượt
    cũ của đúng nguồn + loại media đó. Trả về nguồn."""
    from vidflow.quick import ops

    if kind not in GEN_KINDS:
        raise VidflowError(f"'{kind}' không phải job gen ({', '.join(GEN_KINDS)}).")
    prov = ops.check_provider(provider) if provider else provider_for(kind, load_quick(root))
    ops.clear_limits(root, prov, kind=media_kind(kind))
    return prov


def limit_hit(root: Path, provider: str, kind: str) -> LimitHit | None:
    """Mốc hết lượt mới nhất của nguồn `provider` cho loại media của job `kind` (None nếu không có)."""
    want = media_kind(kind)
    hits = [x for x in load_quick(root).limits if x.provider == provider and x.kind == want]
    return hits[-1] if hits else None


def _operator(provider: str, section: str, writer: Path) -> str:
    """Câu mở đầu cho agent thao tác trình duyệt theo nguồn."""
    if provider not in PROVIDER_LABELS:
        raise ValueError(f"Nguồn gen không hỗ trợ: {provider}")
    label = PROVIDER_LABELS[provider]
    extra = (f" và {AGENTS / 'flow-operator.md'} (kiến thức giao diện Flow, tải file, điều kiện dừng)"
             if provider == "flow" else "")
    return (f"Bạn là operator gen trên {label}, dùng phiên Chrome đã đăng nhập của người dùng. Đọc và tuân thủ mục "
            f"'{provider}' trong {GUIDES / 'gen-providers.md'}{extra}, và mục '{section}' trong {writer}.")


def _limit_rule(cli: str, root: Path, provider: str, kind: str) -> str:
    return (f"Hết lượt/hết tín dụng ở {PROVIDER_LABELS[provider]}, hoặc giao diện đòi bật thanh toán / nhập thẻ / "
            f"API key trả phí / báo phí → KHÔNG bấm tiếp, chạy `{cli} limit -p {root} --provider {provider} "
            f"--kind {kind} --reason \"<nguyên văn>\"` rồi DỪNG và báo cáo.")


def claude_task(kind: str, project_root: Path, preset: Preset, provider: str | None = None) -> str:
    root = project_root
    provider = resolve_provider(kind, project_root, provider)
    cli = CLI
    writer = AGENTS / "quick-writer.md"
    common = _common(root, preset)
    if kind == "ideas":
        return (f"Bạn là quick-writer (bước ý tưởng). Đọc và tuân thủ {writer}. {common} "
                "Đề xuất ĐÚNG 5 ý tưởng video viral theo Giai đoạn 1 của brief (tránh trùng ý tưởng cũ trong quick.yaml nếu có). "
                f"Ghi file JSON `[{{\"title\", \"hook\", \"why_viral\"}}]` rồi chạy `{cli} set-ideas -p {root} --json <file>`.")
    if kind == "script":
        return (f"Bạn là quick-writer (bước kịch bản). Đọc và tuân thủ {writer}. {common} "
                "Viết TOÀN BỘ kịch bản lời dẫn cho ý tưởng đã chọn (quick.yaml: picked, ideas) theo Giai đoạn 2 của brief, "
                "rồi tách thành các mốc: mỗi mốc 1 câu hoặc cụm ngắn đọc khoảng 2–6 giây, giữ nguyên thứ tự và từng chữ. "
                f"Ghi file JSON là mảng chuỗi rồi chạy `{cli} set-beats -p {root} --json <file>` (ghi mới beats.json)."
                " Sau đó đề xuất nhân vật RIÊNG của video (ngoài nhân vật bộ kênh: "
                f"`{cli} chars -p {root} --json`) theo mục 'Nhân vật' trong quick-writer.md; ghi file JSON "
                f"`[{{\"id\", \"name\", \"desc\", \"color\"}}]` rồi chạy `{cli} set-chars -p {root} --json <file>` "
                "(không có nhân vật riêng thì ghi mảng rỗng).")
    if kind == "prompts":
        return (f"Bạn là quick-writer (bước prompt ảnh + clip). Đọc và tuân thủ {writer}. {common} "
                f"Lấy mốc bằng `{cli} beats -p {root} --json`, nhân vật bằng `{cli} chars -p {root} --json`, "
                f"cài đặt (clips.max, clips.enabled, allow_cont) bằng `{cli} status -p {root} --json`. Viết image prompt cho mọi mốc "
                "chưa có prompt đạt (review trống hoặc fail) hoặc có `error` (Flow từ chối — viết lại tránh nội dung bị chặn) theo Giai đoạn 3 của brief: mỗi prompt = câu neo đầu NGUYÊN VĂN "
                f"«{preset.style_anchor_start}» + mô tả cảnh bằng tiếng Anh + câu neo cuối NGUYÊN VĂN "
                f"«{preset.style_anchor_end}». Không thêm mốc [MM:SS] vào prompt. Mọi nhân vật đã khai báo phải nhắc "
                "bằng @TÊN (IN HOA, đúng id). Mốc tiếp nối cùng khoảnh khắc với mốc liền trước: thêm \"cont\": true "
                "(chỉ khi allow_cont). Sau mỗi prompt tự kiểm duyệt theo bảng kiểm trong quick-writer.md; trượt thì viết lại, "
                "tối đa 2 lần; ghi verdict/score/issues của lần cuối. "
                f"Làm theo lô {BATCH} mốc: mỗi lô ghi file JSON `[{{\"n\", \"prompt\", \"verdict\", \"score\", \"issues\", \"cont\"}}]` "
                f"rồi chạy `{cli} set-prompts -p {root} --json <file>`. Lặp tới hết mốc. "
                "Cuối cùng chọn tối đa max_clips mốc có hành động rõ nhất để làm clip động (bỏ qua nếu max_clips = 0 "
                "hoặc đã đủ clip bật), viết prompt clip theo mục 'Clip động' trong quick-writer.md, tự kiểm duyệt, "
                f"ghi `[{{\"n\", \"prompt\", \"verdict\", \"score\", \"issues\"}}]` bằng `{cli} set-clip-prompts -p {root} --json <file>`.")
    if kind == "flow":
        label = PROVIDER_LABELS.get(provider, provider)
        return (f"{_operator(provider, 'Gen ảnh mốc', writer)} {common} "
                f"Lấy việc bằng `{cli} beats -p {root} --json --todo` (mốc gen được ngay; trường `file` là tên đích "
                "NNN_MM-SS; `attach` là các ảnh phải đính kèm theo đúng thứ tự trước khi dán prompt; `blocked` là mốc "
                f"chưa gen được — KHÔNG gen, chỉ báo). Gen ẢNH (không phải video) trên {label}, tỉ lệ {preset.aspect}, "
                f"x1 mỗi mốc, prompt nguyên văn `prompt`, theo lô {BATCH} mốc. Tải từng ảnh về rồi chạy ngay "
                f"`{cli} set-image -p {root} <n> \"<file tải về>\" --provider {provider}` — lệnh tự lưu thành "
                "images/NNN_MM-SS.jpg và cập nhật beats.json. Dịch vụ từ chối prompt → "
                f"`{cli} fail -p {root} <n> --reason \"<nguyên văn>\"` rồi sang mốc sau. "
                f"{_limit_rule(cli, root, provider, 'image')} "
                f"Hết lô thì chạy lại `{cli} beats -p {root} --json --todo` và làm lô tiếp cho tới khi `beats` rỗng. "
                "Báo cáo: số ảnh đã gen, mốc lỗi kèm lý do, mốc bị chặn kèm lý do, lượt/tín dụng còn lại nếu thấy.")
    if kind == "sheets":
        label = PROVIDER_LABELS.get(provider, provider)
        return (f"{_operator(provider, 'Gen character sheet', writer)} {common} Lấy nhân vật bằng "
                f"`{cli} chars -p {root} --json`; với mỗi nhân vật có `image` null và `uses` > 0: gen MỘT ảnh "
                f"character sheet trên {label} (tỉ lệ 16:9, x1) theo mẫu prompt trong mục đó, tải về rồi chạy "
                f"`{cli} char-image -p {root} <ID> \"<file>\"` (thêm `--channel` khi `scope` là channel; KHÔNG thêm --provider vào "
                f"char-image — chỉ ghi nguồn --provider {provider} trong báo cáo). {_limit_rule(cli, root, provider, 'image')} "
                "Báo cáo: nhân vật đã gen, nhân vật lỗi kèm lý do, lượt/tín dụng còn lại nếu thấy.")
    if kind == "clips":
        label = PROVIDER_LABELS.get(provider, provider)
        return (f"{_operator(provider, 'Gen clip động', writer)} {common} Lấy việc bằng "
                f"`{cli} beats -p {root} --json --todo-clips` (model, độ phân giải, và từng clip: ảnh nguồn `image`, "
                f"`prompt`, `duration`). Mỗi clip: tạo VIDEO từ ảnh trên {label}, đính `image` làm khung đầu, chọn "
                "model gần `video_model` nhất mà nguồn này có, thời lượng ngắn nhất ≥ `duration` (không có thì dài nhất), "
                "dán `prompt` nguyên văn, tải bản `resolution` (hoặc gần nhất) về rồi chạy "
                f"`{cli} set-clip -p {root} <n> \"<file>\" --provider {provider}`. Từ chối/lỗi → "
                f"`{cli} fail -p {root} <n> --clip --reason \"<nguyên văn>\"`. "
                f"{_limit_rule(cli, root, provider, 'video')} Tuần tự từng clip. "
                "Báo cáo: số clip đã gen, clip lỗi kèm lý do, lượt/tín dụng còn lại nếu thấy.")
    raise ValueError(f"Không hỗ trợ việc '{kind}'")


def claude_cmd(kind: str, project_root: Path, preset: Preset, provider: str | None = None) -> list[str]:
    cmd = ["claude", "-p", "--permission-mode", "bypassPermissions"]
    if kind in CHROME_KINDS:
        cmd.append("--chrome")
    return cmd + [claude_task(kind, project_root, preset, provider)]


def run_claude(kind: str, project_root: Path, preset: Preset, *, provider: str | None = None, log: IO | None = None) -> int:
    """Chạy job Claude đồng bộ (CLI). UI nên dùng `claude_cmd` với JobRunner riêng."""
    r = subprocess.run(claude_cmd(kind, project_root, preset, provider), cwd=REPO, stdin=subprocess.DEVNULL,
                       stdout=log, stderr=subprocess.STDOUT if log else None)
    return r.returncode


def review_task(project_root: Path, preset: Preset, n: int, *, clip: bool = False) -> str:
    """Kiểm duyệt ĐỘC LẬP một mốc (nút "Lưu & kiểm duyệt" trên UI). Không dùng Chrome nên chạy song song job Flow."""
    root = project_root
    what = "clip" if clip else "ảnh"
    flag = " --clip" if clip else ""
    return (f"Bạn đóng vai prompt-reviewer ĐỘC LẬP (không phải người viết prompt). {_common(root, preset)} "
            f"Dùng bảng kiểm {'mục Clip động' if clip else 'mục Image prompt'} trong {AGENTS / 'quick-writer.md'}. "
            f"Kiểm duyệt prompt {what} của mốc {n}: lấy bằng `{CLI} beats -p {root} --json` (đọc cả mốc {n - 1} và "
            f"{n + 1} để xét nhất quán), nhân vật bằng `{CLI} chars -p {root} --json`. KHÔNG sửa prompt. Ghi kết quả: "
            f"`{CLI} set-review -p {root} {n}{flag} --verdict pass|fail --score <0-10> --issue \"<lỗi + gợi ý sửa>\"` "
            "(lặp --issue cho từng ý, tiếng Việt). In một dòng tóm tắt.")


def review_cmd(project_root: Path, preset: Preset, n: int, *, clip: bool = False) -> list[str]:
    return ["claude", "-p", "--permission-mode", "bypassPermissions", review_task(project_root, preset, n, clip=clip)]
