from datetime import UTC, datetime
from typing import Literal, get_args

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base

# Ba vai trò khớp đúng UserRole của frontend (client/web-app/src/stores/useAuthStore.ts).
# Lệch tên một chữ là ProtectedRoute chặn nhầm người, nên đổi ở đây phải đổi cả bên kia.
UserRole = Literal["participant", "mentor", "admin"]
USER_ROLES: tuple[str, ...] = get_args(UserRole)

DEFAULT_ROLE = "participant"


class User(Base):
    """1 dòng = 1 tài khoản đăng ký thật (email + password hash)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # `sub` là định danh ổn định duy nhất của Apple; không dùng email relay
    # làm khóa vì Apple có thể không gửi email ở những lần đăng nhập sau.
    apple_subject: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, default=None)
    # Refresh token Apple được mã hoá để server có thể revoke khi xoá tài khoản.
    apple_refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    # NULL hoặc sentinel cho tài khoản Google-only chưa từng đặt mật khẩu —
    # login bằng password luôn từ chối chung chung (xem services/auth.py).
    password_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    # Tên hiển thị do người dùng tự đặt. Trước đây chỉ nằm ở localStorage của
    # trình duyệt nên đổi máy là mất, và admin không thấy được ai là ai.
    display_name: Mapped[str] = mapped_column(String(120), default="")
    # Ảnh đại diện lấy từ Google OpenID userinfo khi người dùng kết nối Gmail.
    # Chỉ lưu URL public, tuyệt đối không lưu binary hoặc access token tại đây.
    avatar_url: Mapped[str | None] = mapped_column(String(2048), default=None)
    # Quyền thật, quyết định ở server. Trước đây role nằm trong localStorage nên
    # bất kỳ ai cũng tự đặt mình thành admin được — /admin không hề được bảo vệ.
    role: Mapped[str] = mapped_column(String(16), default=DEFAULT_ROLE, index=True)
    # A: verified program member; B: Discord connected but not matched to crawl;
    # C: no program access, personal features only.
    program_access_level: Mapped[str] = mapped_column(String(1), default="C", index=True)
    # Cohort do admin gán; nếu NULL thì dùng cohort pilot trong settings.
    program_cohort_slug: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    # Khoá tài khoản mà không xoá, để giữ lại bằng chứng trong audit log.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Cho phép scheduler nền tự tạo Run cho user này (xem src/services/auto_sync.py).
    # Đây là công tắc TỪNG NGƯỜI, độc lập với công tắc tổng settings.auto_sync_enabled;
    # phải bật cả hai thì mới có run tự động. Tắt cột này là cách người dùng
    # rút lại đồng ý mà không cần ngắt kết nối nguồn nào.
    auto_sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    llm_quota_day: Mapped[str | None] = mapped_column(String(10), default=None)
    llm_questions_used: Mapped[int] = mapped_column(Integer, default=0)
    # Extra questions earned from substantive product feedback. The allowance
    # is reset together with the daily counter; keeping it separate means a
    # reward always adds exactly N questions even when it is granted early.
    llm_bonus_questions: Mapped[int] = mapped_column(Integer, default=0)
    # Hash (sha256) của token đặt lại mật khẩu đang hiệu lực, không phải
    # plaintext — ai đọc được DB cũng không tự đặt lại mật khẩu người khác.
    # NULL = không có yêu cầu reset nào đang chờ.
    reset_token_hash: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Đếm số lần bấm "quên mật khẩu" trong 1 cửa sổ thời gian (per-user, không
    # phải theo IP) — vượt ngưỡng thì khoá tạm reset_locked_until, xem
    # src/api/auth.py::forgot_password.
    reset_request_count: Mapped[int] = mapped_column(Integer, default=0)
    reset_request_window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    reset_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Mỗi user thường chỉ được một lần tóm tắt meeting mỗi ngày.
    meeting_summary_quota_day: Mapped[str | None] = mapped_column(String(10), default=None)
    meeting_summaries_used: Mapped[int] = mapped_column(Integer, default=0)
    # Số lần quality gate từ chối feedback trong ngày hiện tại.
    feedback_attempts: Mapped[int] = mapped_column(Integer, default=0)
    feedback_quality_day: Mapped[str | None] = mapped_column(String(10), default=None)
    # Giữ lại để tương thích dữ liệu cũ; feedback quality không còn dùng cooldown.
    feedback_cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
