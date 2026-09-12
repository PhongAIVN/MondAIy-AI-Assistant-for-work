from datetime import UTC, datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _script_module():
    path = Path(__file__).parents[3] / "scripts" / "fetch_today_gmail.py"
    spec = spec_from_file_location("fetch_today_gmail", path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_today_gmail_output_uses_local_day_and_hides_body_by_default():
    script = _script_module()
    current = datetime(2026, 8, 11, 14, 30, tzinfo=UTC)
    start, end = script.today_window(current)

    output = script.format_output(
        [{
            "id": "mail-1",
            "subject": "Submit report",
            "author_id": "mentor@example.com",
            "sent_at": current - timedelta(hours=1),
            "importance": "important",
            "importance_score": 70,
            "classification_reasons": ["action_signal"],
            "text": "Private email body",
        }],
        start,
        end,
        include_text=False,
    )

    assert start.hour == 0
    assert end == current
    assert output["eligible_count"] == 1
    assert output["messages"][0]["importance_score"] == 70
    assert "text_preview" not in output["messages"][0]
