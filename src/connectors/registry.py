from __future__ import annotations

from dataclasses import dataclass

from src.connectors.base import BaseConnector
from src.connectors.calendar import CalendarConnector
from src.connectors.discord import DiscordConnector
from src.connectors.gmail import GmailConnector
from src.connectors.jira import JiraConnector
from src.connectors.outlook import OutlookConnector
from src.connectors.slack import SlackConnector


@dataclass(frozen=True)
class ConnectorBinding:
    """Một connector con nằm dưới một OAuth/provider connection.

    Google dùng chung một token cho Gmail và Calendar, nên provider không còn
    xác định duy nhất connector. ``namespace`` được gắn cho connector không
    mặc định để fetch_node route đúng mà không cần thêm connection giả.
    """

    namespace: str
    label: str
    connector_cls: type[BaseConnector]
    legacy_default: bool = False


CONNECTORS_BY_PROVIDER: dict[str, tuple[ConnectorBinding, ...]] = {
    "google": (
        ConnectorBinding("gmail", "Gmail", GmailConnector, legacy_default=True),
        ConnectorBinding("calendar", "Calendar", CalendarConnector),
    ),
    "jira": (ConnectorBinding("jira", "Jira", JiraConnector, legacy_default=True),),
    "outlook": (ConnectorBinding("outlook", "Outlook", OutlookConnector, legacy_default=True),),
    "slack": (ConnectorBinding("slack", "Slack", SlackConnector, legacy_default=True),),
    "discord": (ConnectorBinding("discord", "Discord", DiscordConnector, legacy_default=True),),
}


def bindings_for_provider(provider: str) -> tuple[ConnectorBinding, ...]:
    return CONNECTORS_BY_PROVIDER.get(provider, ())


def public_source(binding: ConnectorBinding, source_id: str, source_name: str, *, namespaced: bool) -> tuple[str, str]:
    """Đổi source connector-native thành contract public của integration API."""
    if not namespaced:
        return source_id, source_name
    # Connector mặc định giữ ID cũ để frontend/backend có thể deploy theo bất
    # kỳ thứ tự nào. Chỉ connector thứ hai trở đi cần namespace để phân luồng.
    if binding.legacy_default:
        return source_id, f"{binding.label} · {source_name}"
    return f"{binding.namespace}:{source_id}", f"{binding.label} · {source_name}"


def resolve_connector(provider: str, public_source_id: str) -> tuple[type[BaseConnector], str]:
    """Route source public về connector và source ID native.

    Google source cũ (``INBOX``) không có namespace vẫn về Gmail. Contract
    tương thích này cho phép các run/bookmark đã lưu trước migration tiếp tục
    chạy. Prefix lạ bị từ chối thay vì âm thầm gửi sang Gmail.
    """
    bindings = bindings_for_provider(provider)
    if not bindings:
        raise ValueError(f"Provider '{provider}' chưa cắm vào pipeline.")
    if len(bindings) == 1:
        return bindings[0].connector_cls, public_source_id

    namespace, separator, native_source_id = public_source_id.partition(":")
    if separator:
        for binding in bindings:
            if binding.namespace == namespace:
                if not native_source_id:
                    raise ValueError(f"Source '{public_source_id}' thiếu ID sau namespace.")
                return binding.connector_cls, native_source_id
        raise ValueError(f"Source namespace '{namespace}' không thuộc provider '{provider}'.")

    default = next((binding for binding in bindings if binding.legacy_default), None)
    if default is None:
        raise ValueError(f"Source '{public_source_id}' phải có namespace connector.")
    return default.connector_cls, public_source_id
