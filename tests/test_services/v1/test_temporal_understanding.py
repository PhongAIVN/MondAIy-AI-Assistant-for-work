from datetime import UTC, datetime

from src.services.temporal_understanding import resolve_temporal

NOW = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def test_relative_periods_are_high_confidence_and_timezone_aware():
    for text in ("hôm nay", "tuần này", "tuần sau", "tháng này", "tháng sau", "tháng trước"):
        decision = resolve_temporal(text, NOW)
        assert decision.confidence >= 0.98
        assert decision.needs_confirmation is False
        assert decision.time_from.tzinfo == UTC
        assert decision.time_to > decision.time_from


def test_temporal_phrase_is_found_inside_a_natural_sentence():
    decision = resolve_temporal("tóm tắt các việc trong tháng này cho tôi", NOW)

    assert decision.kind == "this_month"
    assert decision.time_from.isoformat() == "2026-08-01T00:00:00+00:00"


def test_month_without_year_requires_confirmation_instead_of_guessing():
    decision = resolve_temporal("tóm tắt việc trong tháng 7", NOW)

    assert decision.kind == "month_without_year"
    assert decision.confidence == 0.62
    assert decision.needs_confirmation is True
    assert "tháng 7 năm 2026" in decision.confirmation_question
    assert decision.time_from is None


def test_explicit_month_year_is_high_confidence():
    decision = resolve_temporal("tháng 7 năm 2025", NOW)

    assert decision.confidence >= 0.98
    assert decision.time_from.isoformat() == "2025-07-01T00:00:00+00:00"
    assert decision.time_to.isoformat() == "2025-08-01T00:00:00+00:00"
