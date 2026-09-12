from datetime import UTC, datetime
from types import SimpleNamespace

from src.services.calendar_handoff import build_google_calendar_url, build_ics


def _task(**overrides):
    base = {
        "cluster_key": "ck-abc123",
        "title": "Nộp báo cáo tuần 3",
        "detail": "Nộp báo cáo tuần 3 trước hạn.",
        "due_at": datetime(2026, 8, 14, 16, 59, tzinfo=UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_ics_contains_required_vevent_fields():
    ics = build_ics(_task(), evidence=[])

    assert "BEGIN:VCALENDAR" in ics
    assert "BEGIN:VEVENT" in ics
    assert "UID:mondaiy-task-ck-abc123@mondaiy.vn" in ics
    assert "SUMMARY:Nộp báo cáo tuần 3" in ics
    assert "DTSTART:20260814T165900Z" in ics
    assert "END:VEVENT" in ics
    assert "END:VCALENDAR" in ics


def test_build_ics_escapes_special_characters_in_summary():
    task = _task(title="Nộp; báo cáo, tuần 3\nbản cuối")
    ics = build_ics(task, evidence=[])

    assert "SUMMARY:Nộp\\; báo cáo\\, tuần 3\\nbản cuối" in ics


def test_build_ics_appends_evidence_source_lines():
    evidence = [{"evidence_quote": "vui lòng nộp báo cáo", "deep_link": "https://mail.google.com/mail/u/0/#all/m1"}]
    ics = build_ics(_task(), evidence=evidence)

    assert "https://mail.google.com/mail/u/0/#all/m1" in ics.replace("\r\n ", "")


def test_build_google_calendar_url_uses_template_action_no_oauth():
    url = build_google_calendar_url(_task(), evidence=[])

    assert url.startswith("https://calendar.google.com/calendar/render?")
    assert "action=TEMPLATE" in url
    assert "dates=20260814T165900Z" in url


def test_build_ics_folds_long_utf8_lines_at_75_octets():
    ics = build_ics(_task(title="Báo cáo tiếng Việt " * 12), evidence=[])

    physical_lines = ics.split("\r\n")
    assert any(line.startswith(" ") for line in physical_lines)
    assert all(len(line.encode("utf-8")) <= 75 for line in physical_lines)
