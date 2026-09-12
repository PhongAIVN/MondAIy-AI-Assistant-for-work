import json

from scripts.backfill_cursor_logs import (
    build_response_entry,
    extract_prompt_events,
    load_existing_keys,
    parse_cursor_timestamp,
)


def test_parse_cursor_timestamp_vn():
    raw = "Sunday, Aug 9, 2026, 2:09 PM (UTC+7)"
    assert parse_cursor_timestamp(raw) == "2026-08-09T14:09:00+07:00"


def test_extract_prompt_events_from_transcript(tmp_path):
    transcript = tmp_path / "abc-session.jsonl"
    row = {
        "role": "user",
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "<timestamp>Sunday, Aug 9, 2026, 2:09 PM (UTC+7)</timestamp>\n"
                        "<user_query>\nhello old chat\n</user_query>"
                    ),
                }
            ]
        },
    }
    transcript.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    events = extract_prompt_events(transcript)
    assert len(events) == 1
    assert events[0].session_id == "abc-session"
    assert events[0].prompt == "hello old chat"
    assert events[0].ts_iso == "2026-08-09T14:09:00+07:00"


def test_load_existing_keys(tmp_path):
    session_file = tmp_path / "session.jsonl"
    entry = {
        "ts": "2026-08-09T14:09:00+07:00",
        "prompt": "hello old chat",
        "session_id": "abc-session",
    }
    session_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    keys = load_existing_keys(session_file)
    assert ("2026-08-09T14:09:00+07:00", "hello old chat", "abc-session") in keys


def test_load_existing_keys_scans_archive_dir(tmp_path):
    session_file = tmp_path / "session.jsonl"
    session_file.write_text("", encoding="utf-8")
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    entry = {
        "ts": "2026-08-08T10:00:00+07:00",
        "prompt": "archived prompt",
        "session_id": "xyz-session",
    }
    (archive_dir / "2026-08-08.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")

    keys = load_existing_keys(session_file, archive_dir)
    assert ("2026-08-08T10:00:00+07:00", "archived prompt", "xyz-session") in keys


def test_extract_prompt_events_pairs_assistant_response(tmp_path):
    """Response của assistant sau 1 user turn phải được ghép vào PromptEvent.response."""
    transcript = tmp_path / "abc-session.jsonl"
    user_row = {
        "role": "user",
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "<timestamp>Sunday, Aug 9, 2026, 2:09 PM (UTC+7)</timestamp>\n"
                        "<user_query>\nhello old chat\n</user_query>"
                    ),
                }
            ]
        },
    }
    assistant_row = {
        "role": "assistant",
        "message": {"content": [{"type": "text", "text": "here is my answer"}]},
    }
    transcript.write_text(
        json.dumps(user_row, ensure_ascii=False) + "\n" + json.dumps(assistant_row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    events = extract_prompt_events(transcript)
    assert len(events) == 1
    assert events[0].response == "here is my answer"


def test_build_response_entry_offsets_timestamp_by_two_seconds():
    from scripts.backfill_cursor_logs import PromptEvent

    event = PromptEvent(
        ts_iso="2026-08-09T14:09:00+07:00",
        prompt="hello old chat",
        session_id="abc-session",
        transcript_path="dummy.jsonl",
        response="here is my answer",
    )
    entry = build_response_entry(event)
    assert entry is not None
    assert entry["event"] == "stop"
    assert entry["prompt"] == "here is my answer"
    assert entry["session_id"] == "abc-session"
    assert entry["ts"] == "2026-08-09T14:09:02+07:00"


def test_build_response_entry_returns_none_when_no_response():
    from scripts.backfill_cursor_logs import PromptEvent

    event = PromptEvent(
        ts_iso="2026-08-09T14:09:00+07:00",
        prompt="hello old chat",
        session_id="abc-session",
        transcript_path="dummy.jsonl",
        response="",
    )
    assert build_response_entry(event) is None
