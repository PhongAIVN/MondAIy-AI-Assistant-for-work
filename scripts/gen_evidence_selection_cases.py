"""Sinh >=100 case cho eval/golden_dataset/evidence_verification/evidence_selection_cases.json.
Chạy 1 lần để tạo file, không phải code production. Dùng chính regex thật
(ACTION_RE/DEADLINE_RE/URGENCY_RE) để verify filler bank không lỡ dính từ khóa
tín hiệu trước khi build case — tránh lặp lỗi đã gặp lúc viết tay 6 case đầu."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.filter_classify import ACTION_RE, DEADLINE_RE, URGENCY_RE  # noqa: E402

OUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "eval"
    / "golden_dataset"
    / "evidence_verification"
    / "evidence_selection_cases.json"
)

FILLER_EN = [
    "The office plants were watered on schedule again this week without any issues.",
    "Weather in the office stayed pleasant all week, nothing else worth noting here.",
    "Our team celebrated a colleague's work anniversary with cake in the break room.",
    "The printer on the third floor got new toner installed yesterday morning.",
    "Several people mentioned enjoying the new coffee machine in the kitchen area.",
    "The parking garage repainted its lines over the weekend without disruption.",
    "A new plant was added near the reception desk, brightening up the lobby.",
    "The building management sent a routine notice about elevator maintenance.",
    "Someone left a nice note thanking the cleaning staff for their hard work.",
    "The office wifi speed seems noticeably faster since the recent upgrade.",
    "The break room fridge got a fresh coat of paint over the holiday period.",
    "A few colleagues shared photos from a recent weekend team outing.",
    "The new ergonomic chairs arrived and were distributed across desks.",
    "Someone brought homemade cookies and left them near the water cooler.",
    "The lobby television now shows a rotating slideshow of company photos.",
]

FILLER_VI = [
    "Hôm nay trời khá đẹp và mọi người đều ổn.",
    "Cây cảnh trong văn phòng được tưới nước đều đặn mỗi tuần.",
    "Máy pha cà phê mới nhận được nhiều lời khen từ đồng nghiệp.",
    "Bàn ghế mới được thay đổi ở một số khu vực làm việc.",
    "Wifi văn phòng dạo này chạy nhanh hơn hẳn so với hồi đầu năm.",
    "Một vài đồng nghiệp chia sẻ ảnh chuyến dã ngoại cuối tuần vừa rồi.",
    "Tủ lạnh khu bếp chung vừa được sơn lại màu mới rất đẹp.",
    "Bảo vệ tòa nhà thông báo định kỳ về việc bảo trì thang máy.",
    "Có người để lại bánh quy tự làm gần khu vực máy nước uống.",
    "Sảnh chính giờ chiếu slideshow ảnh hoạt động công ty xoay vòng.",
]

for sentence in FILLER_EN + FILLER_VI:
    assert not ACTION_RE.search(sentence), f"filler dính ACTION_RE: {sentence}"
    assert not DEADLINE_RE.search(sentence), f"filler dính DEADLINE_RE: {sentence}"
    assert not URGENCY_RE.search(sentence), f"filler dính URGENCY_RE: {sentence}"

ACTION_VERBS_EN = ["submit", "send", "complete", "review", "confirm", "update", "reply", "respond", "register"]
OBJECTS_EN = [
    "the report",
    "the form",
    "the proposal",
    "the invoice",
    "the design doc",
    "the budget sheet",
    "the survey",
    "the slides",
    "the contract",
    "the timesheet",
]
DEADLINE_PHRASES_EN = [
    "before Friday",
    "by Monday",
    "before Tuesday",
    "until Thursday",
    "before Wednesday",
]
URGENCY_PHRASES_EN = [
    "This is urgent.",
    "This matter is urgent and important.",
    "Handle with immediate care.",
    "This needs immediate attention.",
]

ACTION_VERBS_VI = ["nộp", "phản hồi", "xác nhận", "hoàn thành", "duyệt"]
OBJECTS_VI = ["báo cáo", "biểu mẫu", "đề xuất", "hóa đơn", "bảng khảo sát"]
DEADLINE_PHRASES_VI = ["trước thứ Sáu", "trước thứ Hai", "trước thứ Ba", "trước thứ Tư", "trước thứ Năm"]


def _action_deadline_en(i: int) -> str:
    verb = ACTION_VERBS_EN[i % len(ACTION_VERBS_EN)]
    obj = OBJECTS_EN[i % len(OBJECTS_EN)]
    deadline = DEADLINE_PHRASES_EN[i % len(DEADLINE_PHRASES_EN)]
    return f"Please {verb} {obj} {deadline}."


def _action_deadline_vi(i: int) -> str:
    verb = ACTION_VERBS_VI[i % len(ACTION_VERBS_VI)]
    obj = OBJECTS_VI[i % len(OBJECTS_VI)]
    deadline = DEADLINE_PHRASES_VI[i % len(DEADLINE_PHRASES_VI)]
    return f"Vui lòng {verb} {obj} {deadline}."


def _pad_to_min_length(sentences: list[str], filler_bank: list[str], min_chars: int = 400) -> list[str]:
    result = list(sentences)
    idx = 0
    while sum(len(s) for s in result) + len(result) < min_chars:
        result.append(filler_bank[idx % len(filler_bank)])
        idx += 1
    return result


def build_unchanged_cases() -> list[dict]:
    short_texts_en = [
        "Hi team, quick heads up: the standup moved to 10am tomorrow.",
        "Thanks everyone for joining the call today.",
        "FYI, the office will be closed on the public holiday.",
        "Great job on the launch, congrats to the whole team!",
        "Just looping you in on this thread for visibility.",
        "Attaching the notes from our sync earlier.",
        "Welcome aboard! Excited to have you on the team.",
        "Here's a quick summary of what we discussed.",
        "Let me know if you have any questions about this.",
        "Sharing this update for your awareness.",
        "Hope you had a great weekend!",
        "This is a short confirmation email for your records.",
        "See you at the meeting later this afternoon.",
        "Just a quick note before I head out for the day.",
        "Appreciate your patience while we sort this out.",
    ]
    short_texts_vi = [
        "Chào cả nhà, cuộc họp sáng mai dời sang 10 giờ.",
        "Cảm ơn mọi người đã tham gia buổi họp hôm nay.",
        "Thông báo văn phòng nghỉ vào ngày lễ sắp tới.",
        "Chúc mừng cả team đã hoàn thành dự án tốt đẹp.",
        "Gửi mọi người tham khảo file đính kèm nhé.",
        "Chia sẻ ghi chú cuộc họp sáng nay.",
        "Chào mừng bạn mới gia nhập đội ngũ.",
        "Đây là bản tóm tắt ngắn buổi thảo luận.",
        "Có gì thắc mắc cứ nhắn lại cho mình nhé.",
        "Chúc mọi người cuối tuần vui vẻ.",
    ]
    cases = []
    for i, text in enumerate(short_texts_en, start=1):
        assert len(text) < 400
        cases.append(
            {
                "id": f"EVD-{i:03d}",
                "description": f"Email ngắn tiếng Anh #{i} giữ nguyên toàn bộ, không cắt",
                "input": {"text": text},
                "expected": {"unchanged": True},
            }
        )
    offset = len(short_texts_en)
    for i, text in enumerate(short_texts_vi, start=1):
        assert len(text) < 400
        cases.append(
            {
                "id": f"EVD-{offset + i:03d}",
                "description": f"Email ngắn tiếng Việt #{i} giữ nguyên toàn bộ, không cắt",
                "input": {"text": text},
                "expected": {"unchanged": True},
            }
        )
    return cases


def build_single_signal_cases(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        case_id = start_id + i
        if i % 3 == 2:
            signal = URGENCY_PHRASES_EN[i % len(URGENCY_PHRASES_EN)]
            lang = "en-urgency"
        elif i % 2 == 0:
            signal = _action_deadline_en(i)
            lang = "en-action-deadline"
        else:
            signal = _action_deadline_vi(i)
            lang = "vi-action-deadline"
        filler_bank = FILLER_VI if lang.startswith("vi") else FILLER_EN
        sentences = _pad_to_min_length([signal], filler_bank)
        # Xen filler trước/sau để câu tín hiệu không luôn nằm ở đầu — vẫn phải
        # đủ 400 ký tự sau khi chèn.
        half = len(sentences) // 2
        arranged = sentences[1 : half + 1] + [signal] + sentences[half + 1 :]
        text = " ".join(arranged)
        assert len(text) >= 400, f"case {case_id} chưa đủ 400 ký tự: {len(text)}"
        filler_snippet = filler_bank[0][:30]
        cases.append(
            {
                "id": f"EVD-{case_id:03d}",
                "description": f"Email dài ({lang}) #{i + 1}, 1 câu tín hiệu giữa filler -> chọn đúng câu đó, loại filler",
                "input": {"text": text},
                "expected": {
                    "max_sentences": 1,
                    "contains": [signal],
                    "excludes": [filler_snippet],
                },
            }
        )
    return cases


def build_multi_signal_cases(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        case_id = start_id + i
        lang_vi = i % 4 == 3
        if lang_vi:
            strong = _action_deadline_vi(i)
            weak = URGENCY_PHRASES_EN[i % len(URGENCY_PHRASES_EN)]  # điểm thấp hơn (chỉ urgency=1)
            filler_bank = FILLER_VI
        else:
            strong = _action_deadline_en(i)  # action(2)+deadline(2)=4 điểm
            weak = URGENCY_PHRASES_EN[i % len(URGENCY_PHRASES_EN)]  # urgency=1 điểm
            filler_bank = FILLER_EN
        weakest = filler_bank[i % len(filler_bank)]  # 0 điểm — chắc chắn bị loại khi max=2
        sentences = _pad_to_min_length([strong, weak], filler_bank)
        arranged = [sentences[2]] + [strong] + sentences[3:5] + [weak] + sentences[5:]
        text = " ".join(arranged)
        assert len(text) >= 400, f"case {case_id} chưa đủ 400 ký tự: {len(text)}"
        cases.append(
            {
                "id": f"EVD-{case_id:03d}",
                "description": f"Email dài #{i + 1} có 2 câu tín hiệu mạnh/yếu + filler, max_sentences=2 -> giữ đúng 2 câu điểm cao nhất",
                "input": {"text": text},
                "expected": {
                    "max_sentences": 2,
                    "contains": [strong, weak],
                    "excludes": [weakest],
                },
            }
        )
    return cases


def build_no_signal_cases(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        case_id = start_id + i
        filler_bank = FILLER_VI if i % 2 else FILLER_EN
        sentence = filler_bank[i % len(filler_bank)]
        text = " ".join([sentence] * 12)
        assert len(text) >= 400, f"case {case_id} chưa đủ 400 ký tự: {len(text)}"
        cases.append(
            {
                "id": f"EVD-{case_id:03d}",
                "description": f"Email dài #{i + 1} toàn câu filler, không tín hiệu nào -> không crash",
                "input": {"text": text},
                "expected": {"no_crash": True, "max_selected_sentence_count": 6},
            }
        )
    return cases


def build_order_preserving_cases(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        case_id = start_id + i
        lang_vi = i % 3 == 2
        if lang_vi:
            first = _action_deadline_vi(i)
            last = URGENCY_PHRASES_EN[i % len(URGENCY_PHRASES_EN)]
            filler_bank = FILLER_VI
        else:
            first = _action_deadline_en(i)
            last = URGENCY_PHRASES_EN[(i + 1) % len(URGENCY_PHRASES_EN)]
            filler_bank = FILLER_EN
        middle = _pad_to_min_length([], filler_bank)
        text = " ".join([first] + middle + [last])
        assert len(text) >= 400, f"case {case_id} chưa đủ 400 ký tự: {len(text)}"
        cases.append(
            {
                "id": f"EVD-{case_id:03d}",
                "description": f"Email dài #{i + 1}, câu tín hiệu ở đầu và cuối -> giữ đúng thứ tự gốc",
                "input": {"text": text},
                "expected": {
                    "max_sentences": 2,
                    "contains": [first, last],
                    "order": [first, last],
                },
            }
        )
    return cases


def main() -> None:
    cases: list[dict] = []
    cases += build_unchanged_cases()  # 25
    next_id = len(cases) + 1
    single = build_single_signal_cases(next_id, 30)
    cases += single
    next_id += 30
    multi = build_multi_signal_cases(next_id, 25)
    cases += multi
    next_id += 25
    no_signal = build_no_signal_cases(next_id, 10)
    cases += no_signal
    next_id += 10
    order = build_order_preserving_cases(next_id, 10)
    cases += order

    assert len(cases) >= 100, f"chỉ có {len(cases)} case"
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "id trùng"

    OUT_PATH.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUT_PATH}")


if __name__ == "__main__":
    main()
