from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

# Gọi ngay khi 1 item tải xong THÀNH CÔNG (không gọi cho item bị skip vì lỗi
# hoặc không có tín hiệu) — cho phép báo tiến trình theo item thay vì đợi cả
# fetch_range() xong mới biết. `label` là chuỗi ngắn hiện lên UI ngay (Gmail:
# subject; Jira: summary).
OnItemCallback = Callable[[dict, str], None]


class ConnectorAPIError(Exception):
    """Base cho lỗi gọi API của bất kỳ connector nào — message đã làm sạch,
    an toàn để lộ ra route/SSE. GmailAPIError/JiraAPIError kế thừa từ đây để
    caller catch chung được mà không cần biết provider cụ thể."""


@dataclass(frozen=True)
class Source:
    """1 kênh/nhãn có thể đồng bộ trong 1 connection (vd. nhãn Gmail)."""

    id: str
    name: str
    item_count: int | None = None
    #: Ghi được vào nguồn này không. Lịch đăng ký (ngày lễ, lịch người khác chia
    #: sẻ dạng chỉ xem) vẫn nằm trong danh sách nhưng Google trả 403 khi ghi —
    #: giao diện cần biết trước để không mời người dùng bấm một nút chắc chắn
    #: hỏng. Mặc định True: connector chỉ đọc (Gmail) không dùng tới cờ này.
    writable: bool = True


class BaseConnector(ABC):
    """Interface chung cho connector chỉ đọc — Gmail hiện tại, Discord/Telegram sau dùng lại."""

    @abstractmethod
    async def list_sources(self) -> list[Source]: ...

    @abstractmethod
    async def fetch_range(
        self, source: Source, time_from: datetime, time_to: datetime, on_item: OnItemCallback | None = None
    ) -> list[dict]: ...

    @abstractmethod
    def normalize(self, raw_item: dict, source: Source) -> dict: ...

    @abstractmethod
    def deep_link(self, raw_item: dict) -> str: ...
