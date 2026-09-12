"""Sinh eval/Slack/cases.json — golden dataset cho rule engine Slack thuần
(src/services/slack_rules.py: hard_filter -> score_message -> decide_from_score
-> extract_title/extract_evidence/extract_deadline_phrase, gọi qua
evaluate_message()).

Cùng tinh thần scripts/gen_outlook_pipeline_cases.py (xem eval/outlook/README.md):
mỗi case KHÔNG đoán tay expected — dựng NormalizedMessage (+ RuleConfig nếu
case cần override), chạy evaluate_message()/extract_deadline_phrase() THẬT
ngay lúc sinh, rồi mới ghi expected xuống JSON. Golden dataset này khoá lại
hành vi hiện tại (regression), không phải oracle độc lập — slack_rules.py là
rule engine 100% tất định (không LLM) nên cách này đúng đắn, khác
task_extraction_cases.json (nhãn do kỹ sư gán tay vì is_task_like có sai số).

Chạy: .venv/Scripts/python.exe eval/Slack/gen_cases.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.services.slack_rules import (  # noqa: E402
    NormalizedMessage,
    RuleConfig,
    evaluate_message,
    extract_deadline_phrase,
)

_OUT = Path(__file__).resolve().parent / "cases.json"

_CHANNEL_PREFIX = {
    "public_channel": "C0PUB",
    "private_channel": "C0PRIV",
    "im": "D0DM",
    "mpim": "G0GROUP",
}
_counter = 0


def _ids(channel_type: str) -> tuple[str, str]:
    global _counter
    _counter += 1
    channel_id = f"{_CHANNEL_PREFIX.get(channel_type, 'C0CH')}{_counter:03d}"
    ts = f"{1755230400 + _counter}.000100"
    return channel_id, f"{channel_id}:{ts}"


def _case(
    group: str,
    desc: str,
    *,
    channel_type: str = "public_channel",
    text: str,
    mentions: bool = False,
    subtype: str | None = None,
    thread_ts: str | None = None,
    is_pinned: bool = False,
    is_thread_reply_to_self: bool = False,
    reactions: tuple[str, ...] = (),
    is_self: bool = False,
    author_id: str = "U0AUTHOR",
    config_overrides: dict | None = None,
) -> dict:
    channel_id, message_id = _ids(channel_type)
    message = NormalizedMessage(
        message_id=message_id,
        channel_id=channel_id,
        channel_type=channel_type,
        thread_ts=thread_ts,
        subtype=subtype,
        text=text,
        author_id=author_id,
        is_self=is_self,
        mentions_current_user=mentions,
        reactions=reactions,
        is_pinned=is_pinned,
        is_thread_reply_to_self=is_thread_reply_to_self,
    )
    config = RuleConfig(**(config_overrides or {}))
    decision, title, evidence = evaluate_message(message, config)
    deadline_phrase = extract_deadline_phrase(message)

    return {
        "group": group,
        "description": desc,
        "input": {
            "message_id": message_id,
            "channel_id": channel_id,
            "channel_type": channel_type,
            "thread_ts": thread_ts,
            "subtype": subtype,
            "text": text,
            "author_id": author_id,
            "is_self": is_self,
            "mentions_current_user": mentions,
            "reactions": list(reactions),
            "is_pinned": is_pinned,
            "is_thread_reply_to_self": is_thread_reply_to_self,
            "config_overrides": config_overrides or {},
        },
        "expected": {
            "decision": decision.decision,
            "score": decision.score,
            "reasons": sorted(decision.reasons),
            "title": title,
            "evidence": evidence,
            "deadline_phrase": deadline_phrase,
        },
    }


cases: list[dict] = []

# ---------------------------------------------------------------------------
# A. Hard Filter — DROP tuyệt đối, không tính điểm (30 case)
# ---------------------------------------------------------------------------

_SYSTEM_SUBTYPES = [
    "channel_join",
    "channel_leave",
    "channel_topic",
    "channel_purpose",
    "channel_name",
    "channel_archive",
    "channel_unarchive",
]
for subtype in _SYSTEM_SUBTYPES:
    cases.append(
        _case(
            "hard_filter_system_subtype",
            f"subtype={subtype} kèm nội dung có tín hiệu mạnh vẫn bị DROP trước khi chấm điểm",
            channel_type="public_channel",
            subtype=subtype,
            text="Vui lòng xác nhận trước thứ Sáu, việc này khẩn cấp.",
            mentions=True,
        )
    )
    cases.append(
        _case(
            "hard_filter_system_subtype",
            f"subtype={subtype} với nội dung trơn",
            channel_type="im",
            subtype=subtype,
            text=f"{subtype} event notice",
        )
    )

for i, (channel_type, text) in enumerate(
    [
        ("public_channel", "Please review and confirm before Friday, this is urgent."),
        ("im", "Vui lòng xác nhận gấp giúp mình."),
        ("mpim", "Bản chỉnh sửa mới nhất của tài liệu."),
        ("private_channel", "Updated attachment for the proposal."),
        ("public_channel", "Sửa lại nội dung tin nhắn trước đó."),
        ("im", "Edited version of the earlier message."),
    ]
):
    cases.append(
        _case(
            "hard_filter_message_changed",
            "subtype=message_changed luôn DROP, không giữ bản sửa mới nhất (đơn giản hoá có chủ đích)",
            channel_type=channel_type,
            subtype="message_changed",
            text=text,
            mentions=(i % 2 == 0),
        )
    )

for text in [
    "<@U0PHONG01>",
    "<@U0PHONG01> <@U0THAI02>",
    ":smile:",
    ":+1: :eyes:",
    "<@U0PHONG01> :wave:",
    "   ",
    "",
    "<@U0PHONG01>  <@U0PHONG01>",
    ":raised_hands:",
    "<@U0LAN03> :thumbsup: :tada:",
]:
    cases.append(
        _case(
            "hard_filter_empty_text",
            "text chỉ còn mention/emoji/khoảng trắng sau khi strip -> EMPTY_TEXT",
            channel_type="public_channel",
            text=text,
            mentions=True,
        )
    )

# ---------------------------------------------------------------------------
# B. Scoring — cô lập từng tín hiệu theo RULE_CONFIG (70 case)
# ---------------------------------------------------------------------------

_B1_PAIRS = [
    ("Ảnh mới chụp ở buổi offsite hôm cuối tuần.", "U0LAN03"),
    ("Bộ font chữ mới cho slide thuyết trình.", "U0MINH04"),
    ("Danh sách quán ăn trưa gần văn phòng.", "U0AN05"),
    ("Playlist nhạc cho buổi làm việc chiều nay.", "U0TRANG06"),
    ("Ghi chú linh tinh về bố cục văn phòng mới.", "U0DAT07"),
]
for text, author in _B1_PAIRS:
    cases.append(
        _case(
            "score_mentioned_current_user",
            "mentions_current_user=True cộng MENTIONED_CURRENT_USER, không có tín hiệu khác",
            channel_type="public_channel",
            text=text,
            mentions=True,
            author_id=author,
        )
    )
    cases.append(
        _case(
            "score_mentioned_current_user",
            "cùng nội dung nhưng không bị mention -> không cộng điểm, không tín hiệu nào khác -> DROP",
            channel_type="public_channel",
            text=text,
            mentions=False,
            author_id=author,
        )
    )

_B2_PLAIN = [
    ("im", "Cảm ơn bạn đã giúp mình hôm qua nhé."),
    ("mpim", "Chúc cả nhóm nghỉ ngơi vui vẻ."),
    ("public_channel", "Hôm nay văn phòng khá yên tĩnh."),
    ("private_channel", "Ghi chú riêng tư về bố trí bàn ghế."),
]
for channel_type, text in _B2_PLAIN:
    cases.append(
        _case(
            "score_direct_message",
            f"channel_type={channel_type}, không mention/không tín hiệu khác — chỉ im/mpim mới cộng DIRECT_MESSAGE",
            channel_type=channel_type,
            text=text,
        )
    )
for channel_type in ["im", "mpim"]:
    cases.append(
        _case(
            "score_direct_message",
            f"channel_type={channel_type} nhưng text là newsletter -> DIRECT_MESSAGE bị treo (is_newsletter_or_automated=True)",
            channel_type=channel_type,
            text="Check out this month's newsletter and don't miss our latest offer.",
        )
    )
for channel_type, text in [
    ("im", "Chúc mừng sinh nhật nha, chúc bạn nhiều sức khoẻ."),
    ("mpim", "Vừa gọi món trà sữa ship tới văn phòng."),
    ("im", "Weekend plans anyone? Thinking about a short trip."),
    ("mpim", "Just sharing a fun photo from yesterday."),
]:
    cases.append(
        _case(
            "score_direct_message",
            f"channel_type={channel_type} plain — thêm biến thể nội dung cho đủ 10 case nhóm này",
            channel_type=channel_type,
            text=text,
        )
    )

_B3_PAIRS = [
    "Đã gửi lại bản cập nhật trong thread này rồi.",
    "Following up on my earlier message in the thread.",
    "Bổ sung thêm ảnh chụp màn hình vào thread cũ.",
]
for text in _B3_PAIRS:
    cases.append(
        _case(
            "score_thread_reply_to_self",
            "is_thread_reply_to_self=True cộng THREAD_REPLY_TO_SELF (hiện luôn False từ connector thật — xem TODO(OD-SLACK1), case này test rule engine độc lập)",
            channel_type="public_channel",
            text=text,
            thread_ts="1755230000.000001",
            is_thread_reply_to_self=True,
        )
    )
    cases.append(
        _case(
            "score_thread_reply_to_self",
            "cùng nội dung nhưng is_thread_reply_to_self=False -> không cộng điểm",
            channel_type="public_channel",
            text=text,
            thread_ts="1755230000.000001",
            is_thread_reply_to_self=False,
        )
    )

_B4_PAIRS = [
    "Bức ảnh này đẹp ghê, ai chụp vậy?",
    "Nice view from the rooftop yesterday.",
    "Món này nhìn ngon quá trời.",
]
for text in _B4_PAIRS:
    cases.append(
        _case(
            "score_pinned",
            "is_pinned=True cộng PINNED (connector thật chưa nối pins.list — xem TODO(OD-SLACK3), case này test rule engine độc lập)",
            channel_type="public_channel",
            text=text,
            is_pinned=True,
        )
    )
    cases.append(
        _case(
            "score_pinned",
            "cùng nội dung nhưng is_pinned=False -> không cộng điểm",
            channel_type="public_channel",
            text=text,
            is_pinned=False,
        )
    )

_B5_ACTIONS = [
    "Please check the shared folder for the file.",
    "Có thể reply lại tin nhắn này giúp mình không?",
    "Respond in the thread when you have a moment.",
    "Submit your expense form through the portal.",
    "Send the photos from the trip to everyone.",
    "Complete the onboarding checklist for new hires.",
    "Có ai review giúp đoạn code này không?",
    "Confirm your attendance for the team lunch.",
    "Mọi người vui lòng điền thông tin liên hệ.",
    "Bạn xác nhận giúp mình địa chỉ giao hàng nhé.",
]
for text in _B5_ACTIONS:
    cases.append(
        _case(
            "score_action",
            "ACTION_RE khớp -> HAS_ACTION, không có deadline/urgency/program/newsletter khác",
            channel_type="public_channel",
            text=text,
        )
    )

_B6_DEADLINES = [
    "The report deadline is next week for the whole office.",
    "Membership renewal is due at the end of this month.",
    "Let's finish the slides by end of day today.",
    "Make sure the venue is booked before the holidays.",
    "The front desk stays open until 9pm tonight.",
    "Hạn chót của vòng đăng ký là cuối tháng này.",
    "Buổi tổng kết dự kiến diễn ra trước kỳ nghỉ lễ.",
    "Chuyến bay khởi hành vào thứ Sáu tuần sau.",
    "The trip departs tomorrow morning for everyone joining.",
    "Ghi chú mốc 15/09 vào lịch nhé mọi người.",
]
for text in _B6_DEADLINES:
    cases.append(
        _case(
            "score_deadline_inferred",
            "DEADLINE_RE khớp -> HAS_DEADLINE_INFERRED (luôn suy luận từ text, Slack không có due_date field cứng)",
            channel_type="public_channel",
            text=text,
        )
    )

_B7_URGENCY = [
    "This is urgent, everyone should look at it right away.",
    "Marking this as asap for visibility on the board.",
    "Action required from the ops side on this one.",
    "This needs immediate attention from the whole group.",
    "Việc này gấp lắm, mọi người xem giúp với nhé.",
    "Tình huống khẩn cấp đang xảy ra ở kho hàng.",
    "This is urgente, we need an answer soon.",
    "至急確認をお願いします。",
]
for text in _B7_URGENCY:
    cases.append(
        _case(
            "score_urgency",
            "URGENCY_RE khớp -> URGENT, bao gồm nhánh CJK không dùng \\b",
            channel_type="public_channel",
            text=text,
        )
    )

_B8 = [
    ("Chào cả nhóm buổi sáng nha.", False),
    ("The new course starts registration next month.", True),
    ("Assignment 3 grading will be posted on the portal.", True),
    ("Cohort B kickoff happens in the main hall.", True),
    ("Đồ án tốt nghiệp sẽ trình bày vào buổi hội đồng.", True),
    ("Sync với mentor về roadmap của milestone tiếp theo.", True),
]
for text, should_score in _B8:
    cases.append(
        _case(
            "score_program_relevance",
            "\"nhóm\" bị loại trừ khỏi PROGRAM_RELEVANCE (score_message so sánh casefold != 'nhóm')"
            if not should_score
            else "PROGRAM_RE khớp từ khoá khác 'nhóm' -> PROGRAM_RELEVANCE",
            channel_type="public_channel",
            text=text,
        )
    )

_B9 = [
    ("Don't miss our newsletter with this week's highlights.", {}),
    ("no-reply: your automated status report is ready.", {}),
    ("no-reply newsletter digest is now automated for everyone.", {}),
    ("no-reply: please submit your report by Friday for the automated review.", {}),
]
for text, _ in _B9:
    cases.append(
        _case(
            "score_newsletter_or_automated",
            "NEWSLETTER_RE/AUTOMATED_RE khớp -> NEWSLETTER_OR_AUTOMATED, áp 1 lần dù khớp cả hai, có thể lấn át tín hiệu dương",
            channel_type="public_channel",
            text=text,
        )
    )

# ---------------------------------------------------------------------------
# C. Decision tích hợp — tin nhắn thực tế đa tín hiệu (60 case)
# ---------------------------------------------------------------------------

_C1_KEEP = [
    ("im", "Nhớ nộp báo cáo tuần trước 5h chiều thứ Sáu nhé", True, "U0MENTOR"),
    ("public_channel", "Vui lòng review PR #482 trước khi merge nhé, deadline sáng mai.", False, "U0DEV01"),
    ("mpim", "Team ơi, submit expense report by this Friday please.", True, "U0OPS02"),
    ("im", "Anh confirm giúp em lịch demo với Northwind trước thứ Ba nha.", True, "U0SALES03"),
    ("public_channel", "Việc này gấp: vui lòng xác nhận thông tin khách hàng trước 5pm hôm nay.", True, "U0CS04"),
    (
        "private_channel",
        "Please review the contract draft, it's due before the client call tomorrow.",
        False,
        "U0LEGAL05",
    ),
    ("im", "Chị ơi nhớ gửi slide thuyết trình cho khách trước thứ Hai giúp em.", True, "U0PM06"),
    ("mpim", "Reminder: submit your milestone update before end of day, this is urgent.", False, "U0LEAD07"),
    (
        "public_channel",
        "Mọi người vui lòng đăng ký tham gia workshop trước thứ Tư, chương trình đã gần đầy chỗ.",
        False,
        "U0HR08",
    ),
    ("im", "Please respond to the Fabrikam proposal by tomorrow, it's urgent.", True, "U0BIZDEV09"),
    ("public_channel", "Anh xác nhận giúp em đơn hàng gấp trước 3h chiều nay nhé.", True, "U0OPS10"),
    ("mpim", "Complete the incident report before the postmortem tomorrow, action required.", True, "U0SRE11"),
    ("im", "Nộp bản demo cho mentor trước thứ Sáu tuần này giúp mình.", True, "U0STU12"),
    ("public_channel", "Vui lòng duyệt ngân sách quý này trước cuối tuần, việc khẩn cấp.", False, "U0FIN13"),
    ("private_channel", "Please confirm the Contoso contract terms before Monday's signing.", False, "U0LEGAL14"),
    ("im", "Chị confirm giúp em số lượng khách mời trước thứ Năm nhé, gấp lắm.", True, "U0EVENT15"),
    ("mpim", "Send the updated roadmap slides before tomorrow's sprint review please.", True, "U0PM16"),
    ("public_channel", "Đội dev vui lòng xác nhận đã deploy xong trước 6h chiều, urgent.", False, "U0DEVOPS17"),
    ("im", "Nhớ phản hồi email khách hàng VietSoft trước thứ Ba nhé, hơi gấp.", True, "U0CS18"),
    ("public_channel", "Please submit your leave request before the deadline this Friday.", False, "U0HR19"),
    ("mpim", "Anh review giúp bản dịch tài liệu trước khi gửi khách sáng mai.", True, "U0TRANS20"),
    ("im", "Team cần hoàn thành checklist trước buổi demo với mentor thứ Sáu này.", True, "U0STU21"),
    ("public_channel", "Vui lòng xác nhận tham dự cuộc họp khẩn trước 4h chiều hôm nay.", True, "U0ADMIN22"),
]
for channel_type, text, mentions, author in _C1_KEEP:
    cases.append(
        _case(
            "decision_keep_realistic",
            "tin nhắn công sở thực tế nhiều tín hiệu cộng dồn -> KEEP",
            channel_type=channel_type,
            text=text,
            mentions=mentions,
            author_id=author,
        )
    )
cases.append(
    _case(
        "decision_keep_realistic",
        "hạn chế thật của rule engine: URGENCY_RE khớp thuần regex trên chuỗi con "
        "'gấp' trong 'không gấp đâu' dù câu đang PHỦ ĐỊNH tính khẩn cấp — DM(15)+"
        "ACTION(25)+URGENT(20)=60 vẫn KEEP, không phải lỗi dataset mà là giới hạn"
        " thật của regex không hiểu phủ định (ghi nhận, không tự ý vá ở đây)",
        channel_type="im",
        text="Chị confirm giúp em nhé, không gấp đâu.",
        mentions=False,
        author_id="U0OPS16",
    )
)

_C2_REVIEW = [
    ("public_channel", "Please review the new onboarding doc when you can.", False, "U0HR01"),
    ("im", "Cảm ơn team đã hỗ trợ hôm qua nhé.", False, "U0LEAD02"),
    ("public_channel", "Có ai confirm giúp mình cái này không?", False, "U0DEV03"),
    ("mpim", "Chúc mọi người một tuần làm việc hiệu quả.", False, "U0HR04"),
    ("public_channel", "This needs immediate attention from someone on the team.", False, "U0OPS05"),
    ("im", "Ghi chú lại giúp mình vài điểm trong buổi họp sáng nay.", False, "U0PM06"),
    ("public_channel", "Việc này khẩn cấp, ai rảnh xử lý giúp với.", False, "U0CS07"),
    ("public_channel", "Sync với mentor về roadmap của assignment tuần sau.", False, "U0STU08"),
    ("im", "Chào cả nhóm, hôm nay có gì mới không?", False, "U0INTERN09"),
    ("public_channel", "Please submit feedback whenever convenient, no rush.", False, "U0PM10"),
    ("private_channel", "Anh xác nhận giúp em số liệu này với.", False, "U0FIN11"),
    ("public_channel", "Vừa xem xong bản demo, khá ổn đó.", False, "U0LEAD12"),
    ("public_channel", "Cohort mới sẽ khai giảng vào tháng sau.", False, "U0ACAD13"),
    ("mpim", "Reminder về buổi họp chiều nay nhé mọi người.", False, "U0ADMIN14"),
    ("public_channel", "Có bạn nào review giúp mình đoạn này không?", False, "U0DEV15"),
    ("public_channel", "Action required: cập nhật trạng thái vào bảng theo dõi.", False, "U0PM17"),
    ("public_channel", "Hạn chót của vòng tuyển dụng vẫn chưa chốt.", False, "U0HR18"),
]
for channel_type, text, mentions, author in _C2_REVIEW:
    cases.append(
        _case(
            "decision_review_realistic",
            "1-2 tín hiệu, tổng điểm nằm giữa review_threshold(15) và keep_threshold(35) -> REVIEW",
            channel_type=channel_type,
            text=text,
            mentions=mentions,
            author_id=author,
        )
    )

_C3_DROP = [
    ("public_channel", "Chào cả nhà buổi sáng nha.", "U0RANDOM01"),
    ("public_channel", "Hôm nay văn phòng có trà sữa free nè.", "U0RANDOM02"),
    ("public_channel", "Ai đi ăn trưa không mọi người ơi?", "U0RANDOM03"),
    ("public_channel", "Cuối tuần này đi đâu chơi không ha?", "U0RANDOM04"),
    ("public_channel", "Haha đúng rồi đó, buồn cười ghê.", "U0RANDOM05"),
    ("public_channel", "Trời hôm nay đẹp thật đấy.", "U0RANDOM06"),
    ("private_channel", "Vừa xem xong bộ phim mới ra, hay lắm.", "U0RANDOM07"),
    ("public_channel", "Great game last night, did anyone watch it?", "U0RANDOM08"),
    ("public_channel", "Just grabbed coffee, anyone want some?", "U0RANDOM09"),
    ("public_channel", "Chúc mừng năm mới cả nhà nha.", "U0RANDOM10"),
    ("public_channel", "Con mèo văn phòng dễ thương ghê.", "U0RANDOM11"),
    ("public_channel", "Ừa được đó, để mình xem lại sau.", "U0RANDOM12"),
    ("public_channel", "Bài nhạc này hay ghê, ai biết tên không?", "U0RANDOM13"),
    ("public_channel", "Sale off 50% toàn bộ sản phẩm tuần này, đừng bỏ lỡ khuyến mãi.", "U0MKT14"),
    ("public_channel", "Check out our newsletter, unsubscribe anytime.", "U0MKT15"),
    ("public_channel", "Cảm ơn mọi người đã tham gia sự kiện hôm qua.", "U0EVENT16"),
    ("public_channel", "Nice weather for a walk, isn't it?", "U0RANDOM17"),
    ("public_channel", "Vừa nghe tin đó, hóng quá.", "U0RANDOM18"),
    ("public_channel", "Ảnh chụp buổi team building hôm đó.", "U0HR19"),
    ("public_channel", "Đợt này công ty có thêm phòng nghỉ mới đó.", "U0ADMIN20"),
]
for channel_type, text, author in _C3_DROP:
    cases.append(
        _case(
            "decision_drop_realistic",
            "chat đời thường/quảng cáo, không có tín hiệu việc cần làm hoặc bị treo bởi newsletter -> DROP",
            channel_type=channel_type,
            text=text,
            mentions=False,
            author_id=author,
        )
    )

# ---------------------------------------------------------------------------
# D. Ranh giới ngưỡng chính xác — keep_threshold=35, review_threshold=15 (8 case)
# ---------------------------------------------------------------------------

cases.append(
    _case(
        "decision_threshold_boundary",
        "score đúng bằng keep_threshold (25 action + 10 pinned = 35) -> KEEP",
        channel_type="public_channel",
        text="Vui lòng xác nhận file đính kèm trong buổi họp.",
        is_pinned=True,
    )
)
cases.append(
    _case(
        "decision_threshold_boundary",
        "score đúng bằng keep_threshold (25 action + 10 pinned = 35) -> KEEP, biến thể tiếng Anh",
        channel_type="public_channel",
        text="Please confirm the attached document is correct.",
        is_pinned=True,
    )
)
cases.append(
    _case(
        "decision_threshold_boundary",
        "score = 30 (15 direct_message + 15 thread_reply_to_self), ngay dưới keep_threshold -> REVIEW",
        channel_type="im",
        text="Cảm ơn bạn nhiều nhé.",
        thread_ts="1755230000.000002",
        is_thread_reply_to_self=True,
    )
)
cases.append(
    _case(
        "decision_threshold_boundary",
        "score = 30 (15 direct_message + 15 thread_reply_to_self), ngay dưới keep_threshold -> REVIEW, biến thể mpim",
        channel_type="mpim",
        text="Thanks a lot for your help earlier.",
        thread_ts="1755230000.000003",
        is_thread_reply_to_self=True,
    )
)
cases.append(
    _case(
        "decision_threshold_boundary",
        "score đúng bằng review_threshold (15 direct_message) -> REVIEW",
        channel_type="im",
        text="Chúc bạn cuối tuần vui vẻ nhé.",
    )
)
cases.append(
    _case(
        "decision_threshold_boundary",
        "score đúng bằng review_threshold (15 direct_message) -> REVIEW, biến thể mpim",
        channel_type="mpim",
        text="Have a great weekend everyone.",
    )
)
cases.append(
    _case(
        "decision_threshold_boundary",
        "score = 10 (chỉ pinned), ngay dưới review_threshold -> DROP với reasons=(PINNED,)",
        channel_type="public_channel",
        text="Bức ảnh này đẹp ghê.",
        is_pinned=True,
    )
)
cases.append(
    _case(
        "decision_threshold_boundary",
        "score = 10 (chỉ pinned), ngay dưới review_threshold -> DROP, biến thể private_channel",
        channel_type="private_channel",
        text="Nice photo from the trip.",
        is_pinned=True,
    )
)

# ---------------------------------------------------------------------------
# E. Extraction — extract_title/extract_evidence/extract_deadline_phrase (26 case)
# ---------------------------------------------------------------------------

_E1_SIGNAL_SENTENCE = [
    ("im", "Chào cả nhóm buổi sáng. Vui lòng gửi báo cáo trước 5h chiều nay. Cảm ơn mọi người.", True),
    ("im", "Good morning everyone. Please review the proposal by Friday. Thanks so much.", True),
    ("public_channel", "Hi team. Submit the timesheet before Monday please. Have a good day.", False),
    ("mpim", "Chào buổi chiều. Nhớ xác nhận danh sách khách mời trước thứ Tư nhé. Cảm ơn.", True),
    ("im", "Hey there. Confirm your slot before tomorrow please. Appreciate it.", True),
    ("public_channel", "Xin chào cả team. Vui lòng duyệt tài liệu trước thứ Sáu này. Cảm ơn nhiều.", False),
    ("mpim", "Morning all. Send the updated deck before the client call tomorrow. Cheers.", True),
    ("im", "Chào anh chị. Hoàn thành checklist trước cuối ngày hôm nay giúp em. Em cảm ơn.", True),
]
for channel_type, text, mentions in _E1_SIGNAL_SENTENCE:
    cases.append(
        _case(
            "extract_title_prefers_signal_sentence",
            "extract_title ưu tiên câu khớp ACTION_RE/DEADLINE_RE, không lấy câu chào/kết",
            channel_type=channel_type,
            text=text,
            mentions=mentions,
        )
    )

_E2_FALLBACK_FIRST_SENTENCE = [
    ("im", "Hôm nay trời đẹp quá. Mọi người khoẻ không?"),
    ("mpim", "Just finished lunch. Anyone up for coffee later?"),
    ("im", "Đang nghe bài hát này hay ghê. Bạn có biết tên bài không?"),
    ("public_channel", "Vừa dọn xong bàn làm việc. Cảm thấy gọn gàng hẳn."),
    ("mpim", "The office plant finally bloomed. Kind of a nice surprise."),
]
for channel_type, text in _E2_FALLBACK_FIRST_SENTENCE:
    cases.append(
        _case(
            "extract_title_fallback_first_sentence",
            "không câu nào khớp ACTION_RE/DEADLINE_RE -> extract_title lấy câu đầu tiên",
            channel_type=channel_type,
            text=text,
            mentions=True,
        )
    )
cases.append(
    _case(
        "extract_title_fallback_first_sentence",
        "\"Câu thứ hai\" là cách nói thứ tự, KHÔNG tính là câu tín hiệu (_is_signal_sentence loại trừ) dù DEADLINE_RE khớp nguyên văn bản do chứa 'thứ hai'",
        channel_type="im",
        text="Không có tín hiệu gì đặc biệt ở đây. Câu thứ hai trong tin nhắn này.",
        mentions=True,
    )
)

_E3_LONG_TEXT = [
    (
        "public_channel",
        "Vui lòng chuẩn bị đầy đủ toàn bộ hồ sơ giấy tờ cần thiết cho buổi họp tổng kết quý này trước thứ Sáu nhé mọi người trong team",
        False,
    ),
    (
        "public_channel",
        "Please make sure every single document required for the quarterly review meeting is fully prepared before Friday for everyone",
        False,
    ),
    (
        "im",
        "Hôm nay mình vừa dọn dẹp lại toàn bộ góc làm việc và sắp xếp lại tủ tài liệu cho gọn gàng hơn một chút xíu",
        True,
    ),
    (
        "mpim",
        "Just spent the whole afternoon reorganizing the shared drive folders so everything is easier to find from now on",
        True,
    ),
]
for channel_type, text, mentions in _E3_LONG_TEXT:
    cases.append(
        _case(
            "extract_title_truncation",
            "câu dài hơn 80 ký tự bị cắt và thêm dấu … (_truncate_title)",
            channel_type=channel_type,
            text=text,
            mentions=mentions,
        )
    )

_E4_EVIDENCE_FULL_TEXT = [
    ("im", "Chào buổi sáng cả nhà. Hôm nay có ai rảnh không?"),
    ("mpim", "Vừa pha xong cà phê. Ai muốn uống không?"),
    ("im", "Weather's quite nice this afternoon. Thinking of a short walk soon."),
    ("public_channel", "Bàn làm việc mới đến rồi. Trông khá đẹp đó."),
]
for channel_type, text in _E4_EVIDENCE_FULL_TEXT:
    cases.append(
        _case(
            "extract_evidence_fallback_full_text",
            "không câu nào khớp -> extract_evidence fallback lấy NGUYÊN text (khác extract_title chỉ lấy câu đầu)",
            channel_type=channel_type,
            text=text,
            mentions=True,
        )
    )

_E5_DEADLINE_PHRASE = [
    ("im", "Vui lòng chuẩn bị tài liệu. Hạn chót là thứ Sáu tuần này. Cảm ơn.", True, True),
    ("mpim", "Please prepare the documents. The deadline is next Friday. Thank you.", True, True),
    ("public_channel", "Vui lòng xác nhận giúp mình nhé.", True, False),
    ("im", "Please confirm your attendance soon.", True, False),
]
for channel_type, text, mentions, _has_deadline in _E5_DEADLINE_PHRASE:
    cases.append(
        _case(
            "extract_deadline_phrase",
            "extract_deadline_phrase chỉ trả câu khớp DEADLINE_RE riêng; câu chỉ có action thì trả rỗng",
            channel_type=channel_type,
            text=text,
            mentions=mentions,
        )
    )

# ---------------------------------------------------------------------------
# F. RuleConfig override — threshold/weight configurable (6 case)
# ---------------------------------------------------------------------------

cases.append(
    _case(
        "config_override",
        "action_score=1000 (mặc định 25) biến message REVIEW mặc định thành KEEP",
        channel_type="public_channel",
        text="Please review the notes.",
        config_overrides={"action_score": 1000},
    )
)
cases.append(
    _case(
        "config_override",
        "newsletter_or_automated_score=0 (mặc định -40) gỡ penalty, message DROP mặc định thành KEEP",
        channel_type="public_channel",
        text="no-reply: please submit your report by Friday for the automated review.",
        config_overrides={"newsletter_or_automated_score": 0},
    )
)
cases.append(
    _case(
        "config_override",
        "review_threshold=100 (mặc định 15) biến message REVIEW mặc định (score=25) thành DROP",
        channel_type="public_channel",
        text="Please submit the form.",
        config_overrides={"review_threshold": 100},
    )
)
cases.append(
    _case(
        "config_override",
        "pinned_score=50 (mặc định 10) biến message DROP mặc định (chỉ pinned=10) thành KEEP",
        channel_type="public_channel",
        text="Bức ảnh đẹp quá.",
        is_pinned=True,
        config_overrides={"pinned_score": 50},
    )
)
cases.append(
    _case(
        "config_override",
        "mentioned_current_user_score=5 (mặc định 30) biến message REVIEW mặc định (chỉ mention=30) thành DROP",
        channel_type="public_channel",
        text="Ghi chú linh tinh không có gì đặc biệt.",
        mentions=True,
        config_overrides={"mentioned_current_user_score": 5},
    )
)
cases.append(
    _case(
        "config_override",
        "direct_message_score=0 (mặc định 15) biến message REVIEW mặc định (chỉ direct_message=15) thành DROP",
        channel_type="im",
        text="Chúc bạn cuối tuần vui vẻ nhé.",
        config_overrides={"direct_message_score": 0},
    )
)

# ---------------------------------------------------------------------------
# Gán id tuần tự SLK-001..SLK-{n} rồi ghi file
# ---------------------------------------------------------------------------

for idx, case in enumerate(cases, start=1):
    case["id"] = f"SLK-{idx:03d}"
    case_ordered = {
        "id": case["id"],
        "group": case["group"],
        "description": case["description"],
        "input": case["input"],
        "expected": case["expected"],
    }
    cases[idx - 1] = case_ordered

_OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Đã ghi {len(cases)} case vào {_OUT}")

from collections import Counter  # noqa: E402

group_counts = Counter(c["group"] for c in cases)
decision_counts = Counter(c["expected"]["decision"] for c in cases)
print("\nSố case theo nhóm:")
for group, count in group_counts.items():
    print(f"  {group:<40} {count}")
print("\nPhân bố decision:")
for decision, count in decision_counts.items():
    print(f"  {decision:<10} {count}")
