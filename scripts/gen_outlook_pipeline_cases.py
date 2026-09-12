"""Sinh >=100 case cho eval/outlook/cases.json — nội dung mail THẬT hơn:
nhiều đoạn, chào hỏi, ngữ cảnh, chữ ký, HTML thật (không phải 1 câu trần trụi).
Chạy 1 lần để tạo file, không phải code production. Mỗi case được tự
validate bằng chính OutlookConnector.normalize()/filter_and_classify() thật
ngay trong lúc sinh — bắt lỗi generator trước khi ghi file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.connectors.base import Source  # noqa: E402
from src.connectors.outlook import OutlookConnector  # noqa: E402
from src.models.connection import Connection  # noqa: E402
from src.services.filter_classify import FilterConfig, filter_and_classify  # noqa: E402

OUT_PATH = Path(__file__).resolve().parents[1] / "eval" / "outlook" / "cases.json"
_SOURCE = Source(id="inbox", name="Hộp thư chính")

# ---------------------------------------------------------------------------
# Ngân hàng nội dung thật — tên, công ty, chữ ký, lời chào — để mail không
# lặp lại thành 1 câu khô khan như "Please submit X before Y."
# ---------------------------------------------------------------------------

SENDERS_EN = [
    ("Jordan Lee", "jordan.lee@northwind.example", "Finance Operations"),
    ("Priya Nair", "priya.nair@contoso.example", "Product Management"),
    ("Marcus Webb", "marcus.webb@fabrikam.example", "Engineering"),
    ("Sofia Alvarez", "sofia.alvarez@northwind.example", "People Operations"),
    ("Daniel Kim", "daniel.kim@contoso.example", "Client Success"),
    ("Grace Osei", "grace.osei@fabrikam.example", "Legal"),
    ("Ethan Brooks", "ethan.brooks@northwind.example", "IT Support"),
    ("Nadia Farouk", "nadia.farouk@contoso.example", "Marketing"),
]

RECIPIENT_NAMES_EN = ["Alex", "Taylor", "Jamie", "Morgan", "Casey", "Riley"]

SENDERS_VI = [
    ("Nguyễn Thảo Vy", "vy.nguyen@vietsoft.example", "Phòng Nhân sự"),
    ("Trần Minh Khôi", "khoi.tran@vietsoft.example", "Phòng Kỹ thuật"),
    ("Lê Bảo Trâm", "tram.le@dtsolutions.example", "Phòng Kế toán"),
    ("Phạm Anh Tú", "tu.pham@dtsolutions.example", "Ban Dự án"),
]

RECIPIENT_NAMES_VI = ["An", "Bảo", "Chi", "Duy", "Hà", "Khang"]

DAYS_EN = ["Friday", "Monday", "Tuesday", "Wednesday", "Thursday"]
DAYS_VI = ["thứ Sáu", "thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm"]

ACCEPTED_SCENARIOS_EN = [
    {
        "subject": "Q{q} budget sheet — need your review",
        "context": (
            "Hope you're doing well. As we discussed in yesterday's sync, we still need "
            "the Q{q} budget sheet finalized before we can present it to leadership next week."
        ),
        "ask": "Could you please review the budget sheet and send back your comments {deadline}?",
        "closing": "The finance team is waiting on this to close out the quarter. Let me know if you run into any blockers.",
    },
    {
        "subject": "Action needed: {task} for Project Phoenix",
        "context": (
            "Thanks for the update in this week's standup. The client is asking for a status "
            "update on {task}, and we want to make sure we're aligned before the review call."
        ),
        "ask": "Please submit {task} {deadline} so I can compile everything for the client.",
        "closing": "Happy to hop on a quick call if anything is unclear.",
    },
    {
        "subject": "Reminder: contract renewal paperwork",
        "context": (
            "Following up on our conversation last week about the vendor contract renewal. "
            "Legal flagged a couple of clauses that still need sign-off from your side."
        ),
        "ask": "Could you please confirm the updated terms {deadline}?",
        "closing": "Once we have your confirmation, we can move forward with signing.",
    },
    {
        "subject": "Please review the onboarding checklist",
        "context": (
            "We have a new hire starting next month and want to make sure the onboarding "
            "checklist is accurate before we send it out."
        ),
        "ask": "Please review the checklist and reply {deadline} with any changes.",
        "closing": "Thanks so much for helping us get this right.",
    },
    {
        "subject": "Client escalation — response needed",
        "context": (
            "One of our key clients raised a concern during today's check-in call about the "
            "delivery timeline for their project."
        ),
        "ask": "Could you please send a written response to the client {deadline}?",
        "closing": "I'd rather we get ahead of this before it becomes a bigger issue.",
    },
]

ACCEPTED_SCENARIOS_VI = [
    {
        "subject": "Cần {task} trước cuộc họp tuần sau",
        "context": (
            "Như đã trao đổi trong buổi họp hôm qua, đội mình vẫn cần hoàn thiện {task} "
            "trước khi trình bày với ban lãnh đạo vào tuần sau."
        ),
        "ask": "Bạn giúp mình xem lại {task} và phản hồi {deadline} nhé.",
        "closing": "Đội tài chính đang chờ phần này để chốt số liệu quý.",
    },
    {
        "subject": "Nhắc việc: {task} cho dự án Phoenix",
        "context": (
            "Cảm ơn bạn đã cập nhật trong buổi standup tuần này. Khách hàng đang hỏi tiến độ "
            "{task}, mình cần thống nhất trước cuộc họp review."
        ),
        "ask": "Bạn gửi lại {task} {deadline} giúp mình để tổng hợp cho khách hàng nhé.",
        "closing": "Có gì chưa rõ mình trao đổi thêm qua call cũng được.",
    },
    {
        "subject": "Nhắc gia hạn hợp đồng với đối tác",
        "context": (
            "Tiếp nối trao đổi tuần trước về việc gia hạn hợp đồng với nhà cung cấp. "
            "Bên pháp lý có đánh dấu vài điều khoản cần bạn xác nhận."
        ),
        "ask": "Bạn xác nhận lại các điều khoản mới {deadline} giúp mình nhé.",
        "closing": "Sau khi có xác nhận của bạn, mình sẽ tiến hành ký hợp đồng.",
    },
]

NEWSLETTER_TEMPLATES_EN = [
    {
        "sender_name": "Northwind Weekly",
        "sender_email": "no-reply@newsletter.northwind.example",
        "subject": "Northwind Weekly Digest — Issue {n}",
        "body": (
            "<h2>This Week's Highlights</h2>"
            "<p>Welcome back to Northwind Weekly! Here's what's new across the company this week.</p>"
            "<h3>Product Updates</h3>"
            "<p>Our engineering team shipped several performance improvements this sprint.</p>"
            "<h3>Upcoming Events</h3>"
            "<p>Join us for the monthly town hall streaming live on the company portal.</p>"
            "<p style='font-size:11px;color:#888'>You are receiving this digest because you subscribed to "
            "company updates. <a href='#'>Unsubscribe</a> from this newsletter at any time.</p>"
        ),
    },
    {
        "sender_name": "Contoso Product Updates",
        "sender_email": "digest@updates.contoso.example",
        "subject": "What's New This Month — {month}",
        "body": (
            "<p>Here's your monthly digest of product updates and announcements.</p>"
            "<ul><li>New dashboard widgets</li><li>Faster export times</li><li>Bug fixes and improvements</li></ul>"
            "<p style='font-size:11px;color:#888'>This is an automated digest. "
            "Unsubscribe anytime from your notification settings.</p>"
        ),
    },
    {
        "sender_name": "Fabrikam Community",
        "sender_email": "newsletter@community.fabrikam.example",
        "subject": "Community Newsletter — {month} Edition",
        "body": (
            "<p>Read the latest community digest curated by our newsletter team.</p>"
            "<p>This month we're featuring member spotlights, upcoming webinars, and a roundup "
            "of forum discussions.</p>"
            "<p style='font-size:11px;color:#888'>You are receiving this because you subscribed. "
            "<a href='#'>Unsubscribe here</a>.</p>"
        ),
    },
]


def _is_grounded_html(text: str) -> str:
    return text


def _normalize_case(provider_user_id: str, raw_item: dict) -> dict:
    connection = Connection(provider_user_id=provider_user_id)
    connector = OutlookConnector(connection, db=None)
    return connector.normalize(raw_item, _SOURCE)


def _make_case(
    case_id: int,
    description: str,
    *,
    provider_user_id: str,
    raw_item: dict,
    expect_filter_status: str | None,
    expect_must_not_miss: bool | None = None,
    expect_is_self: bool | None = None,
    expect_sent_at_resolved: bool | None = None,
    expect_attachments_empty: bool | None = None,
    expect_text_contains: list[str] | None = None,
    expect_text_excludes: list[str] | None = None,
) -> dict:
    normalized = _normalize_case(provider_user_id, raw_item)

    normalized_block: dict = {}
    if expect_is_self is not None:
        assert normalized["is_self"] == expect_is_self, f"OTL-{case_id:03d} is_self mismatch: {description}"
        normalized_block["is_self"] = expect_is_self
    if expect_sent_at_resolved is not None:
        resolved = normalized["sent_at"] != "unknown"
        assert resolved == expect_sent_at_resolved, f"OTL-{case_id:03d} sent_at_resolved mismatch: {description}"
        normalized_block["sent_at_resolved"] = expect_sent_at_resolved
    if expect_attachments_empty is not None:
        assert (normalized["attachments"] == []) == expect_attachments_empty, f"OTL-{case_id:03d} attachments mismatch"
        normalized_block["attachments_equals"] = []
    if expect_text_contains:
        for snippet in expect_text_contains:
            assert snippet in normalized["text"], f"OTL-{case_id:03d} missing '{snippet}' in text: {description}"
        normalized_block["text_contains"] = expect_text_contains
    if expect_text_excludes:
        for snippet in expect_text_excludes:
            assert snippet not in normalized["text"], f"OTL-{case_id:03d} unexpected '{snippet}' in text: {description}"
        normalized_block["text_excludes"] = expect_text_excludes

    expected: dict = {}
    if normalized_block:
        expected["normalized"] = normalized_block

    if expect_filter_status is not None:
        config = FilterConfig(user_email=provider_user_id)
        result = filter_and_classify([normalized], config)
        if expect_filter_status == "accepted":
            assert len(result["items"]) == 1, f"OTL-{case_id:03d} expected accepted, got rejected: {description}"
            filter_block = {"status": "accepted"}
            if expect_must_not_miss is not None:
                assert result["items"][0]["must_not_miss"] == expect_must_not_miss, f"OTL-{case_id:03d} must_not_miss mismatch"
                filter_block["must_not_miss"] = expect_must_not_miss
        else:
            assert len(result["items"]) == 0, f"OTL-{case_id:03d} expected rejected, got accepted: {description}"
            filter_block = {"status": "rejected"}
        expected["filter"] = filter_block

    return {
        "id": f"OTL-{case_id:03d}",
        "description": description,
        "input": {"provider_user_id": provider_user_id, "raw_item": raw_item},
        "expected": expected,
    }


def _base_raw_item(msg_id: str, **overrides) -> dict:
    item = {
        "id": msg_id,
        "conversationId": f"conv-{msg_id}",
        "subject": "Update",
        "from": {"emailAddress": {"address": "sender@example.edu", "name": "Sender"}},
        "toRecipients": [{"emailAddress": {"address": "student@example.edu"}}],
        "ccRecipients": [],
        "body": {"contentType": "text", "content": "Hello."},
        "bodyPreview": "Hello.",
        "receivedDateTime": "2026-08-10T09:00:00Z",
        "isRead": True,
        "importance": "normal",
        "hasAttachments": False,
        "webLink": f"https://outlook.office.com/mail/inbox/id/{msg_id}",
    }
    item.update(overrides)
    return item


def _html_email(greeting: str, paragraphs: list[str], closing: str, sig_name: str, sig_title: str) -> str:
    body_paragraphs = "".join(f"<p>{p}</p>" for p in paragraphs)
    return (
        f"<div><p>{greeting}</p>{body_paragraphs}<p>{closing}</p>"
        f"<p>Best regards,<br>{sig_name}<br><span style='color:#666'>{sig_title}</span></p></div>"
    )


def _plain_email(greeting: str, paragraphs: list[str], closing: str, sig_name: str, sig_title: str) -> str:
    body = "\n\n".join([greeting, *paragraphs, closing, f"Best regards,\n{sig_name}\n{sig_title}"])
    return body


def build_accepted_cases(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        case_id = start_id + i
        vi = i % 3 == 0
        html = i % 2 == 0
        recipient = RECIPIENT_NAMES_VI[i % len(RECIPIENT_NAMES_VI)] if vi else RECIPIENT_NAMES_EN[i % len(RECIPIENT_NAMES_EN)]
        sender_name, sender_email, sender_title = (SENDERS_VI if vi else SENDERS_EN)[i % len(SENDERS_VI if vi else SENDERS_EN)]

        if vi:
            scenario = ACCEPTED_SCENARIOS_VI[i % len(ACCEPTED_SCENARIOS_VI)]
            deadline = DAYS_VI[i % len(DAYS_VI)]
            task = ["báo cáo tài chính", "bảng khảo sát khách hàng", "tài liệu thiết kế", "hợp đồng đối tác"][i % 4]
            subject = scenario["subject"].format(task=task)
            context = scenario["context"].format(task=task)
            ask_phrase = f"trước {deadline}"
            ask = scenario["ask"].format(task=task, deadline=ask_phrase)
            greeting = f"Chào {recipient},"
        else:
            scenario = ACCEPTED_SCENARIOS_EN[i % len(ACCEPTED_SCENARIOS_EN)]
            deadline = DAYS_EN[i % len(DAYS_EN)]
            task = ["the design doc", "the client report", "the API documentation", "the vendor invoice"][i % 4]
            subject = scenario["subject"].format(q=(i % 4) + 1, task=task)
            context = scenario["context"].format(q=(i % 4) + 1, task=task)
            ask_phrase = f"before {deadline}"
            ask = scenario["ask"].format(task=task, deadline=ask_phrase)
            greeting = f"Hi {recipient},"

        paragraphs = [context, ask]
        closing = scenario["closing"]

        if html:
            body_content = _html_email(greeting, paragraphs, closing, sender_name, sender_title)
            content_type = "html"
        else:
            body_content = _plain_email(greeting, paragraphs, closing, sender_name, sender_title)
            content_type = "text"

        msg_id = f"acc-{case_id:03d}"
        raw_item = _base_raw_item(
            msg_id,
            subject=subject,
            **{"from": {"emailAddress": {"address": sender_email, "name": sender_name}}},
            body={"contentType": content_type, "content": body_content},
            bodyPreview=context[:100],
            isRead=(i % 2 == 0),
        )
        cases.append(
            _make_case(
                case_id,
                f"Accepted #{i + 1} ({'vi' if vi else 'en'}, {'html' if html else 'text'}): "
                f"mail thật nhiều đoạn có chào hỏi + chữ ký, chứa action+deadline -> must_not_miss",
                provider_user_id="student@example.edu",
                raw_item=raw_item,
                expect_filter_status="accepted",
                expect_must_not_miss=True,
                expect_text_contains=[ask_phrase if not html else deadline],
            )
        )
    return cases


def build_rejected_cases(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        case_id = start_id + i
        template = NEWSLETTER_TEMPLATES_EN[i % len(NEWSLETTER_TEMPLATES_EN)]
        subject = template["subject"].format(n=i + 1, month=["January", "February", "March", "April"][i % 4])
        msg_id = f"rej-{case_id:03d}"
        raw_item = _base_raw_item(
            msg_id,
            subject=subject,
            **{"from": {"emailAddress": {"address": template["sender_email"], "name": template["sender_name"]}}},
            body={"contentType": "html", "content": template["body"]},
            bodyPreview=subject,
            isRead=True,
        )
        cases.append(
            _make_case(
                case_id,
                f"Rejected #{i + 1}: newsletter HTML thật nhiều section (heading/list/footer unsubscribe), đã đọc -> filter rejected",
                provider_user_id="student@example.edu",
                raw_item=raw_item,
                expect_filter_status="rejected",
            )
        )
    return cases


def build_self_cases(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        case_id = start_id + i
        is_self = i % 2 == 0
        msg_id = f"self-{case_id:03d}"
        sender_variant = "Me@Example.EDU" if is_self else f"other{i}@example.edu"
        body = _plain_email(
            "Hi team,",
            ["Just leaving a quick reminder note here for my own tracking on this project."],
            "Will follow up after the weekend.",
            "Me",
            "Project Lead",
        )
        raw_item = _base_raw_item(
            msg_id,
            subject="Reminder to self: project tracking",
            **{"from": {"emailAddress": {"address": sender_variant, "name": "Sender"}}},
            body={"contentType": "text", "content": body},
        )
        cases.append(
            _make_case(
                case_id,
                f"is_self #{i + 1}: from {'khớp' if is_self else 'khác'} provider_user_id -> is_self={is_self}",
                provider_user_id="me@example.edu",
                raw_item=raw_item,
                expect_filter_status=None,
                expect_is_self=is_self,
            )
        )
    return cases


def build_timestamp_cases(start_id: int, count: int) -> list[dict]:
    cases = []
    bad_values = [None, "", "not-a-date", "2026-13-40T99:99:99Z"]
    for i in range(count):
        case_id = start_id + i
        resolved = i % 3 == 0
        received = "2026-08-10T09:00:00Z" if resolved else bad_values[i % len(bad_values)]
        msg_id = f"ts-{case_id:03d}"
        body = _plain_email(
            "Hi there,",
            ["Sharing a quick note about the office schedule change for next month."],
            "Let me know if you have questions.",
            "Ops Team",
            "Operations",
        )
        raw_item = _base_raw_item(msg_id, receivedDateTime=received, body={"contentType": "text", "content": body})
        cases.append(
            _make_case(
                case_id,
                f"sent_at #{i + 1}: receivedDateTime {'hợp lệ' if resolved else 'thiếu/lỗi'} -> resolved={resolved}",
                provider_user_id="student@example.edu",
                raw_item=raw_item,
                expect_filter_status=None,
                expect_sent_at_resolved=resolved,
            )
        )
    return cases


def build_html_strip_cases(start_id: int, count: int) -> list[dict]:
    cases = []
    core_paragraphs = [
        "Following up from our sync earlier — please reply before Monday with your availability.",
        "Please review the attached draft and share feedback before Tuesday's call.",
        "Team sync moved to Thursday this week, please confirm you can attend.",
    ]
    for i in range(count):
        case_id = start_id + i
        core = core_paragraphs[i % len(core_paragraphs)]
        style_variant = i % 3
        if style_variant == 0:
            junk = "<style>.x{color:red;font-family:Arial}</style>"
            forbidden = "color:red"
        elif style_variant == 1:
            junk = "<script>trackOpen('outlook');</script>"
            forbidden = "trackOpen"
        else:
            junk = "<style>.y{}</style><script>reportRead();</script>"
            forbidden = "reportRead"
        html = f"{junk}<div><p>Hi,</p><p>{core}</p><p>Thanks,<br>Ops Team</p></div>"
        msg_id = f"html-{case_id:03d}"
        raw_item = _base_raw_item(msg_id, body={"contentType": "html", "content": html}, bodyPreview=core[:80])
        cases.append(
            _make_case(
                case_id,
                f"HTML strip #{i + 1}: script/style bị loại khỏi text, giữ nguyên nội dung thật",
                provider_user_id="student@example.edu",
                raw_item=raw_item,
                expect_filter_status=None,
                expect_text_contains=[core],
                expect_text_excludes=[forbidden],
            )
        )
    return cases


def build_quoted_reply_cases(start_id: int, count: int) -> list[dict]:
    """Mail thật thường có lịch sử quoted-reply bên dưới — OutlookConnector
    KHÔNG cắt phần này (khác _active_text() dùng riêng cho classify_email),
    nên field text/evidence vẫn thấy toàn bộ. Golden case này ghi nhận đúng
    hành vi thật, không phải hành vi lý tưởng."""
    cases = []
    for i in range(count):
        case_id = start_id + i
        deadline = DAYS_EN[i % len(DAYS_EN)]
        new_reply = (
            f"Thanks for the context. I'll make sure to send the updated report before {deadline}. "
            "Adding a couple more people to this thread for visibility."
        )
        quoted_history = (
            "\n\nFrom: Priya Nair\nSent: Monday, August 3, 2026 9:12 AM\n"
            "To: Marcus Webb\nSubject: RE: Status update\n\n"
            "Sure, sounds good. Let's touch base after the review."
        )
        body = new_reply + quoted_history
        msg_id = f"quote-{case_id:03d}"
        raw_item = _base_raw_item(
            msg_id,
            subject="RE: Status update",
            **{"from": {"emailAddress": {"address": "marcus.webb@fabrikam.example", "name": "Marcus Webb"}}},
            body={"contentType": "text", "content": body},
            bodyPreview=new_reply[:100],
            isRead=False,
        )
        cases.append(
            _make_case(
                case_id,
                f"Quoted reply #{i + 1}: mail trả lời có lịch sử quote bên dưới — text giữ nguyên cả phần quote",
                provider_user_id="student@example.edu",
                raw_item=raw_item,
                expect_filter_status="accepted",
                expect_must_not_miss=True,
                expect_text_contains=[deadline, "From: Priya Nair"],
            )
        )
    return cases


def main() -> None:
    cases: list[dict] = []
    cases += build_accepted_cases(1, 35)
    n = len(cases) + 1
    cases += build_rejected_cases(n, 25)
    n += 25
    cases += build_self_cases(n, 10)
    n += 10
    cases += build_timestamp_cases(n, 10)
    n += 10
    cases += build_html_strip_cases(n, 10)
    n += 10
    cases += build_quoted_reply_cases(n, 12)
    n += 12

    assert len(cases) >= 100, f"chỉ có {len(cases)} case"
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "id trùng"

    OUT_PATH.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUT_PATH}")


if __name__ == "__main__":
    main()
