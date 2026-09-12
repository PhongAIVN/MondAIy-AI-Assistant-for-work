from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.api.rate_limit import limiter
from src.models.schemas import CamelModel
from src.services.llm import get_llm, response_text

router = APIRouter(prefix="/public-ask", tags=["public-ask"])

# Khớp đúng giới hạn hiển thị ở frontend (client/web-app/src/pages/marketing/TryChatPage.tsx):
# ba câu gợi ý + một câu tự nhập.
# Đây là chốt chặn thật — giới hạn phía client chỉ để UX, dễ bị vòng qua bằng cách gọi API trực tiếp.
MAX_USER_TURNS = 4

SYSTEM_PROMPT = """Bạn là trợ lý FAQ công khai của mondaiy — một trợ lý AI tổng hợp lịch, \
email, thông báo và việc cần làm từ các nguồn người dùng tự kết nối (Gmail, Google Calendar, \
Discord, Jira, Outlook), luôn dẫn nguồn cho câu trả lời và luôn cần người dùng xác nhận trước \
khi tạo hành động thật (task, nhắc việc, sự kiện). mondaiy không tự động ghi vào ứng dụng bên \
ngoài, không theo dõi màn hình hay lịch sử duyệt web.

Đây là bản demo công khai, người hỏi CHƯA đăng nhập nên không có dữ liệu cá nhân nào để tra cứu.
Nhiệm vụ của bạn CHỈ LÀ trả lời ngắn gọn (2-4 câu) các câu hỏi về bản thân mondaiy: mondaiy là \
gì, làm được gì, cách dùng cơ bản, các nguồn hỗ trợ, quyền riêng tư ở mức tổng quan.

Quy tắc bắt buộc:
- Không trả lời câu hỏi kiến thức chung, bài tập, code, hay bất kỳ chủ đề nào ngoài chính sản \
phẩm mondaiy. Nếu bị hỏi ngoài chủ đề, từ chối lịch sự và mời người hỏi đăng ký để trải nghiệm \
đầy đủ.
- Không bịa tính năng mondaiy chưa có, không hứa hẹn giá hay ngày ra mắt cụ thể nếu không chắc.
- Trả lời đúng ngôn ngữ người dùng đang dùng để hỏi.
- Có thể gợi ý người dùng đăng ký tài khoản để dùng đầy đủ tính năng."""


class PublicAskTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class PublicAskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[PublicAskTurn] = Field(default_factory=list, max_length=MAX_USER_TURNS * 2)


class PublicAskResponse(CamelModel):
    reply: str
    turns_used: int
    limit_reached: bool


@router.post("/messages", response_model=PublicAskResponse)
@limiter.limit("8/minute")
async def public_ask(payload: PublicAskRequest, request: Request) -> PublicAskResponse:
    turns_used = sum(1 for turn in payload.history if turn.role == "user") + 1
    if turns_used > MAX_USER_TURNS:
        raise HTTPException(status_code=429, detail="Public demo message limit reached")

    messages: list[SystemMessage | HumanMessage | AIMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    for turn in payload.history:
        if turn.role == "user":
            messages.append(HumanMessage(content=turn.content))
        else:
            messages.append(AIMessage(content=turn.content))
    messages.append(HumanMessage(content=payload.message))

    llm = get_llm(lane="small_talk")
    result = await llm.ainvoke(messages)
    reply = response_text(result)

    return PublicAskResponse(
        reply=reply,
        turns_used=turns_used,
        limit_reached=turns_used >= MAX_USER_TURNS,
    )
