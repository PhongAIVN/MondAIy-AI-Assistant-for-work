from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config import get_settings
from src.services import auth as auth_service


def user_or_ip_key(request: Request) -> str:
    """Share limits by authenticated user and client IP; anonymous routes use IP."""
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            user_id = auth_service.decode_token(authorization.split(" ", 1)[1].strip(), "access")
            return f"user:{user_id}:ip:{get_remote_address(request)}"
        except ValueError:
            pass
    return f"ip:{get_remote_address(request)}"


_settings = get_settings()
# Tests remain deterministic and do not require an external Redis daemon.
_storage_uri = "memory://" if _settings.app_env == "test" else _settings.redis_url
# default_limits ap dung cho MOI route KHONG co @limiter.limit rieng — truoc
# day hau het API (tasks.py, messages.py, calendar.py, meeting_notes.py...)
# hoan toan khong co gioi han nao, chi vai router (auth/connections/runs) tu
# gan decorator thu cong. Endpoint nao can gioi han chat hon (vd ghi Google
# Calendar that, gioi han quota phia Google) van khai @limiter.limit rieng —
# decorator cu the luon uu tien hon default_limits (slowapi tu xu ly).
# Yeu cau SlowAPIMiddleware duoc dang ky o main.py thi default_limits moi co
# hieu luc — chi co app.state.limiter/exception_handler KHONG du.
limiter = Limiter(key_func=user_or_ip_key, storage_uri=_storage_uri, default_limits=["100/minute"])
