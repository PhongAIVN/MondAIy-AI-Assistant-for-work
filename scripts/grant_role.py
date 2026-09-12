"""Đổi role của một tài khoản từ dòng lệnh — dùng để tạo admin đầu tiên.

API `/api/v1/admin/users/{id}` đòi người gọi đã là admin, nên trên một hệ thống
mới chưa ai là admin thì không có đường nào vào portal. Script này là cửa duy
nhất mở khoá tình huống đó, và vì thế nó chỉ chạy được từ máy có quyền vào DB.

    python scripts/grant_role.py an@example.com admin
    python scripts/grant_role.py an@example.com participant

Mọi lần đổi đều ghi vào `audit_events` giống hệt khi đổi qua portal, để nhật ký
không có lỗ hổng "role tự nhiên đổi mà không ai làm gì".
"""

import sys
from pathlib import Path

# Chạy `python scripts/grant_role.py` thì Python đặt scripts/ lên sys.path chứ
# không phải gốc repo, nên `import src` hỏng. Thêm gốc repo vào trước khi import.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from src.db import SessionLocal  # noqa: E402
from src.models.user import USER_ROLES, User  # noqa: E402
from src.services.telemetry import emit_audit  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    email, role = argv[0].strip().lower(), argv[1].strip().lower()
    if role not in USER_ROLES:
        print(f"Role không hợp lệ: {role!r}. Chọn một trong {', '.join(USER_ROLES)}.")
        return 2

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            print(f"Không tìm thấy tài khoản {email}. Đăng ký trước rồi chạy lại.")
            return 1

        truoc = user.role
        if truoc == role:
            print(f"{email} đã là {role}, không đổi gì.")
            return 0

        user.role = role
        emit_audit(
            db,
            action="admin_user_updated",
            object_type="user",
            object_id=str(user.id),
            actor_type="cli",
            actor_id="scripts/grant_role.py",
            before={"role": truoc, "is_active": user.is_active},
            after={"role": role, "is_active": user.is_active},
        )
        db.commit()
        print(f"{email}: {truoc} -> {role}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
