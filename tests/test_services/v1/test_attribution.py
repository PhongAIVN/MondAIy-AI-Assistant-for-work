"""Dòng nguồn "ai gửi cho ai" phải đúng hình dạng của từng nền tảng.

Trước đây hàm này cứng theo dạng mail, nên issue Jira hiện ra
`[Từ: reporter] [Đến: ?]` (Jira không có người nhận) và sự kiện lịch thì rỗng
hẳn vì Calendar không có `author_id`/`to` — việc vào tóm tắt mà không ai biết
ai mời.
"""

import pytest

from src.services.attribution import source_header


def test_mail_uses_sender_and_recipients():
    header = source_header(
        {
            "provider": "google",
            "author_name": "Hatsuki Lynn",
            "author_id": "lynn@example.com",
            "to": ["nhi@example.com"],
            "cc": ["mentor@example.com"],
        }
    )
    assert header == "[Từ: Hatsuki Lynn <lynn@example.com>] [Đến: nhi@example.com] [Cc: mentor@example.com]"


def test_outlook_shares_the_mail_shape():
    header = source_header(
        {"provider": "outlook", "author_name": "An", "author_id": "an@x.com", "to": ["nhi@x.com"]}
    )
    assert header.startswith("[Từ: An <an@x.com>] [Đến: nhi@x.com]")


def test_jira_uses_reporter_and_assignee_not_recipients():
    """Issue không có người nhận. Gán reporter vào "Từ" rồi bỏ trống "Đến" chỉ
    tạo ra dòng `[Đến: ?]` vô nghĩa."""
    header = source_header(
        {
            "provider": "jira",
            "author_name": "HoàiAn Thái",
            "author_id": "acc-hoaian",
            "jira_assignee_name": "Yến Nhi",
            "jira_status": "In Progress",
        }
    )
    # CHỈ tên, không kèm accountId: "70121:5780b9fc-7755-4d9a-…" là chuỗi băm,
    # dán vào câu tóm tắt chỉ làm rối. Khác mail — địa chỉ mail thì hữu ích.
    assert header == "[Người báo: HoàiAn Thái] [Giao cho: Yến Nhi] [Trạng thái: In Progress]"


def test_jira_says_when_nobody_has_picked_the_issue_up():
    header = source_header({"provider": "jira", "author_name": "HoàiAn", "author_id": "acc-1"})
    assert "chưa ai nhận" in header


def test_calendar_uses_organizer_and_attendees():
    header = source_header(
        {
            "provider": "google_calendar",
            "organizer": "mentor@example.com",
            "attendees": ["nhi@example.com", "an@example.com"],
        }
    )
    assert header == "[Người tổ chức: mentor@example.com] [Tham dự: nhi@example.com, an@example.com]"


def test_long_attendee_lists_are_trimmed():
    """40 người tham dự dán nguyên vào prompt vừa tốn token vừa đẩy nội dung
    thật ra khỏi tầm chú ý của mô hình."""
    header = source_header(
        {"provider": "google_calendar", "organizer": "a@x.com", "attendees": [f"u{i}@x.com" for i in range(12)]}
    )
    assert "(+7)" in header
    assert "u11@x.com" not in header


@pytest.mark.parametrize(
    "item",
    [
        {"provider": "google"},
        {"provider": "jira"},
        {"provider": "google_calendar"},
        {"provider": "slack", "to": [], "cc": []},
    ],
)
def test_sources_without_people_produce_no_header(item):
    """Dán `[Từ: ?] [Đến: ?]` vào chỗ không có dữ liệu chỉ thêm nhiễu cho cả
    người đọc lẫn mô hình."""
    assert source_header(item) == ""


def test_unknown_provider_falls_back_to_the_mail_shape():
    header = source_header({"provider": "telegram", "author_name": "Bot", "to": ["me"]})
    assert header == "[Từ: Bot] [Đến: me]"


class TestProviderLabel:
    """Bảng nhãn nguồn dùng chung cho cả công cụ agent lẫn thẻ task trên UI.

    Trước đây nằm private trong task_tool.py nên chỗ khác cần dùng phải import
    biến private xuyên module.
    """

    def test_known_providers_get_a_human_name(self):
        from src.services.attribution import provider_label

        assert provider_label("google") == "Gmail"
        assert provider_label("jira") == "Jira"
        assert provider_label("google_calendar") == "Google Calendar"

    def test_unknown_provider_is_passed_through_not_invented(self):
        from src.services.attribution import provider_label

        assert provider_label("notion") == "notion"

    def test_missing_provider_does_not_crash(self):
        from src.services.attribution import provider_label

        assert provider_label(None) == ""


def test_jira_falls_back_to_the_account_id_only_when_there_is_no_name():
    """Không có tên thì thà hiện chuỗi băm còn hơn để trống người chịu trách nhiệm."""
    header = source_header({"provider": "jira", "author_id": "70121:abc"})
    assert "70121:abc" in header

