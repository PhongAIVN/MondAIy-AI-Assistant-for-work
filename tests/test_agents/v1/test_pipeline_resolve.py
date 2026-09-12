from src.agents.pipeline.time_resolve import resolve_due_at


def test_resolve_due_at_returns_none_for_empty_expression():
    assert resolve_due_at("") is None


def test_resolve_due_at_returns_none_when_timezone_missing():
    # Có ngày + giờ nhưng thiếu timezone tường minh -> không được đoán (BR-05).
    assert resolve_due_at("Friday 9:00am") is None


def test_resolve_due_at_returns_none_when_time_missing():
    # Có ngày + timezone nhưng thiếu giờ cụ thể.
    assert resolve_due_at("Friday ICT") is None


def test_resolve_due_at_parses_when_date_time_and_timezone_all_present():
    result = resolve_due_at("Friday 9:00am ICT")
    assert result is not None
    assert result.tzinfo is not None


def test_resolve_due_at_accepts_explicit_utc_offset():
    result = resolve_due_at("2026-08-14 17:00 +07:00")
    assert result is not None
    assert result.utcoffset().total_seconds() == 7 * 3600
