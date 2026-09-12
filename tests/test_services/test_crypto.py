from cryptography.fernet import Fernet

from src.services import crypto


def test_encrypt_decrypt_round_trip():
    plaintext = "ya29.a0Ael9sCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

    encrypted = crypto.encrypt_token(plaintext)

    assert encrypted != plaintext
    assert crypto.decrypt_token(encrypted) == plaintext


def test_decrypt_rejects_garbage_input():
    # Chuỗi không phải Fernet token hợp lệ (vd. đọc nhầm cột plaintext cũ,
    # hoặc dữ liệu hỏng) — phải báo lỗi rõ ràng, không được im lặng trả rác.
    try:
        crypto.decrypt_token("not-a-fernet-token")
        assert False, "phải raise ValueError"
    except ValueError as exc:
        assert "không hợp lệ" in str(exc) or "key mã hoá" in str(exc)


def test_decrypt_rejects_token_encrypted_with_different_key(monkeypatch):
    # Mô phỏng key rotation: token cũ mã hoá bằng key A, server giờ cấu hình
    # key B — mọi token cũ PHẢI báo lỗi rõ ràng để caller biết cần user kết
    # nối lại, không được trả plaintext rác hoặc crash mơ hồ.
    other_key_token = Fernet(Fernet.generate_key()).encrypt(b"leaked-under-old-key").decode()

    try:
        crypto.decrypt_token(other_key_token)
        assert False, "phải raise ValueError"
    except ValueError:
        pass


def test_encrypt_raises_runtime_error_when_key_not_configured(monkeypatch):
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "token_encryption_key", "")
    crypto._fernet.cache_clear()
    try:
        try:
            crypto.encrypt_token("anything")
            assert False, "phải raise RuntimeError"
        except RuntimeError as exc:
            assert "TOKEN_ENCRYPTION_KEY" in str(exc)
    finally:
        # Trả lại key thật cho cache, tránh làm hỏng test khác chạy sau trong
        # cùng process (get_settings() là @lru_cache singleton dùng chung).
        monkeypatch.undo()
        crypto._fernet.cache_clear()
