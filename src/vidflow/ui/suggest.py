"""AI gợi ý nhanh cho một ô trên UI: gọi `claude -p` (model nhanh), nhận về 3 phương án JSON."""
from __future__ import annotations

import json
import re
import subprocess

from vidflow.ui.jobs import REPO


def parse_suggestions(text: str) -> list[str]:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ValueError("AI không trả về danh sách gợi ý")
    data = json.loads(m.group(0))
    if not isinstance(data, list) or not data or not all(isinstance(x, str) for x in data):
        raise ValueError("Định dạng gợi ý không hợp lệ")
    return [x.strip() for x in data if x.strip()][:5]


def build_prompt(label: str, field: str, current: str, context: dict) -> str:
    return (
        "Bạn là trợ lý biên kịch video ngắn (TikTok/Reels) cho người dùng Việt Nam. "
        f"Hãy đưa ra đúng 3 phương án khác nhau cho ô \"{label}\" (khóa `{field}`).\n"
        "Viết tiếng Việt tự nhiên, cụ thể, dùng được ngay; ngắn gọn phù hợp với ô; không đánh số; "
        "không bịa trend không có thật. Nếu ô đang có nội dung, hãy cải thiện nó theo 3 hướng khác nhau.\n"
        f"Nội dung hiện tại của ô: {current or '(trống)'}\n"
        f"Ngữ cảnh project (JSON): {json.dumps(context, ensure_ascii=False)[:6000]}\n"
        "CHỈ trả về một mảng JSON gồm 3 chuỗi, không giải thích."
    )


class Suggester:
    model = "haiku"
    timeout = 120

    def command(self, prompt: str) -> list[str]:
        return ["claude", "-p", "--model", self.model, prompt]

    def run_llm(self, prompt: str) -> str:
        r = subprocess.run(self.command(prompt), cwd=REPO, capture_output=True, text=True,
                           timeout=self.timeout, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout).strip()[:500] or f"claude thoát mã {r.returncode}")
        return r.stdout

    def suggest(self, label: str, field: str, current: str, context: dict) -> list[str]:
        return parse_suggestions(self.run_llm(build_prompt(label, field, current, context)))
