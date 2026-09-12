"""Sinh cặp khoá VAPID cho kênh Web Push và in ra để dán vào `.env`.

    python3 scripts/generate_vapid_keys.py

Chạy một lần cho mỗi môi trường rồi giữ nguyên cặp khoá đó: đổi khoá là mọi
subscription trình duyệt đã cấp trước đó ngừng nhận được thông báo, người dùng
phải bật lại bằng tay.

Khoá in ra là bí mật thật — **không commit**, không dán vào `.env.example`,
không gửi qua chat nhóm.
"""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402


def _b64url(raw: bytes) -> str:
    """Base64url không padding — đúng định dạng mà chuẩn VAPID và Push API dùng.

    Trình duyệt nhận khoá công khai qua `applicationServerKey` và sẽ từ chối
    chuỗi base64 thường (ký tự `+`, `/`, `=`), nên khác biệt này không phải làm
    đẹp mà là điều kiện để đăng ký chạy được.
    """
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_vapid_keypair() -> tuple[str, str]:
    """Sinh khoá EC P-256 và trả về (public_key, private_key) đã mã hoá base64url.

    P-256 là đường cong duy nhất RFC 8292 cho phép. Khoá công khai xuất ở dạng
    điểm không nén 65 byte, khoá riêng ở dạng số nguyên 32 byte — đúng hai dạng
    pywebpush đọc trực tiếp, nên không cần thêm bước chuyển đổi lúc chạy.
    """
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    private_raw = private_key.private_numbers().private_value.to_bytes(32, "big")
    return _b64url(public_raw), _b64url(private_raw)


def main() -> None:
    public_key, private_key = generate_vapid_keypair()
    print("Dán hai dòng dưới đây vào .env (KHÔNG commit):\n")
    print(f"VAPID_PUBLIC_KEY={public_key}")
    print(f"VAPID_PRIVATE_KEY={private_key}")
    print("\nNhớ đặt VAPID_SUBJECT=mailto:<email-liên-hệ-thật> và WEB_PUSH_ENABLED=true khi sẵn sàng.")


if __name__ == "__main__":
    main()
