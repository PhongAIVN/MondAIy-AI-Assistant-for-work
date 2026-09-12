"""Allowlist redirect phải phủ MỌI domain web đang phục vụ, không chỉ một.

Ca lỗi thật trên production 21/08/2026: `CORS_ORIGINS` đã có `mondaiy.io.vn`
nhưng `WEB_APP_PUBLIC_URL` vẫn là `c3-app-004.io.vn`. Vì `auth.py` chỉ so với
`WEB_APP_PUBLIC_URL`, đăng nhập Google chết trên domain mới với
"ext_redirect_uri không hợp lệ", trong khi domain cũ vẫn chạy bình thường.
"""

import pytest

from src.api.auth import _is_allowed_redirect_target
from src.config import allowed_web_origins, get_settings


@pytest.fixture
def two_domains(monkeypatch):
    # get_settings() có @lru_cache — không xoá cache thì setenv không có tác dụng,
    # và test sẽ xanh khi chạy riêng nhưng đỏ khi chạy cả suite.
    get_settings.cache_clear()
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://www.mondaiy.io.vn,https://mondaiy.io.vn,https://www.c3-app-004.io.vn",
    )
    monkeypatch.setenv("WEB_APP_PUBLIC_URL", "https://www.c3-app-004.io.vn")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_domain_moi_trong_cors_van_dang_nhap_duoc(two_domains):
    # Chính xác ca production đã hỏng.
    assert _is_allowed_redirect_target("https://www.mondaiy.io.vn/auth/google/callback")


def test_domain_cu_khong_bi_mat(two_domains):
    assert _is_allowed_redirect_target("https://www.c3-app-004.io.vn/auth/google/callback")


def test_callback_mobile_van_chay(two_domains):
    assert _is_allowed_redirect_target("mondaiy://auth/callback")


@pytest.mark.parametrize(
    "hostile",
    [
        # Tiền tố trùng nhưng domain khác — đây là lý do cấm dùng startswith.
        "https://www.mondaiy.io.vn.evil.com/steal",
        "http://www.mondaiy.io.vn/auth/google/callback",  # sai scheme
        "https://evil.com/auth/google/callback",
        "javascript:alert(1)",
    ],
)
def test_van_chan_open_redirect(two_domains, hostile):
    assert not _is_allowed_redirect_target(hostile)


def test_web_app_public_url_luon_nam_trong_tap_cho_phep(two_domains):
    # Kể cả khi ai đó quên khai nó trong CORS_ORIGINS.
    assert "https://www.c3-app-004.io.vn" in allowed_web_origins()
