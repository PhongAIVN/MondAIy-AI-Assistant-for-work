"""Bộ dữ liệu vàng đo tầng định tuyến XÁC ĐỊNH (`plan_tool_calls`).

Vì sao cần: định tuyến hiện dựa vào 23 regex trên text đã bỏ dấu, cộng một loạt
luật vá. Không có bộ đo thì không ai trả lời được câu quan trọng nhất khi muốn
dọn hoặc thay nó: *bỏ một regex thì độ chính xác tụt bao nhiêu?* Mọi thay đổi
router đều thành đoán mò.

Phạm vi: đo ĐÚNG tầng xác định, bằng cách truyền `tool_calls=[]` — tức "model
chưa đề xuất gì". Không gọi LLM: bộ đo phải chạy được trong CI, không tốn tiền,
không phụ thuộc mạng, và cho cùng kết quả ở mọi lần chạy. Việc LLM chọn tool tốt
đến đâu là một câu hỏi khác, cần một bộ đo khác.

Cách dùng khi sửa router: chạy `pytest tests/eval/ -v`. Số liệu in ra ở cuối cho
biết độ chính xác trước/sau. Sửa mà số tụt là hồi quy, dù mọi test khác còn xanh.

`status`:
  "locked"  — hành vi đúng, đã khoá. Tụt là hồi quy.
  "gap"     — hành vi SAI đang tồn tại trên production, đã biết, chưa sửa.
              Không làm đỏ CI, nhưng được đếm và in ra. Sửa được thì đổi sang
              "locked" trong cùng PR để nó khỏi tụt lại.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldCase:
    query: str
    # Đạt khi CÓ ÍT NHẤT MỘT tool trong tập này. Dùng tập thay vì một tên vì
    # nhiều câu có hơn một cách route đúng — ép đúng một tên là khoá cứng chi
    # tiết cài đặt, và bộ đo sẽ đỏ mỗi lần đổi tên tool.
    expect_any_of: frozenset[str]
    # Tool KHÔNG được xuất hiện. Đây là nửa quan trọng hơn: bung sang nguồn
    # không liên quan chính là thứ làm ngập ngân sách ngữ cảnh và đẩy nguồn
    # đúng ra khỏi câu trả lời.
    expect_none_of: frozenset[str] = field(default_factory=frozenset)
    note: str = ""
    status: str = "locked"

    def __str__(self) -> str:  # pragma: no cover - chỉ để đọc log
        return self.query


CALENDAR = "calendar_search_events"
GMAIL_SWEEP = "gmail_deadline_sweep"
JIRA = "jira_search_issues"
DISCORD = "discord_search_program"
TASKS = "list_tasks"
WEB = "web_search"
PROGRAM = "program_information_search"


GOLD_CASES: tuple[GoldCase, ...] = (
    # ---- Lịch: hỏi thẳng về thời gian biểu ----
    GoldCase("mai có lịch gì", frozenset({CALENDAR}), frozenset({JIRA, GMAIL_SWEEP})),
    GoldCase("mai co lich gi", frozenset({CALENDAR}), frozenset({JIRA}), "không dấu"),
    GoldCase("lich hop tuan sau", frozenset({CALENDAR}), frozenset({JIRA}), "không dấu"),
    GoldCase(
        "tuần này có họp gì không",
        frozenset({CALENDAR}),
        frozenset({JIRA}),
        note="'mai có lịch gì' đạt nhưng câu này trượt — regex bắt 'lịch', không bắt 'họp'",
        status="gap",
    ),
    GoldCase(
        "chiều nay tôi rảnh lúc nào",
        frozenset({CALENDAR}),
        frozenset({JIRA}),
        note="hỏi lịch rảnh mà không dùng từ 'lịch' nên không luật nào bắt",
        status="gap",
    ),
    # ---- Gmail ----
    GoldCase("email nào cần trả lời", frozenset({GMAIL_SWEEP}), frozenset({JIRA})),
    GoldCase("mail nao can tra loi", frozenset({GMAIL_SWEEP}), frozenset({JIRA}), "không dấu"),
    GoldCase("có mail nào sắp tới hạn không", frozenset({GMAIL_SWEEP})),
    # ---- Jira ----
    GoldCase(
        "TAPB-130 đang ở trạng thái nào",
        frozenset({JIRA}),
        frozenset({CALENDAR}),
        note=(
            "Có mã issue rõ ràng mà vẫn không route sang Jira. _jira_search_terms "
            "biết trích ISSUE-KEY, nhưng luật route lại đòi từ khoá 'jira' trong câu."
        ),
        status="gap",
    ),
    GoldCase("issue jira nào của tôi quá hạn", frozenset({JIRA})),
    # ---- Tổng hợp ngày: bung nhiều nguồn LÀ ĐÚNG ----
    GoldCase(
        "hôm nay tôi cần làm gì",
        frozenset({TASKS, CALENDAR}),
        note="câu agenda — quét rộng là đúng",
    ),
    GoldCase("hom nay toi can lam gi", frozenset({TASKS, CALENDAR}), note="không dấu"),
    GoldCase("tuần này có gì cần chú ý", frozenset({TASKS, CALENDAR})),
    # ---- Câu hỏi kiến thức: KHÔNG được quét nguồn cá nhân ----
    GoldCase(
        "AI thực chiến là gì",
        frozenset({WEB, PROGRAM}),
        frozenset({JIRA, GMAIL_SWEEP, CALENDAR}),
        note=(
            "Hỏi định nghĩa một chương trình. Tầng xác định hiện KHÔNG route đi "
            "đâu cả — trả về rỗng. Trước đây tôi báo với chủ dự án là "
            "_prefer_web_search đã lo câu này; đo lại thì sai."
        ),
        status="gap",
    ),
    GoldCase(
        "LangGraph là gì",
        frozenset({WEB}),
        frozenset({JIRA, GMAIL_SWEEP, CALENDAR}),
        note="kiến thức chung, không dính dữ liệu cá nhân",
        status="gap",
    ),
    # ---- Ca đã gây lỗi thật trên production ----
    GoldCase(
        "trước khi họp mentor duty cần làm gì",
        frozenset({CALENDAR}),
        note=(
            "Câu thật của chủ dự án. Calendar PHẢI có mặt — nó là nguồn duy nhất "
            "biết 'Mentor Duty 29/08 20:00'. Câu này cũng khớp luật agenda nên "
            "bung sang năm nguồn; xem note trong PR về chuyện Jira query rỗng."
        ),
    ),
    GoldCase(
        "chuẩn bị gì cho buổi họp với mentor",
        frozenset({CALENDAR}),
        note=(
            "Cùng ý định với ca ngay trên, chỉ khác cách nói — và trượt. Đây là "
            "bằng chứng gọn nhất cho tính giòn của regex: 'trước khi họp' khớp "
            "luật agenda, 'chuẩn bị gì cho buổi họp' thì không."
        ),
        status="gap",
    ),
    # ---- Nói vòng / gõ sai ----
    GoldCase("tôi quên mất mai phải làm gì rồi", frozenset({TASKS, CALENDAR}), note="nói vòng"),
    GoldCase(
        "mai co viec j ko",
        frozenset({TASKS, CALENDAR}),
        note="viết tắt kiểu chat ('j' = 'gì', 'ko' = 'không') — không luật nào bắt",
        status="gap",
    ),
    # ---- Yêu cầu TẠO: không được biến thành câu tra nguồn ----
    GoldCase(
        "nhắc tôi 01/09 23:59 nộp dự án P004",
        frozenset(),
        frozenset({JIRA, GMAIL_SWEEP, DISCORD}),
        note=(
            "Ca thật Thái gặp 27/08. Source routing thấy 'P004' là tên dự án rồi "
            "hỏi 'bạn muốn lấy từ nguồn nào: Tasks, Jira, Gmail...?' — nhưng câu "
            "này không tra gì cả, người dùng đang ĐỌC CHO máy ghi. Họ phải gõ "
            "thêm 'tạo task í' mới xong việc."
        ),
    ),
    # ---- Chào hỏi: KHÔNG được tra nguồn nào ----
    GoldCase("hi", frozenset(), frozenset({JIRA, GMAIL_SWEEP, CALENDAR, DISCORD, TASKS}), "small talk"),
    GoldCase("cảm ơn nhé", frozenset(), frozenset({JIRA, GMAIL_SWEEP, CALENDAR, TASKS}), "small talk"),
)


def cases_by_status(status: str) -> tuple[GoldCase, ...]:
    return tuple(case for case in GOLD_CASES if case.status == status)
