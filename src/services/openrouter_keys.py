"""Pool xoay vòng API key OpenRouter.

Key chỉ được đọc từ environment/secret manager, không được ghi vào log hoặc DB.
`OPENROUTER_API_KEYS` nhận danh sách phân cách bằng dấu phẩy; biến cũ
`OPENROUTER_API_KEY` vẫn được hỗ trợ để không phá môi trường hiện tại.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from src.config import get_settings


@dataclass
class _KeyState:
    value: str
    unavailable_until: float = 0.0


class OpenRouterKeyPool:
    def __init__(self, keys: list[str], cooldown_seconds: float = 30.0) -> None:
        if not keys:
            raise ValueError("Chưa cấu hình OPENROUTER_API_KEY hoặc OPENROUTER_API_KEYS")
        self._keys = [_KeyState(key) for key in dict.fromkeys(keys)]
        self._cooldown_seconds = cooldown_seconds
        self._cursor = 0
        self._lock = threading.Lock()

    def next_key(self) -> str:
        """Chọn key khả dụng theo round-robin; nếu tất cả đang cooldown, chọn key cũ nhất."""
        now = time.monotonic()
        with self._lock:
            for offset in range(len(self._keys)):
                index = (self._cursor + offset) % len(self._keys)
                state = self._keys[index]
                if state.unavailable_until <= now:
                    self._cursor = (index + 1) % len(self._keys)
                    return state.value

            state = min(self._keys, key=lambda item: item.unavailable_until)
            self._cursor = (self._keys.index(state) + 1) % len(self._keys)
            return state.value

    def mark_unavailable(self, key: str) -> None:
        """Tạm bỏ qua key sau lỗi quota/auth/rate-limit; không lưu nguyên nhân chứa secret."""
        with self._lock:
            for state in self._keys:
                if state.value == key:
                    state.unavailable_until = time.monotonic() + self._cooldown_seconds
                    return

    @property
    def size(self) -> int:
        return len(self._keys)


def build_openrouter_key_pool() -> OpenRouterKeyPool:
    settings = get_settings()
    configured = [item.strip() for item in settings.openrouter_api_keys.split(",") if item.strip()]
    if not configured and settings.openrouter_api_key.strip():
        configured = [settings.openrouter_api_key.strip()]
    return OpenRouterKeyPool(configured)


def build_groq_key_pool() -> OpenRouterKeyPool:
    """Build the same rotating pool for Groq's OpenAI-compatible endpoint."""
    settings = get_settings()
    configured = [item.strip() for item in settings.groq_api_keys.split(",") if item.strip()]
    if not configured and settings.groq_api_key.strip():
        configured = [settings.groq_api_key.strip()]
    return OpenRouterKeyPool(configured)
