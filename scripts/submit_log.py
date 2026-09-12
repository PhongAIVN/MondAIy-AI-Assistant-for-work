#!/usr/bin/env python3
"""
Submit .ai-log/session.jsonl to grading server.
Called by git pre-push hook or manually.

After a successful submit, the live log is rotated:
  - Moved into .ai-log/archive/YYYY-MM-DD.jsonl (appended, never overwritten)
  - The live session.jsonl is recreated empty by the next hook write

If the POST fails, the pending file is restored so nothing is lost.
"""
import json
import os
import shutil
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

def load_env_file(path: Path) -> None:
    """Load simple .env entries when python-dotenv is unavailable.

    The pre-push hook may run in a virtual environment without optional
    packages. AI log submission must still be able to read the repository's
    .env configuration in that case.
    """
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


try:
    from dotenv import load_dotenv
except ImportError:
    load_env_file(Path(".env"))
else:
    load_dotenv()
BATCH_LIMIT = 500
VN_TZ = timezone(timedelta(hours=7))


def _archive_day_for_line(raw_line: bytes) -> str:
    """Resolve archive day from the entry timestamp, normalized to VN timezone.

    Fallback to today's VN date if the line is not valid JSON or lacks a usable
    timestamp. This keeps broken lines archivable instead of dropping them.
    """
    fallback = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    try:
        entry = json.loads(raw_line.decode("utf-8"))
        ts = entry.get("ts")
        if not ts:
            return fallback
        return datetime.fromisoformat(ts).astimezone(VN_TZ).strftime("%Y-%m-%d")
    except Exception:
        return fallback


SERVER_URL = os.environ.get("AI_LOG_SERVER", "")
API_KEY = os.environ.get("AI_LOG_API_KEY", "")
LOG_DIR = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
LOG_FILE = LOG_DIR / "session.jsonl"
ARCHIVE_DIR = LOG_DIR / "archive"


def _archive(pending: Path) -> None:
    """Append pending file to per-day archive based on each entry's timestamp."""
    if not pending.exists() or pending.stat().st_size == 0:
        return
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[bytes]] = defaultdict(list)
    with open(pending, "rb") as src:
        for raw_line in src:
            if not raw_line.strip():
                continue
            grouped[_archive_day_for_line(raw_line)].append(raw_line)

    for day, lines in grouped.items():
        archive_file = ARCHIVE_DIR / f"{day}.jsonl"
        with open(archive_file, "ab") as dst:
            for line in lines:
                dst.write(line)


def _restore_pending(pending: Path) -> None:
    """Failure path: put pending back at LOG_FILE so the next push retries.
    If hook wrote new entries to LOG_FILE in the meantime, prepend pending."""
    if not pending.exists():
        return
    if LOG_FILE.exists():
        # Concat: pending (older) + LOG_FILE (newer) → LOG_FILE
        tmp = LOG_FILE.with_suffix(".merge.jsonl")
        with open(tmp, "wb") as out:
            with open(pending, "rb") as a:
                shutil.copyfileobj(a, out)
            with open(LOG_FILE, "rb") as b:
                shutil.copyfileobj(b, out)
        os.replace(tmp, LOG_FILE)
        pending.unlink()
    else:
        pending.rename(LOG_FILE)


def main():
    if not SERVER_URL:
        print("[ai-log] AI_LOG_SERVER not set — skipping submission.", file=sys.stderr)
        sys.exit(0)

    if not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0:
        print("[ai-log] No logs to submit.", file=sys.stderr)
        sys.exit(0)

    # Atomic rename closes the race window: hook writes that arrive after this
    # land in a fresh LOG_FILE, not in the batch we're about to POST.
    pending = LOG_FILE.with_name(f"session.pending.{int(time.time())}.jsonl")
    try:
        LOG_FILE.rename(pending)
    except FileNotFoundError:
        print("[ai-log] No logs to submit.", file=sys.stderr)
        sys.exit(0)

    entries = []
    leftover_lines = []
    with open(pending, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            if len(entries) >= BATCH_LIMIT:
                leftover_lines.append(line)
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError:
                pass  # drop unparseable line

    if not entries:
        # Nothing to send; archive whatever was there (probably junk) and bail.
        _archive(pending)
        pending.unlink()
        print("[ai-log] No valid entries to submit.", file=sys.stderr)
        sys.exit(0)

    payload = json.dumps({"entries": entries}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(
        SERVER_URL,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[ai-log] Submitted {len(entries)} entries → {resp.status}", file=sys.stderr)
    except urllib.error.URLError as e:
        # Failure: restore the whole pending (including leftover) for next push.
        _restore_pending(pending)
        print(f"[ai-log] Submit failed: {e} — logs kept locally.", file=sys.stderr)
        sys.exit(0)  # Don't block push on server error

    # Success: archive the submitted batch, then handle any leftover.
    _archive(pending)
    pending.unlink()

    if leftover_lines:
        # More than BATCH_LIMIT entries existed; put the rest back so the
        # next push picks them up.
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.writelines(leftover_lines)
        print(
            f"[ai-log] {len(leftover_lines)} entries deferred to next push.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
