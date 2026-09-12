"""Default Redis URL must work for local .venv (not only Docker DNS)."""

from src.config import Settings


def test_default_redis_url_targets_localhost():
    # Compose ghi đè REDIS_URL=redis://redis:6379/0 — default Settings phải
    # trỏ localhost để uvicorn ngoài container không 500 trên /auth/login.
    assert Settings().redis_url.startswith("redis://localhost:")
