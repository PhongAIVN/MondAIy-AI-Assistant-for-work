"""Dòng "ai gửi cho ai" đặt trước mỗi trích dẫn, theo từng loại nguồn.

Bản tóm tắt không nêu nguồn thì người dùng không biết việc này từ đâu ra. Với
mail thì cặp có ý nghĩa là người gửi/người nhận, nhưng mỗi nền tảng lại có một
cặp khác:

* Gmail/Outlook  -> Từ / Đến / Cc
* Jira           -> người báo cáo / người được giao (KHÔNG phải "Đến": issue
                    không có người nhận, và reporter gán vào "Từ" rồi bỏ trống
                    "Đến" chỉ tạo ra dòng `[Đến: ?]` vô nghĩa)
* Google Calendar-> người tổ chức / người tham dự (trước đây không có
                    author_id/to nên header luôn rỗng — sự kiện lịch vào tóm
                    tắt mà không ai biết ai mời)

Trả về chuỗi RỖNG khi nguồn không có khái niệm người gửi/người nhận. Dán
`[Từ: ?] [Đến: ?]` vào chỗ không có dữ liệu chỉ thêm nhiễu cho cả người đọc
lẫn mô hình.
"""

from __future__ import annotations

_MAX_LISTED = 5

# Tên nền tảng hiển thị cho người dùng. Ở chung với `source_header` vì cùng một
# việc: nói cho người dùng biết thông tin này từ đâu ra. Trước đây bảng này nằm
# private trong task_tool.py, khiến chỗ khác cần dùng phải import biến private
# xuyên module.
PROVIDER_LABELS: dict[str, str] = {
    "google": "Gmail",
    "gmail": "Gmail",
    "outlook": "Outlook",
    "google_calendar": "Google Calendar",
    "google_sheets": "Google Sheets",
    "jira": "Jira",
    "slack": "Slack",
    "discord": "Discord",
    "canvas": "Canvas LMS",
}


def provider_label(provider: str | None) -> str:
    """Tên hiển thị của nguồn; provider lạ thì trả nguyên chuỗi chứ không bịa."""
    key = str(provider or "")
    return PROVIDER_LABELS.get(key, key)


def _people(values: list[str] | None) -> str:
    """Danh sách người, cắt bớt khi quá dài — 40 người tham dự dán nguyên vào
    prompt vừa tốn token vừa đẩy nội dung thật ra khỏi tầm chú ý."""
    items = [str(value).strip() for value in (values or []) if str(value).strip()]
    if not items:
        return ""
    if len(items) <= _MAX_LISTED:
        return ", ".join(items)
    return f"{', '.join(items[:_MAX_LISTED])} (+{len(items) - _MAX_LISTED})"


def _named(name: str | None, identifier: str | None) -> str:
    name = (name or "").strip()
    identifier = (identifier or "").strip()
    if name and identifier and name != identifier:
        return f"{name} <{identifier}>"
    return name or identifier


def _mail_header(item: dict) -> str:
    sender = _named(item.get("author_name"), item.get("author_id"))
    recipients = _people(item.get("to"))
    if not sender and not recipients:
        return ""
    cc = _people(item.get("cc"))
    cc_part = f" [Cc: {cc}]" if cc else ""
    return f"[Từ: {sender or '?'}] [Đến: {recipients or '?'}]{cc_part}"


def _person_name_only(name: str | None, identifier: str | None) -> str:
    """Chỉ TÊN, dùng cho nguồn mà định danh là chuỗi băm.

    Với mail thì `Tên <địa chỉ>` hữu ích — người đọc nhận ra hộp thư. Còn
    accountId của Atlassian ("70121:5780b9fc-7755-4d9a-…") không nói lên điều
    gì, dán vào chỉ làm rối câu tóm tắt. Chỉ rơi về định danh khi không có tên.
    """
    return (name or "").strip() or (identifier or "").strip()


def _jira_header(item: dict) -> str:
    reporter = _person_name_only(item.get("author_name"), item.get("author_id"))
    assignee = _person_name_only(item.get("jira_assignee_name"), item.get("jira_assignee_account_id"))
    if not reporter and not assignee:
        return ""
    status = str(item.get("jira_status") or "").strip()
    status_part = f" [Trạng thái: {status}]" if status else ""
    return f"[Người báo: {reporter or '?'}] [Giao cho: {assignee or 'chưa ai nhận'}]{status_part}"


def _calendar_header(item: dict) -> str:
    organizer = str(item.get("organizer") or "").strip()
    attendees = _people(item.get("attendees"))
    if not organizer and not attendees:
        return ""
    return f"[Người tổ chức: {organizer or '?'}] [Tham dự: {attendees or '?'}]"


_BY_PROVIDER = {
    "google": _mail_header,
    "outlook": _mail_header,
    "jira": _jira_header,
    "google_calendar": _calendar_header,
}


def source_header(item: dict) -> str:
    """Dòng nguồn cho 1 item đã chuẩn hoá. Rỗng khi không có gì đáng nêu.

    Provider lạ đi theo dạng mail — đó là hình dạng chung nhất, và nếu item
    không có author/to thì `_mail_header` tự trả rỗng chứ không bịa.
    """
    builder = _BY_PROVIDER.get(str(item.get("provider") or ""), _mail_header)
    return builder(item)
