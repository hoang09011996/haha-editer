"""Chạy một việc nền (lệnh vidflow hoặc phiên `claude -p`) và theo dõi log."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from vidflow.errors import VidflowError
from vidflow.quick import jobs as qjobs
from vidflow.ui.quick_jobs import QUICK_LABELS, build_quick_cmd, check_provider

REPO = Path(__file__).resolve().parents[3]
AGENTS = REPO / ".claude" / "agents"

CLI_KINDS = {"tts": "tts", "export_prompts": "prompts", "build": "build", "render": "render"}
CLAUDE_KINDS = ("script", "prompts", "refimg", "flow", "assist", "review", "frames_flow")
KINDS = tuple(CLI_KINDS) + CLAUDE_KINDS

LABELS = {
    "script": "Claude viết kịch bản chi tiết",
    "prompts": "Claude viết prompt chi tiết",
    "refimg": "Tạo ảnh nhân vật trong Google Flow",
    "flow": "Gen video trong Google Flow",
    "tts": "Tạo voice-over",
    "export_prompts": "Xuất prompts.md",
    "build": "Dựng draft CapCut",
    "assist": "AI sửa theo yêu cầu",
    "review": "Kiểm duyệt prompt",
    "frames_flow": "Gen ảnh khung trong Google Flow",
    "render": "Render cảnh ảnh (ffmpeg)",
}


def _claude_task(kind: str, project_root: Path, scenes: list[str] | None, instruction: str = "") -> str:
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
    if kind == "review":
        return (f"Bạn là prompt-reviewer, KHÔNG phải người viết prompt. Đọc và tuân thủ {AGENTS / 'prompt-reviewer.md'}. "
                f"{common} Kiểm duyệt mọi prompt cảnh veo và khung ảnh đã duyệt đang 'chưa kiểm duyệt' hoặc 'kiểm duyệt cũ' "
                f"(xem `uv run vidflow frames -p {rel}` và `uv run vidflow prompts -p {rel}`), ghi kết quả bằng "
                f"`uv run vidflow review-set`.{only} Không sửa prompt.")
    if kind == "frames_flow":
        return (f"Bạn là flow-operator. Đọc và tuân thủ {AGENTS / 'flow-operator.md'} (phần Ảnh khung). {common} "
                f"Lấy danh sách bằng `uv run vidflow frames -p {rel} --json`, gen từng ảnh khung trong Google Flow, tải về và "
                f"`uv run vidflow import-frame -p {rel} <scene> <frame> <file>`. Không gen video.{only}")
    if kind == "assist":
        if not instruction.strip():
            raise ValueError("Cần nội dung yêu cầu cho AI")
        return (f"Bạn là biên kịch + đạo diễn hình ảnh. Đọc {AGENTS / 'scriptwriter.md'} và {AGENTS / 'prompt-artist.md'}. "
                f"{common} Người dùng yêu cầu: \"{instruction.strip()}\".{only} Sửa script.yaml đúng theo yêu cầu "
                "(ô tiếng Việt theo scriptwriter; nếu sửa veo_prompt thì theo prompt-artist và chạy mark-prompts). "
                "Không sửa phần locked: true. Validate đến khi OK. Báo cáo ngắn đã đổi gì.")
    raise ValueError(kind)


def build_job_cmd(kind: str, project_root: Path, scenes: list[str] | None, instruction: str = "") -> list[str]:
    if kind in CLI_KINDS:
        cmd = [sys.executable, "-m", "vidflow", CLI_KINDS[kind], "-p", str(project_root)]
        for s in scenes or []:
            cmd += ["-s", s]
        return cmd
    if kind in CLAUDE_KINDS:
        cmd = ["claude", "-p", "--permission-mode", "bypassPermissions"]
        if kind in ("refimg", "flow", "frames_flow"):
            cmd.append("--chrome")
        return cmd + [_claude_task(kind, project_root, scenes, instruction)]
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
    label: str = ""
    stopped: bool = False
    provider: str = ""  # nguồn gen thực dùng (flow | gemini | aistudio) — chỉ job nhanh sheets/flow/clips
    root: Path | None = None

    @property
    def state(self) -> str:
        rc = self.proc.poll()
        if rc is None:
            return "running"
        if self.stopped:
            return "stopped"
        return "done" if rc == 0 else "failed"

    @property
    def quota_exhausted(self) -> bool:
        """Job gen kết thúc vì hết lượt: không bị dừng tay, và mã 3 hoặc nguồn có mốc hết lượt cho loại media của job."""
        rc = self.proc.poll()
        if rc is None or self.stopped or not self.provider:
            return False  # chỉ job gen nhanh (có nguồn) mới có khái niệm hết lượt
        if rc == 3:
            return True
        if self.root is None:
            return False
        try:
            return qjobs.limit_hit(self.root, self.provider, self.kind) is not None
        except (VidflowError, OSError):
            return False

    def to_dict(self, tail: int = 20000) -> dict:
        text = self.log_path.read_text(encoding="utf-8", errors="replace") if self.log_path.exists() else ""
        return {"kind": self.kind, "label": self.label or LABELS.get(self.kind, self.kind), "project": self.project,
                "state": self.state, "returncode": self.proc.poll(), "started_at": self.started_at,
                "scenes": self.scenes, "log": text[-tail:], "provider": self.provider,
                "quota_exhausted": self.quota_exhausted}


class JobLaunchError(Exception):
    """Không khởi chạy được tiến trình của job (lệnh không tồn tại / không chạy được) — API trả 503."""


class JobRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self.current: Job | None = None

    def command_for(self, kind: str, project_root: Path, scenes: list[str] | None, instruction: str = "") -> list[str]:
        return build_job_cmd(kind, project_root, scenes, instruction)

    def quick_command_for(self, kind: str, project_root: Path, instruction: str = "",
                          options: dict | None = None, provider: str | None = None) -> list[str]:
        return build_quick_cmd(kind, project_root, instruction, options, provider)

    def busy(self) -> bool:
        return self.current is not None and self.current.state == "running"

    def start(self, kind: str, project: str, project_root: Path, scenes: list[str] | None = None,
              instruction: str = "", *, quick: bool = False, options: dict | None = None,
              provider: str | None = None) -> Job:
        with self._lock:
            if self.busy():
                raise RuntimeError(f"Đang chạy: {self.current.label or LABELS.get(self.current.kind, self.current.kind)}")
            if quick:
                check_provider(kind, provider)
                if kind in qjobs.GEN_KINDS:
                    # chọn nguồn thực dùng + xóa mốc hết lượt cũ của nguồn đó, ngay trước khi chạy
                    provider = qjobs.begin_gen(project_root, kind, provider)
                cmd = self.quick_command_for(kind, project_root, instruction, options, provider)
                label = QUICK_LABELS.get(kind, kind)
            else:
                if kind == "assist" and not instruction.strip():
                    raise ValueError("Cần nội dung yêu cầu cho AI")
                cmd = (self.command_for(kind, project_root, scenes, instruction) if instruction
                       else self.command_for(kind, project_root, scenes))
                label = LABELS.get(kind, kind)
            logs = project_root / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            log_path = logs / f"job-{stamp}-{kind}.log"
            f = open(log_path, "w", encoding="utf-8")
            try:
                proc = subprocess.Popen(cmd, cwd=REPO, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        start_new_session=True)  # nhóm tiến trình riêng để dừng cả tiến trình con
            except OSError as e:  # vd. `claude` không có trên PATH
                f.close()
                raise JobLaunchError(f"Không chạy được lệnh: {cmd[0]} ({e.strerror or e})") from e
            self.current = Job(kind, project, log_path, proc, stamp, scenes, f, label=label,
                               provider=provider or "", root=project_root)
            return self.current

    def stop(self, timeout: float = 10) -> bool:
        """Dừng việc đang chạy (nút "Tạm dừng") cùng mọi tiến trình con của nó (Remotion, công cụ của claude -p).
        Trả False nếu không có việc nào đang chạy."""
        with self._lock:
            if not self.busy():
                return False
            job = self.current
            if job.proc.poll() is None:
                job.stopped = True
            _signal_group(job.proc, signal.SIGTERM)
        try:
            job.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            pass
        _signal_group(job.proc, signal.SIGKILL)  # dọn tiến trình con còn sót (hoặc tiến trình chính bỏ qua SIGTERM)
        job.proc.wait()
        return True


def _signal_group(proc: subprocess.Popen, sig: int) -> None:
    """Gửi tín hiệu cho cả nhóm tiến trình của job (job chạy với start_new_session=True)."""
    try:
        os.killpg(proc.pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


class ReviewRunner:
    """Hàng đợi RIÊNG cho kiểm duyệt một mốc (`claude -p`, không Chrome): các lần kiểm duyệt chạy tuần tự với nhau
    nhưng độc lập với JobRunner — không bị job Flow đang chạy chặn (nút "Lưu & kiểm duyệt")."""
    timeout = 300

    def __init__(self):
        self._lock = threading.Lock()

    def run(self, cmd: list[str]) -> tuple[int, str]:
        with self._lock:
            # nhóm tiến trình riêng: quá giờ thì diệt cả tiến trình con (Bash của claude chạy `set-review`...),
            # tránh chúng ghi beats.json sau khi đã trả 504 hoặc chồng lên lần kiểm duyệt sau
            try:
                proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                        stdin=subprocess.DEVNULL, start_new_session=True)
            except OSError as e:
                return 127, f"Không chạy được lệnh: {cmd[0]} ({e.strerror or e})"
            try:
                out, err = proc.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                _signal_group(proc, signal.SIGKILL)
                proc.communicate()
                return 124, f"Kiểm duyệt quá {self.timeout} giây"
            return proc.returncode, ((out or "") + (err or "")).strip()
