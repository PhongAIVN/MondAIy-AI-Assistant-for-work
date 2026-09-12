from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class WorkerHeartbeat(Base):
    """1 dòng = nhịp đập của 1 vòng nền trong `src/worker.py`.

    Vì sao phải qua DB chứ không dùng thẳng Counter của prometheus_client:
    worker chạy ở container riêng và không mở cổng HTTP (xem docker-compose),
    nên bộ đếm trong tiến trình đó không ai scrape được. API mới là nơi phục vụ
    `/metrics`, nên worker ghi vào Postgres và API đọc ra — đây là kênh duy
    nhất hai tiến trình cùng nhìn thấy.

    Kiểu hỏng cần bắt là "tiến trình còn sống nhưng vòng lặp đã chết": healthcheck
    container vẫn xanh trong khi không việc nào được xếp nữa. Chỉ `last_tick_at`
    mới lộ ra chuyện đó, nên nó được ghi ở MỌI vòng — kể cả vòng không làm gì và
    vòng vừa ném lỗi.
    """

    __tablename__ = "worker_heartbeats"
    __table_args__ = (UniqueConstraint("loop", name="uq_worker_heartbeat_loop"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Tên vòng lặp, trùng tên hàm trong worker.py để tra ngược cho nhanh.
    loop: Mapped[str] = mapped_column(String(64), index=True)
    last_tick_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # Nhịp gần nhất KHÔNG ném lỗi. Lệch xa dần khỏi `last_tick_at` nghĩa là vòng
    # vẫn quay nhưng hỏng liên tục — im lặng hơn hẳn một tiến trình chết hẳn.
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # BigInteger vì đây là bộ đếm cộng dồn suốt vòng đời cài đặt, không reset.
    tick_count: Mapped[int] = mapped_column(BigInteger, default=0)
    error_count: Mapped[int] = mapped_column(BigInteger, default=0)
    # Số việc vòng này thật sự tạo ra (run đã xếp, lịch đã làm mới...). Tách
    # khỏi tick_count để phân biệt "quét đều mà không có việc" với "không quét".
    processed_count: Mapped[int] = mapped_column(BigInteger, default=0)
    # CHỈ tên class exception, không bao giờ là message: message của lỗi
    # connector có thể chứa email hay nội dung tin nhắn, mà PRD §13 cấm đưa nội
    # dung gốc vào dữ liệu vận hành.
    last_error_class: Mapped[str | None] = mapped_column(String(128), default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
