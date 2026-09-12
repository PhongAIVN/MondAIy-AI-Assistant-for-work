from typing import Literal

from pydantic import BaseModel, Field

ActionType = Literal["direct_action", "commitment", "conditional_action", "waiting", "prohibition"]
WorkStatus = Literal["open", "waiting", "blocked", "cancelled", "completed"]


class ExtractedSignal(BaseModel):
    """1 tín hiệu việc-cần-làm rút ra từ 1 message trong batch."""

    message_id: str = Field(description="external id của message tương ứng, phải khớp đúng id đã cho trong batch")
    title: str = Field(description="Tiêu đề việc cần làm, ngắn gọn")
    assignee_hint: str = Field(default="", description="Ai được giao, nếu tin có nhắc tới — để trống nếu không rõ")
    time_expression: str = Field(
        default="", description="Câu chữ NGUYÊN VĂN mô tả thời hạn, không tự chuyển đổi ngày giờ"
    )
    evidence_quote: str = Field(description="Trích NGUYÊN VĂN câu chứa tín hiệu việc cần làm, không diễn giải lại")
    summary: str = Field(
        default="",
        description=(
            "Tóm tắt 1-3 câu bằng lời của bạn, MỞ ĐẦU bằng mail đến từ ai gửi cho ai (dựa dòng "
            "[Từ:]/[Đến:] trong evidence), sau đó nội dung việc cần làm, dựa trên message gốc — "
            "khác evidence_quote (evidence_quote phải nguyên văn, summary được diễn giải lại cho dễ đọc)"
        ),
    )
    confidence: float = Field(ge=0.0, le=1.0)
    action_type: ActionType = "direct_action"
    requires_user_action: bool = True
    condition: str = ""
    status: WorkStatus = "open"
    certainty: Literal["confirmed", "inferred", "uncertain"] = "confirmed"


class BatchExtraction(BaseModel):
    items: list[ExtractedSignal] = Field(
        default_factory=list,
        description="Chỉ liệt kê message có tín hiệu việc-cần-làm rõ ràng, bỏ qua các message còn lại",
    )
