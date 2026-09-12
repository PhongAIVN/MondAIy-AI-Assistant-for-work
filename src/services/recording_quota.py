"""Hạn mức ghi âm cuộc họp theo ngày cho từng người dùng.

Quản trị viên không bị giới hạn; mọi tài khoản còn lại dùng chung một hạn mức
cấu hình ở `recording_quota_daily_minutes`. Hạn mức đo bằng thời gian họp thật
chứ không phải tổng thời lượng audio — chi tiết ở docstring của
`RecordingQuotaSlot`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.recording_quota import RecordingQuotaSlot
from src.models.user import User

# Hạn mức reset lúc nửa đêm giờ Việt Nam, không phải nửa đêm UTC. Dùng UTC thì
# hạn mức của người dùng reset lúc 7 giờ sáng — giữa buổi làm việc, và một cuộc
# họp buổi chiều sẽ bị cắt đôi giữa hai ngày hạn mức.
QUOTA_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class QuotaStatus:
    """Ảnh chụp hạn mức của một người tại một thời điểm."""

    limit_ms: int
    used_ms: int
    unlimited: bool

    @property
    def remaining_ms(self) -> int:
        """Số mili giây còn lại, không bao giờ âm để tầng hiển thị khỏi phải kẹp."""
        if self.unlimited:
            return self.limit_ms
        return max(0, self.limit_ms - self.used_ms)

    @property
    def exhausted(self) -> bool:
        """Đã hết hạn mức hay chưa. Tài khoản không giới hạn thì không bao giờ hết."""
        return not self.unlimited and self.used_ms >= self.limit_ms


def quota_day(now: datetime | None = None) -> date:
    """Trả về ngày hạn mức theo giờ Việt Nam.

    Nhận `now` để test đẩy được mốc thời gian mà không phải vá đồng hồ hệ thống.
    Thời điểm truyền vào phải có múi giờ; thiếu múi giờ là lỗi lập trình nên để
    nó nổ ở đây thay vì âm thầm coi là UTC.
    """
    moment = now or datetime.now(QUOTA_TIMEZONE)
    if moment.tzinfo is None:
        raise ValueError("quota_day cần datetime có múi giờ.")
    return moment.astimezone(QUOTA_TIMEZONE).date()


def daily_limit_ms() -> int:
    """Hạn mức mỗi ngày tính bằng mili giây, đọc từ cấu hình."""
    return get_settings().recording_quota_daily_minutes * 60 * 1000


def slot_offset_ms(offset_ms: int, duration_ms: int) -> int:
    """Quy offset thô của một chunk về mốc đầu lát trên lưới hạn mức.

    Khoá chống tính đôi là `(user, note, offset_ms)`, nên hai kênh mic và tab
    chỉ triệt tiêu nhau khi gửi lên CÙNG một con số. Thực tế thì không: mỗi kênh
    có `setInterval` riêng và tự lấy `Date.now()` lúc cắt, nên cùng một lát họp
    ra 20003 và 20005 — khác khoá, và người dùng bị trừ hai lần cho một lát.
    Làm tròn xuống theo bước lưới xoá luôn phần lệch đó, và giữ đúng định nghĩa
    hạn mức là thời gian họp thật chứ không phải tổng thời lượng audio.

    Bước lưới không hợp lệ (0 hoặc âm) thì trả nguyên offset: thà đếm hơi rộng
    còn hơn chia cho 0 giữa một cuộc họp đang ghi.
    """
    if duration_ms <= 0:
        return max(0, offset_ms)
    return (max(0, offset_ms) // duration_ms) * duration_ms


def get_status(db: Session, user: User, day: date | None = None) -> QuotaStatus:
    """Đọc hạn mức đã dùng trong ngày của một người.

    Cơ chế: cộng `duration_ms` của mọi lát đã ghi trong ngày. Quản trị viên được
    trả về ngay với cờ `unlimited` mà không cần truy vấn, vì họ không sinh dòng
    hạn mức nào.
    """
    limit_ms = daily_limit_ms()
    if user.is_admin:
        return QuotaStatus(limit_ms=limit_ms, used_ms=0, unlimited=True)

    used = db.execute(
        select(func.coalesce(func.sum(RecordingQuotaSlot.duration_ms), 0)).where(
            RecordingQuotaSlot.user_id == str(user.id),
            RecordingQuotaSlot.usage_date == (day or quota_day()),
        )
    ).scalar_one()
    return QuotaStatus(limit_ms=limit_ms, used_ms=int(used), unlimited=False)


def consume_slot(
    db: Session,
    user: User,
    note_id: int,
    offset_ms: int,
    duration_ms: int,
    day: date | None = None,
) -> bool:
    """Ghi nhận một lát thời gian đã ghi âm, trả về True nếu lát đó là mới.

    Cơ chế: chèn một dòng và dựa vào ràng buộc duy nhất để chống tính đôi. Kênh
    thứ hai của cùng lát, hoặc lần gửi lại sau lỗi mạng, sẽ vi phạm ràng buộc và
    được nuốt lặng lẽ — trả về False để chỗ gọi biết không có gì bị trừ thêm.

    Quản trị viên không sinh dòng nào, vừa đúng nghĩa không giới hạn vừa tránh
    bảng phình ra vì dữ liệu không ai dùng đến.
    """
    if user.is_admin:
        return False

    slot = RecordingQuotaSlot(
        user_id=str(user.id),
        usage_date=day or quota_day(),
        note_id=note_id,
        offset_ms=offset_ms,
        duration_ms=duration_ms,
    )
    # Điểm lưu để lần chèn trùng không kéo theo phần transcript đã ghi cùng
    # transaction bị cuốn ngược khi rollback.
    nested = db.begin_nested()
    try:
        db.add(slot)
        nested.commit()
    except IntegrityError:
        nested.rollback()
        return False
    return True
