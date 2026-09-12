"""Chặn tái diễn sự cố bundle production trỏ vào backend dưới máy dev.

Bản deploy 2026-08-09 gọi http://127.0.0.1:8001 vì Vite nạp .env.local ở mọi
mode, kể cả `vc build --prod` chạy dưới máy. .env.production khai lại
VITE_API_URL rỗng để đè .env.local — chỉ có tác dụng khi file này được commit,
nên test kiểm luôn cả ngoại lệ trong .gitignore.
"""

import subprocess
from pathlib import Path

import pytest

_WEB_APP = Path(__file__).resolve().parents[2] / "client" / "web-app"
_ENV_PRODUCTION = _WEB_APP / ".env.production"


def _parse_env(path: Path) -> dict[str, str]:
    """Đọc file .env thành dict, bỏ dòng trống và dòng comment."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def test_env_production_exists():
    assert _ENV_PRODUCTION.is_file(), ".env.production bị xoá thì .env.local của máy dev sẽ lọt vào bundle production"


def test_vite_api_url_is_empty():
    """Rỗng nghĩa là same-origin, để vercel.json/Caddyfile rewrite /api/*.

    Điền URL backend vào đây là ghim cứng domain vào bundle, mất luôn đường lùi
    khi backend đổi chỗ.
    """
    values = _parse_env(_ENV_PRODUCTION)
    assert "VITE_API_URL" in values, "phải khai VITE_API_URL thì mới đè được .env.local"
    assert values["VITE_API_URL"] == ""


def test_env_production_not_gitignored():
    """File chỉ có tác dụng khi được commit; .gitignore đang chặn .env*."""
    if not (_WEB_APP.parents[1] / ".git").is_dir():
        pytest.skip("không phải git checkout")

    result = subprocess.run(
        ["git", "check-ignore", "-q", str(_ENV_PRODUCTION)],
        cwd=_WEB_APP,
        capture_output=True,
    )
    # git check-ignore: 0 = bị ignore, 1 = không bị ignore.
    assert result.returncode == 1, ".env.production đang bị .gitignore chặn"
