"""Job Claude (`claude -p`) cho quy trình nhanh: ideas | script | prompts | flow."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import IO

from vidflow.quick.preset import REPO, Preset, brief_path

AGENTS = REPO / ".claude" / "agents"
QUICK_KINDS = ("ideas", "script", "prompts", "flow")
BATCH = 20
LABELS = {
    "ideas": "Claude đề xuất 5 ý tưởng",
    "script": "Claude viết kịch bản + tách mốc",
    "prompts": "Claude viết prompt ảnh từng mốc",
    "flow": "Gen ảnh trong Google Flow",
}


def claude_task(kind: str, project_root: Path, preset: Preset) -> str:
    root = project_root
    cli = f"uv run vidflow quick"
    brief = brief_path(preset)
    writer = AGENTS / "quick-writer.md"
    common = (f"Thư mục làm việc: {REPO}. Project nhanh: {root} (quick.yaml, beats.json). "
              f"Bộ kênh: {preset.id} — brief gốc: {brief} (đọc TOÀN BỘ, tuân thủ nội dung/giọng/phong cách; "
              "BỎ QUA các chỉ dẫn tương tác trong brief như chờ người dùng trả lời, xuất code block, tạo file tải về). "
              f"Xem trạng thái: `{cli} status -p {root}`. KHÔNG sửa tay quick.yaml, beats.json — mọi ghi đều qua CLI "
              f"`{cli} ...`; file JSON tạm đặt trong {root}/tmp/. Người dùng chỉ dùng tín dụng gói Google Flow: KHÔNG chạy "
              "`vidflow gen`, `vidflow estimate`, `vidflow refimg`. Báo cáo bằng tiếng Việt, ngắn gọn.")
    if kind == "ideas":
        return (f"Bạn là quick-writer (bước ý tưởng). Đọc và tuân thủ {writer}. {common} "
                "Đề xuất ĐÚNG 5 ý tưởng video viral theo Giai đoạn 1 của brief (tránh trùng ý tưởng cũ trong quick.yaml nếu có). "
                f"Ghi file JSON `[{{\"title\", \"hook\", \"why_viral\"}}]` rồi chạy `{cli} set-ideas -p {root} --json <file>`.")
    if kind == "script":
        return (f"Bạn là quick-writer (bước kịch bản). Đọc và tuân thủ {writer}. {common} "
                "Viết TOÀN BỘ kịch bản lời dẫn cho ý tưởng đã chọn (quick.yaml: picked, ideas) theo Giai đoạn 2 của brief, "
                "rồi tách thành các mốc: mỗi mốc 1 câu hoặc cụm ngắn đọc khoảng 2–6 giây, giữ nguyên thứ tự và từng chữ. "
                f"Ghi file JSON là mảng chuỗi rồi chạy `{cli} set-beats -p {root} --json <file>` (ghi mới beats.json).")
    if kind == "prompts":
        return (f"Bạn là quick-writer (bước prompt ảnh). Đọc và tuân thủ {writer}. {common} "
                f"Lấy mốc bằng `{cli} beats -p {root} --json`. Viết image prompt cho mọi mốc chưa có prompt đạt "
                "(review trống hoặc fail) theo Giai đoạn 3 của brief: mỗi prompt = câu neo đầu NGUYÊN VĂN "
                f"«{preset.style_anchor_start}» + mô tả cảnh bằng tiếng Anh + câu neo cuối NGUYÊN VĂN "
                f"«{preset.style_anchor_end}». Không thêm mốc [MM:SS] vào prompt. Giữ cảnh qua các mốc liên tiếp, "
                "nhân vật nhất quán. Sau mỗi prompt tự kiểm duyệt theo bảng kiểm trong quick-writer.md; trượt thì viết lại, "
                "tối đa 2 lần; ghi verdict/score/issues của lần cuối. "
                f"Làm theo lô {BATCH} mốc: mỗi lô ghi file JSON `[{{\"n\", \"prompt\", \"verdict\", \"score\", \"issues\"}}]` "
                f"rồi chạy `{cli} set-prompts -p {root} --json <file>` (lẻ: `{cli} set-prompt -p {root} <n> --prompt ... "
                "--verdict pass|fail --score <n> --issue ...`). Lặp tới hết mốc.")
    if kind == "flow":
        return (f"Bạn là flow-operator. Đọc và tuân thủ {AGENTS / 'flow-operator.md'} (kiến thức giao diện Flow, tải file, "
                f"điều kiện dừng) và phần 'Gen ảnh mốc' trong {writer}. {common} "
                f"Lấy việc bằng `{cli} beats -p {root} --json --todo` (mốc pending/redo đã có prompt đạt; trường `file` là "
                f"tên đích NNN_MM-SS). Gen ẢNH (không phải video) trong Google Flow, tỉ lệ {preset.aspect}, x1 mỗi mốc, "
                f"prompt nguyên văn `prompt`, theo lô {BATCH} mốc. Tải từng ảnh (1K/2K) về rồi chạy ngay "
                f"`{cli} set-image -p {root} <n> \"<file tải về>\"` — lệnh tự lưu thành images/NNN_MM-SS.jpg và cập nhật "
                f"beats.json. Hết lô thì chạy lại `{cli} beats -p {root} --json --todo` và làm lô tiếp cho tới khi rỗng. "
                "Báo cáo: số ảnh đã gen, mốc lỗi kèm lý do, tín dụng còn lại.")
    raise ValueError(f"Không hỗ trợ việc '{kind}'")


def claude_cmd(kind: str, project_root: Path, preset: Preset) -> list[str]:
    cmd = ["claude", "-p", "--permission-mode", "bypassPermissions"]
    if kind == "flow":
        cmd.append("--chrome")
    return cmd + [claude_task(kind, project_root, preset)]


def run_claude(kind: str, project_root: Path, preset: Preset, *, log: IO | None = None) -> int:
    """Chạy job Claude đồng bộ (CLI). UI nên dùng `claude_cmd` với JobRunner riêng."""
    r = subprocess.run(claude_cmd(kind, project_root, preset), cwd=REPO, stdin=subprocess.DEVNULL,
                       stdout=log, stderr=subprocess.STDOUT if log else None)
    return r.returncode
