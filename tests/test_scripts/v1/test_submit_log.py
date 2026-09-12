import json

from scripts import submit_log


def test_archive_groups_lines_by_entry_day(tmp_path, monkeypatch):
    log_dir = tmp_path / ".ai-log"
    archive_dir = log_dir / "archive"
    pending = log_dir / "session.pending.jsonl"
    log_dir.mkdir()

    first = {
        "ts": "2026-08-06T23:55:00+07:00",
        "tool": "cursor",
        "prompt": "first",
    }
    second = {
        "ts": "2026-08-07T00:05:00+07:00",
        "tool": "cursor",
        "prompt": "second",
    }
    pending.write_text(
        "\n".join((json.dumps(first), json.dumps(second))) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(submit_log, "ARCHIVE_DIR", archive_dir)
    submit_log._archive(pending)

    august_6 = archive_dir / "2026-08-06.jsonl"
    august_7 = archive_dir / "2026-08-07.jsonl"

    assert august_6.exists()
    assert august_7.exists()
    assert '"prompt": "first"' in august_6.read_text(encoding="utf-8")
    assert '"prompt": "second"' in august_7.read_text(encoding="utf-8")


def test_archive_falls_back_for_invalid_or_missing_timestamp(tmp_path, monkeypatch):
    log_dir = tmp_path / ".ai-log"
    archive_dir = log_dir / "archive"
    pending = log_dir / "session.pending.jsonl"
    log_dir.mkdir()
    pending.write_bytes(b'{"tool":"cursor"}\nnot-json\n')

    monkeypatch.setattr(submit_log, "ARCHIVE_DIR", archive_dir)
    monkeypatch.setattr(submit_log, "_archive_day_for_line", lambda _line: "2026-08-06")
    submit_log._archive(pending)

    archive_file = archive_dir / "2026-08-06.jsonl"
    assert archive_file.exists()
    content = archive_file.read_text(encoding="utf-8")
    assert '{"tool":"cursor"}' in content
    assert "not-json" in content
