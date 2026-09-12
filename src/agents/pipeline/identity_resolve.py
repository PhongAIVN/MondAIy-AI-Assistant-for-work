from __future__ import annotations

_SELF_OR_GROUP_HINTS = frozenset(
    {
        "mình",
        "tôi",
        "em",
        "bạn",
        "các bạn",
        "cả lớp",
        "cả nhóm",
        "mọi người",
        "everyone",
        "all",
        "you",
        "team",
    }
)


def resolve_assignee(assignee_hint: str, message: dict, user_email: str | None) -> tuple[str | None, bool]:
    """Chuẩn hoá người phụ trách — áp nguyên tắc BR-05/FR-061 cho danh tính: không suy
    diễn người thứ ba từ tên gợi ý tự do. Chỉ xác nhận là chính người dùng khi có bằng
    chứng cứng (họ là người nhận trực tiếp của message) và gợi ý không chỉ đích danh ai
    khác. Mọi trường hợp còn lại để trống và đánh dấu chưa xác định."""
    hint = (assignee_hint or "").strip().lower()
    to_addresses = {a.lower() for a in (message.get("to") or [])}
    is_direct_recipient = bool(user_email) and user_email.lower() in to_addresses

    references_self_or_group = not hint or any(word in hint for word in _SELF_OR_GROUP_HINTS)
    if is_direct_recipient and references_self_or_group:
        return user_email, False
    return None, True
