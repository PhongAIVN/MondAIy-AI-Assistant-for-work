#!/usr/bin/env python3
"""
Backfill AI log cho Cursor từ agent transcripts cục bộ.

Mục tiêu:
- Khôi phục prompt cũ đã bị miss hook.
- Khôi phục response (câu trả lời cuối của assistant cho mỗi turn) thành
  entry riêng, event="stop", cùng session_id, ts = prompt.ts + 2s. Server chỉ
  POST-append (không có API update), nên response không được ghi đè lên entry
  prompt đã archive/đã submit — nó là một dòng mới, dashboard tự sắp đúng thứ
  tự nhờ timestamp, giống cách Claude tách UserPromptSubmit/PostToolUse/Stop
  thành nhiều dòng cho cùng một turn.
- Giữ timestamp gốc trong transcript (UTC+7), không dùng giờ hiện tại.
- Ghi vào .ai-log/session.jsonl để submit_log.py xử lý bình thường.
- Dedup quét cả session.jsonl lẫn archive/ để không lặp lại entry đã archive.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable

VN_TZ = timezone(timedelta(hours=7))
TIMESTAMP_RE = re.compile(r"<timestamp>(.*?)</timestamp>", re.DOTALL)
QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL)
RESPONSE_MAX_CHARS = 2000


def git(cmd: str) -> str:
    """Chạy git command và trả chuỗi rỗng nếu thất bại."""
    try:
        return subprocess.check_output(
            cmd.split(),
            shell=False,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def parse_cursor_timestamp(raw: str) -> str | None:
    """Parse định dạng timestamp của Cursor transcript về ISO8601 (+07:00)."""
    cleaned = raw.strip()
    if "(UTC+7)" in cleaned:
        cleaned = cleaned.replace("(UTC+7)", "").strip()
    try:
        dt = datetime.strptime(cleaned, "%A, %b %d, %Y, %I:%M %p")
        return dt.replace(tzinfo=VN_TZ).isoformat()
    except ValueError:
        return None


@dataclass(frozen=True)
class PromptEvent:
    ts_iso: str
    prompt: str
    session_id: str
    transcript_path: str
    response: str = ""


def _text_blocks(row: dict) -> list[str]:
    """Lấy các đoạn text (bỏ tool_use) trong một message row."""
    message = row.get("message") or {}
    content = message.get("content") or []
    return [item.get("text", "") for item in content if item.get("type") == "text"]


def extract_prompt_events(transcript_file: Path) -> list[PromptEvent]:
    """Trích cặp (user prompt, response cuối của assistant) từ một transcript file."""
    session_id = transcript_file.stem
    rows: list[dict] = []
    for raw_line in transcript_file.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            rows.append(json.loads(raw_line))
        except json.JSONDecodeError:
            continue

    events: list[PromptEvent] = []
    pending: dict | None = None  # {"ts_iso":..., "prompt":...}
    response_parts: list[str] = []

    def flush() -> None:
        nonlocal pending, response_parts
        if pending is not None:
            response = "\n\n".join(p.strip() for p in response_parts if p.strip())
            events.append(
                PromptEvent(
                    ts_iso=pending["ts_iso"],
                    prompt=pending["prompt"],
                    session_id=session_id,
                    transcript_path=str(transcript_file),
                    response=response[:RESPONSE_MAX_CHARS],
                )
            )
        pending = None
        response_parts = []

    for row in rows:
        role = row.get("role")
        if role == "user":
            for text in _text_blocks(row):
                ts_match = TIMESTAMP_RE.search(text)
                query_match = QUERY_RE.search(text)
                if not ts_match or not query_match:
                    continue
                ts_iso = parse_cursor_timestamp(ts_match.group(1))
                prompt = query_match.group(1).strip()
                if not ts_iso or not prompt:
                    continue
                flush()
                pending = {"ts_iso": ts_iso, "prompt": prompt[:1000]}
        elif role == "assistant" and pending is not None:
            response_parts.extend(_text_blocks(row))

    flush()
    return events


def load_existing_keys(
    session_file: Path, archive_dir: Path | None = None
) -> set[tuple[str, str, str]]:
    """Đọc session hiện có + archive (nếu có) để chống ghi trùng (ts, prompt, session_id)."""
    keys: set[tuple[str, str, str]] = set()
    files = [session_file]
    if archive_dir is not None and archive_dir.exists():
        files.extend(sorted(archive_dir.glob("*.jsonl")))
    for path in files:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            keys.add((row.get("ts", ""), row.get("prompt", ""), row.get("session_id", "")))
    return keys


def _repo_meta() -> dict:
    repo = git("git remote get-url origin").rstrip("/").split("/")[-1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return {
        "repo": repo,
        "branch": git("git rev-parse --abbrev-ref HEAD"),
        "commit": git("git rev-parse --short HEAD"),
        "student": git("git config user.email"),
    }


def build_entry(event: PromptEvent) -> dict:
    """Dựng log entry prompt theo schema normalize() cho tool=cursor."""
    return {
        "ts": event.ts_iso,
        "tool": "cursor",
        "event": "beforeSubmitPrompt",
        "session_id": event.session_id,
        "model": "",
        **_repo_meta(),
        "prompt": event.prompt,
        "files_context": [],
        "backfill": True,
        "backfill_source": "cursor-agent-transcripts",
        "backfill_note": "Recovered due to prior Cursor hook failure.",
        "transcript_path": event.transcript_path,
    }


def build_response_entry(event: PromptEvent) -> dict | None:
    """Dựng log entry response, event=stop, ts = prompt.ts + 2s.

    Entry riêng biệt (không sửa entry prompt) — server chỉ append nên đây là
    cách duy nhất thêm response mà không đụng dữ liệu đã submit trước đó.
    """
    if not event.response:
        return None
    try:
        response_ts = (
            datetime.fromisoformat(event.ts_iso) + timedelta(seconds=2)
        ).isoformat()
    except ValueError:
        return None
    return {
        "ts": response_ts,
        "tool": "cursor",
        "event": "stop",
        "session_id": event.session_id,
        "model": "",
        **_repo_meta(),
        "prompt": event.response,
        "files_context": [],
        "backfill": True,
        "backfill_source": "cursor-agent-transcripts",
        "backfill_note": (
            "Recovered assistant response, paired with a prior prompt entry "
            "via session_id and adjacent timestamp."
        ),
        "transcript_path": event.transcript_path,
    }


def iter_transcript_files(root: Path) -> Iterable[Path]:
    """Lấy transcript chính của từng chat, bỏ transcript subagent."""
    for path in sorted(root.glob("**/*.jsonl")):
        if "subagents" in {p.lower() for p in path.parts}:
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Cursor logs from agent transcripts.")
    parser.add_argument("--transcripts-root", required=True, help="Path tới thư mục agent-transcripts.")
    parser.add_argument(
        "--session-file",
        default=".ai-log/session.jsonl",
        help="Đường dẫn file session log cần append.",
    )
    parser.add_argument(
        "--archive-dir",
        default=".ai-log/archive",
        help="Thư mục archive để quét dedup (không ghi vào đây trực tiếp).",
    )
    args = parser.parse_args()

    transcripts_root = Path(args.transcripts_root)
    if not transcripts_root.exists():
        print(f"[backfill] transcripts root not found: {transcripts_root}")
        return 1

    session_file = Path(args.session_file)
    session_file.parent.mkdir(parents=True, exist_ok=True)
    archive_dir = Path(args.archive_dir)
    existing = load_existing_keys(session_file, archive_dir)

    total_candidates = 0
    inserted_prompts = 0
    inserted_responses = 0
    with open(session_file, "a", encoding="utf-8") as out:
        for file in iter_transcript_files(transcripts_root):
            for event in extract_prompt_events(file):
                total_candidates += 1

                prompt_entry = build_entry(event)
                prompt_key = (prompt_entry["ts"], prompt_entry["prompt"], prompt_entry["session_id"])
                if prompt_key not in existing:
                    out.write(json.dumps(prompt_entry, ensure_ascii=False) + "\n")
                    existing.add(prompt_key)
                    inserted_prompts += 1

                response_entry = build_response_entry(event)
                if response_entry is None:
                    continue
                response_key = (
                    response_entry["ts"],
                    response_entry["prompt"],
                    response_entry["session_id"],
                )
                if response_key not in existing:
                    out.write(json.dumps(response_entry, ensure_ascii=False) + "\n")
                    existing.add(response_key)
                    inserted_responses += 1

    print(
        f"[backfill] scanned={total_candidates} "
        f"inserted_prompts={inserted_prompts} inserted_responses={inserted_responses} "
        f"session_file={session_file}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
