from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from src.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    if not settings.token_encryption_key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY chưa cấu hình — bắt buộc để lưu token dịch vụ đã kết nối. "
            'Tạo bằng: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(settings.token_encryption_key.encode())


def encrypt_token(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_token(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Token lưu trữ không hợp lệ hoặc key mã hoá đã đổi.") from exc
