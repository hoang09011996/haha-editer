"""Chạy một việc nền (lệnh vidflow hoặc phiên `claude -p`) và theo dõi log."""
from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
AGENTS = REPO / ".claude" / "agents"

CLI_KINDS = {"tts": "tts", "export_prompts": "prompts", "build": "build"}
CLAUDE_KINDS = ("script", "prompts", "refimg", "flow")
KINDS = tuple(CLI_KINDS) + CLAUDE_KINDS

LABELS = {
    "script": "Claude viết kịch bản chi tiết",
    "prompts": "Claude viết prompt chi tiết",
    "refimg": "Tạo ảnh nhân vật trong Google Flow",
    "flow": "Gen video trong Google Flow",
    "tts": "Tạo voice-over",
    "export_prompts": "Xuất prompts.md",
    "build": "Dựng draft CapCut",
}


def _claude_task(kind: str, project_root: Path, scenes: list[str] | None) -> str:
    rel = project_root
    only = f" Chỉ xử lý các cảnh: {', '.join(scenes)}." if scenes else ""
    common = (f"Thư mục làm việc: {REPO}. Project vidflow: {rel}. Mọi lệnh CLI chạy dạng "
              f"`uv run vidflow <lệnh> -p {rel}`. Người dùng chỉ dùng tín dụng gói Google Flow: KHÔNG chạy "
              "`vidflow gen`, `vidflow estimate`, `vidflow refimg`. Trả lời/báo cáo bằng tiếng Việt, ngắn gọn.")
    if kind == "script":
        return (f"Bạn là scriptwriter. Đọc và tuân thủ {AGENTS / 'scriptwriter.md'}. {common} "
                "Đọc script.yaml (profile.idea là ý tưởng người dùng). Viết/hoàn thiện kịch bản chi tiết: profile, "
                "characters, locations, props, scenes với MỌI ô chi tiết (tiếng Việt). Không sửa cảnh có locked: true, "
                f"không sửa characters có locked: true.{only} Validate đến khi OK.")
    if kind == "prompts":
        return (f"Bạn là prompt-artist. Đọc và tuân thủ {AGENTS / 'prompt-artist.md'}. {common} "
                "Viết veo_prompt (tiếng Anh) + veo_prompt_vi cho các cảnh có prompt cũ hoặc trống (bỏ qua cảnh locked), "
                "viết characters[].description và props[].description tiếng Anh nếu trống hoặc hồ sơ đã đổi, "
                f"rồi chạy `uv run vidflow mark-prompts -p {rel}` cho các cảnh đã viết.{only}")
    if kind == "refimg":
        return (f"Bạn là flow-operator. Đọc và tuân thủ {AGENTS / 'flow-operator.md'} (phần Ảnh nhân vật). {common} "
                "Tạo ảnh tham chiếu trong Google Flow cho mọi nhân vật chưa có ảnh refs/<id>.png|jpg, lưu vào refs/. "
                "KHÔNG gen video.")
    if kind == "flow":
        return (f"Bạn là flow-operator. Đọc và tuân thủ {AGENTS / 'flow-operator.md'}. {common} "
                "Gen video trong Google Flow cho các cảnh `uv run vidflow prompts -p ... --json` liệt kê, tải về, "
                f"import từng cảnh, rồi chạy `uv run vidflow preview -p {rel}`.{only}")
    raise ValueError(kind)


def build_job_cmd(kind: str, project_root: Path, scenes: list[str] | None) -> list[str]:
    if kind in CLI_KINDS:
        cmd = [sys.executable, "-m", "vidflow", CLI_KINDS[kind], "-p", str(project_root)]
        for s in scenes or []:
            cmd += ["-s", s]
        return cmd
    if kind in CLAUDE_KINDS:
        cmd = ["claude", "-p", "--permission-mode", "bypassPermissions"]
        if kind in ("refimg", "flow"):
            cmd.append("--chrome")
        return cmd + [_claude_task(kind, project_root, scenes)]
    raise ValueError(f"Không hỗ trợ việc '{kind}'")


@dataclass
class Job:
    kind: str
    project: str
    log_path: Path
    proc: subprocess.Popen
    started_at: str
    scenes: list[str] | None = None
    _log_file: object = field(default=None, repr=False)

    @property
    def state(self) -> str:
        rc = self.proc.poll()
        return "running" if rc is None else ("done" if rc == 0 else "failed")

    def to_dict(self, tail: int = 20000) -> dict:
        text = self.log_path.read_text(encoding="utf-8", errors="replace") if self.log_path.exists() else ""
        return {"kind": self.kind, "label": LABELS.get(self.kind, self.kind), "project": self.project,
                "state": self.state, "returncode": self.proc.poll(), "started_at": self.started_at,
                "scenes": self.scenes, "log": text[-tail:]}


class JobRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self.current: Job | None = None

    def command_for(self, kind: str, project_root: Path, scenes: list[str] | None) -> list[str]:
        return build_job_cmd(kind, project_root, scenes)

    def busy(self) -> bool:
        return self.current is not None and self.current.state == "running"

    def start(self, kind: str, project: str, project_root: Path, scenes: list[str] | None = None) -> Job:
        with self._lock:
            if self.busy():
                raise RuntimeError(f"Đang chạy: {LABELS.get(self.current.kind, self.current.kind)}")
            logs = project_root / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            log_path = logs / f"job-{stamp}-{kind}.log"
            f = open(log_path, "w", encoding="utf-8")
            proc = subprocess.Popen(self.command_for(kind, project_root, scenes), cwd=REPO, stdout=f,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            self.current = Job(kind, project, log_path, proc, stamp, scenes, f)
            return self.current
