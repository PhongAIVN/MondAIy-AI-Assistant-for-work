from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """State schema cho LangGraph agent.

    Mỗi node đọc và ghi vào state này.
    total=False cho phép tất cả fields là optional.
    """

    query: str
    image_data: str
    context: str
    analysis: str
    response: str
    error: str
    metadata: dict
    # Facts profile dài hạn đã được tầng API tải theo user_id xác thực. Model
    # không được tự chọn user hay ghi trực tiếp vào trường này.
    user_profile: dict[str, str]
    # Draft của đúng lượt trước khi tool cần hỏi thêm trường bắt buộc. API chỉ
    # truyền tiếp khi assistant message gần nhất có trạng thái clarification.
    pending_productivity_action: dict
    # Tool calls do node `think` đề xuất cho vòng hiện tại. `action` chỉ thực
    # thi danh sách này; model không được gọi tool ngoài registry.
    pending_tool_calls: list[dict]
    # Kết quả tool đã được `observe` xác nhận, theo đúng thứ tự thực thi. Giữ
    # dạng có cấu trúc để vòng think sau biết tool/args nào đã chạy và tránh gọi
    # lặp vô ích.
    observations: list[dict]
    latest_observations: list[dict]
    tool_iterations: int
    # Các lượt trước trong cùng phiên chat, cũ đến mới, dạng
    # {"role": "user" | "assistant", "content": str}. Tầng gọi đã cắt bớt cho
    # vừa ngân sách token (PRD mục 12.5), node không cắt lại.
    history: list[dict]
    # Tóm tắt các lượt đã rơi khỏi cửa sổ nguyên văn của chính phiên này. Là bộ
    # nhớ ngắn hạn đã nén, không phải bằng chứng: mọi khẳng định về công việc
    # vẫn phải dựa vào kết quả công cụ.
    conversation_summary: str
    # Facts dài hạn đã truy hồi theo câu hỏi hiện tại, mỗi phần tử có `status`
    # và `source` để node biết cái nào mới là candidate. Tầng API tải theo
    # user_id đã xác thực; model không được chọn user hay ghi vào trường này.
    long_term_memories: list[dict]
