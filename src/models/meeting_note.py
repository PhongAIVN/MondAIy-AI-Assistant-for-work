from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class MeetingNote(Base):
    """1 dòng = 1 cuộc họp do người dùng tự ghi chú hoặc tự dán transcript.

    Đây KHÔNG phải nguồn dữ liệu mới theo ADR-002: nội dung do chính người dùng
    nhập tay vào ứng dụng, không có connector nào đi lấy về. Vẫn coi là dữ liệu
    không tin cậy khi đưa vào prompt (transcript có thể chứa injection).

    `status` chỉ có 2 giá trị: "open" (đang ghi, còn sửa được) và "summarized"
    (đã bấm kết thúc, AI đã trích action). Tách trạng thái ra thay vì suy từ
    `ended_at` để một cuộc họp kết thúc nhưng LLM lỗi không bị kẹt nửa vời.
    """

    __tablename__ = "meeting_notes"
    __table_args__ = (
        # Màn hình danh sách lấy cuộc họp của 1 user, mới nhất trước.
        Index("ix_meeting_notes_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # user_id lưu chuỗi vì get_current_user_id trả về chuỗi, và users.id là
    # INTEGER nên không đặt ForeignKey — cùng lý do đã ghi ở conversations.
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="Cuộc họp mới")
    # Ghi chú người dùng tự gõ trong lúc họp.
    notes: Mapped[str] = mapped_column(Text, default="")
    # Transcript dán vào từ công cụ khác. Tách khỏi `notes` vì độ tin cậy khác
    # nhau: ghi chú là lời của chính người dùng, transcript là lời người khác.
    transcript: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open")
    # Tóm tắt và các quyết định do LLM sinh sau khi bấm kết thúc.
    summary: Mapped[str] = mapped_column(Text, default="")
    decisions: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now,
    )


class MeetingActionItem(Base):
    """1 dòng = 1 việc cần làm AI trích ra từ 1 cuộc họp, chưa phải Task thật.

    Đây là bản nháp: chỉ khi người dùng bấm chấp nhận mới sinh ra `Task` và ghi
    id vào `task_id`. Giữ nguyên tắc FR-062 — không tự tạo việc, không tự đặt
    lịch trước khi người dùng xác nhận.
    """

    __tablename__ = "meeting_action_items"
    __table_args__ = (Index("ix_meeting_action_items_note_status", "meeting_note_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_note_id: Mapped[int] = mapped_column(
        ForeignKey("meeting_notes.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500))
    detail: Mapped[str] = mapped_column(Text, default="")
    assignee: Mapped[str | None] = mapped_column(String(255), default=None)
    # True khi cuộc họp không nói rõ ai làm — hiển thị "chưa rõ người phụ trách"
    # thay vì gán bừa cho người đang đăng nhập.
    assignee_ambiguous: Mapped[bool] = mapped_column(Boolean, default=True)
    # Nguyên văn cụm chỉ thời gian trong cuộc họp ("cuối tuần này", "thứ 5 15:00
    # ICT"). Giữ lại để người dùng đối chiếu khi due_at trống.
    time_expression: Mapped[str] = mapped_column(String(255), default="")
    # Chỉ có giá trị khi time_expression đủ ngày + giờ + timezone tường minh
    # (BR-05). Mơ hồ thì để None, không đoán.
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    # Trích nguyên văn từ notes/transcript — căn cứ để người dùng kiểm chứng.
    evidence_quote: Mapped[str] = mapped_column(Text, default="")
    # "suggested" | "accepted" | "dismissed".
    status: Mapped[str] = mapped_column(String(32), default="suggested")
    # id của Task được tạo khi người dùng chấp nhận; None nếu chưa chấp nhận.
    task_id: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
