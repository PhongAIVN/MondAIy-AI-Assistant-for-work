"""Nhận diện câu chat đang hỏi thẳng về công việc / việc cần làm.

Dùng cho `chat_sync.decide()`: câu hỏi kiểu "tôi có task gì" phải ép đồng bộ
lại nếu dữ liệu đã cũ, còn câu chat bình thường thì không.

Tất định, không gọi LLM: quyết định này chạy trên MỌI câu chat, gọi mô hình chỉ
để phân loại một câu là vừa chậm vừa tốn, và một lần đoán sai chỉ khiến người
dùng thấy dữ liệu hơi cũ — không đáng đánh đổi.

Theo đúng quy ước đã lập cho `filter_classify.py`: nhóm theo ngôn ngữ, không
dùng từ trần mơ hồ. Ở đây "từ trần" nguy hiểm theo chiều ngược lại — "task" hay
"việc" đứng một mình có mặt trong vô số câu không phải câu hỏi ("tạo task cho
tôi", "việc này khó quá"), nên phải có cả DANH TỪ chỉ công việc lẫn dấu hiệu
HỎI/LIỆT KÊ thì mới tính.
"""

from __future__ import annotations

import re
import unicodedata

# Danh từ chỉ "việc cần làm" — cộng cả nguồn dữ liệu việc (lịch, Gmail, Jira,
# đồng bộ) vì hỏi "lịch tuần này thế nào"/"đồng bộ Gmail xem có gì mới" cũng
# cần dữ liệu tươi y hệt hỏi task, dùng chung một cổng cho gọn.
_WORK_NOUNS = (
    # -- en --
    "task",
    "todo",
    "to-do",
    "to do",
    "assignment",
    "deadline",
    "due",
    "action item",
    "calendar",
    "schedule",
    "gmail",
    "email",
    "jira",
    "sync",
    # -- vi --
    "viec",
    "cong viec",
    "deadline",
    "han",
    "nhiem vu",
    "bai tap",
    "lich",
    "gmail",
    "jira",
    "dong bo",
    # -- ja / zh / ko --
    "タスク",
    "やること",
    "予定",
    "締切",
    "任务",
    "待办",
    "截止",
    "업무",
    "할 일",
    "마감",
    # -- es / fr / de --
    "tarea",
    "pendiente",
    "tache",
    "aufgabe",
    "frist",
)

# Dấu hiệu đang HỎI hoặc yêu cầu LIỆT KÊ.
_QUERY_MARKERS = (
    # -- en --
    "what",
    "which",
    "any",
    "do i have",
    "show me",
    "list",
    "anything",
    # -- vi --
    "gi",
    "nao",
    "co khong",
    "khong",
    "liet ke",
    "cho toi xem",
    "xem",
    "dang co",
    # -- ja / zh / ko --
    "ありますか",
    "教えて",
    "何",
    "有什么",
    "有哪些",
    "列出",
    "뭐",
    "무엇",
    "알려",
    # -- es / fr / de --
    "que",
    "cuales",
    "quelles",
    "welche",
    "zeig",
)


def _fold(value: str) -> str:
    """Cùng phép chuẩn hoá với filter_classify: NFKD, bỏ dấu, đ -> d, casefold.

    Chữ Nhật/Trung/Hàn bị NFKD tách dấu đục (ド -> ト) nên TỪ KHOÁ cũng phải đi
    qua đúng hàm này trước khi so — xem `_folded` bên dưới. Viết từ khoá ở dạng
    tổ hợp sẵn rồi so thẳng là lỗi đã gặp một lần ở filter_classify.
    """
    normalized = unicodedata.normalize("NFKD", value).replace("đ", "d").replace("Đ", "d")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


_FOLDED_WORK_NOUNS = tuple(_fold(term) for term in _WORK_NOUNS)
_FOLDED_QUERY_MARKERS = tuple(_fold(term) for term in _QUERY_MARKERS)

# Động từ RA LỆNH tạo/sửa việc. Có mặt là câu sai khiến, không phải câu hỏi
# "đang có gì" — "tạo task nhắc tôi họp lúc 3h" có đủ danh từ "task" lẫn chữ
# "nhắc" nhưng người dùng đang bảo tạo mới, kéo đồng bộ ở đây là vô nghĩa.
_COMMAND_VERBS = (
    # -- en --
    "create ",
    "add ",
    "make a task",
    "set a reminder",
    "remind me to",
    "schedule ",
    # -- vi --
    "tao task",
    "tao viec",
    "tao nhac",
    "them task",
    "them viec",
    "lap task",
    "nhac toi",
    "dat lich",
    # -- ja / zh / ko --
    "作成して",
    "追加して",
    "创建",
    "添加",
    "만들어",
    "추가해",
)

_FOLDED_COMMAND_VERBS = tuple(_fold(term) for term in _COMMAND_VERBS)


# Câu hỏi hay kết thúc bằng dấu hỏi — tính là dấu hiệu hỏi, kể cả dấu toàn rộng
# của tiếng Nhật/Trung.
_QUESTION_MARK = re.compile(r"[?？]")


def asks_about_work(message: str) -> bool:
    """True khi câu chat đang hỏi về việc cần làm của chính người dùng.

    Cần ĐỒNG THỜI một danh từ chỉ công việc và một dấu hiệu hỏi/liệt kê. Chỉ
    một trong hai là chưa đủ: "tạo task nhắc tôi họp" có "task" nhưng là câu ra
    lệnh tạo mới, không phải hỏi xem đang có gì.
    """
    if not message or not message.strip():
        return False
    folded = _fold(message)
    if not any(noun in folded for noun in _FOLDED_WORK_NOUNS):
        return False
    # Câu ra lệnh tạo việc bị phủ quyết TRƯỚC, kể cả khi có dấu hỏi: "tạo task
    # nhắc tôi họp lúc 3h?" vẫn là lệnh tạo.
    if any(verb in folded for verb in _FOLDED_COMMAND_VERBS):
        return False
    return bool(_QUESTION_MARK.search(message)) or any(
        marker in folded for marker in _FOLDED_QUERY_MARKERS
    )
