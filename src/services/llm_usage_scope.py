"""Context nội bộ để quy usage LLM về user đã được backend xác thực."""

from contextvars import ContextVar

_user_id: ContextVar[str | None] = ContextVar("llm_usage_user_id", default=None)


def set_llm_usage_user(user_id: str | None) -> None:
    _user_id.set(user_id or None)


def current_llm_usage_user() -> str | None:
    return _user_id.get()


def reset_llm_usage_user() -> None:
    _user_id.set(None)
