from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class RecordingQuotaSlot(Base):
    """1 dòng = 1 lát thời gian ghi âm đã dùng của 1 người trong 1 ngày.

    Không lưu tổng số phút đã dùng vào một dòng duy nhất, vì hai kênh mic và tab
    của cùng một cuộc họp gửi chunk song song: cộng dồn kiểu đó sẽ tính đôi và
    người dùng mất một nửa hạn mức oan. Thay vào đó mỗi lát thời gian được ghi
    thành một dòng, khoá duy nhất theo `(user_id, note_id, offset_ms)` — kênh
    thứ hai của cùng lát rơi vào đúng khoá đó nên bị bỏ qua, và chunk gửi lại
    sau lỗi mạng cũng không bị tính thêm lần nữa.

    Hạn mức tính theo thời gian họp thật (wall-clock), không phải tổng thời
    lượng audio: họp 15 phút luôn tốn đúng 15 phút hạn mức dù thu mấy kênh.
    """

    __tablename__ = "recording_quota_slots"
    __table_args__ = (
        # Chống tính đôi: kênh thứ hai và lần gửi lại của cùng lát bị chặn ở đây.
        UniqueConstraint("user_id", "note_id", "offset_ms", name="uq_recording_slot"),
        # Truy vấn duy nhất của tính năng: tổng hạn mức đã dùng của 1 user trong 1 ngày.
        Index("ix_recording_quota_user_day", "user_id", "usage_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Lưu chuỗi cho khớp `meeting_notes.user_id`, cùng lý do đã ghi ở model đó.
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    # Ngày theo giờ Việt Nam chứ không phải UTC, xem `quota_day()` trong service.
    usage_date: Mapped[date] = mapped_column(Date)
    note_id: Mapped[int] = mapped_column(Integer)
    offset_ms: Mapped[int] = mapped_column(Integer)
    # Số mili giây lát này chiếm trong hạn mức. Tách thành cột thay vì hằng số để
    # đổi độ dài chunk sau này không làm sai lệch các dòng đã ghi.
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
