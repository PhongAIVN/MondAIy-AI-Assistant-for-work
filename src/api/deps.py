from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.user import User
from src.services import auth as auth_service


def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Thiếu Authorization Bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Access token rỗng.")

    try:
        user_id = auth_service.decode_token(token, "access")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return str(user_id)


def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    """Lấy bản ghi User thật thay vì chỉ id, để kiểm tra được role và trạng thái khoá.

    Token còn hạn không có nghĩa tài khoản còn quyền: quản trị viên có thể đã hạ
    role hoặc khoá tài khoản sau khi token được cấp. Đọc lại từ DB mỗi request là
    cách duy nhất để thu hồi quyền có hiệu lực ngay mà không cần blacklist token.
    """
    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User không tồn tại.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khoá.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Chặn mọi endpoint quản trị ở tầng server.

    Frontend cũng chặn `/admin` bằng ProtectedRoute nhưng đó chỉ là điều hướng —
    ai gọi thẳng API vẫn qua được. Quyền phải kiểm ở đây mới tính.
    """
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Endpoint này chỉ dành cho quản trị viên.")
    return user
