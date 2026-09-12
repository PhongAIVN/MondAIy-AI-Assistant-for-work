"""Trích và lưu profile memory từ phát biểu tường minh của người dùng.

Không dùng LLM để quyết định lưu gì: một prompt hoặc đoạn nguồn bên ngoài không
được phép tự biến thành profile. Chỉ các mẫu hẹp bên dưới và giá trị đã chuẩn
hoá mới đi vào bảng memory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.models.user import User
from src.models.user_memory import UserProfileMemory

PROFILE_KEYS = frozenset({"display_name", "preferred_name", "response_style", "role", "timezone", "language"})

_NAME_PATTERNS = (
    # (?<!của\s) chặn sở hữu cách: "mentor của tôi tên là X" là người thứ ba,
    # không phải danh tính user (bug prod 22/08). "Tôi tên là X" ở đầu câu/sau
    # dấu phẩy vẫn khớp bình thường.
    re.compile(r"(?i)(?<!của\s)\b(?:tôi|mình|em)\s+tên\s+là\s+([^.!?\n,;]{1,80})"),
    # "Tên của tôi là X": đại từ đứng sau "của" là hợp lệ (sở hữu ngược của
    # keyword tên), nên mẫu này không dùng lookbehind — nó không thể khớp với
    # câu người thứ ba vì cần chữ "tên" ngay trước đại từ.
    re.compile(r"(?i)\btên\s+(?:của\s+)?(?:tôi|mình|em)\s+là\s+([^.!?\n,;]{1,80})"),
    re.compile(r"(?i)\bmy\s+name\s+is\s+([^.!?\n,;]{1,80})"),
)
_PREFERRED_NAME_PATTERNS = (
    # Lookbehind vô hại ở đây (đại từ luôn đứng sau "gọi ") nhưng giữ để nhất
    # quán: mọi pattern danh tính đều chặn vị trí sở hữu cách.
    re.compile(r"(?i)(?<!của\s)\b(?:hãy\s+)?gọi\s+(?:tôi|mình|em)\s+là\s+([^.!?\n,;]{1,80})"),
    re.compile(r"(?i)(?<!của\s)\bcall\s+me\s+([^.!?\n,;]{1,80})"),
)
_CLEAR_ALL = re.compile(
    r"(?i)\b(?:xóa|xoá|quên|forget|clear|delete)\b.{0,40}"
    r"\b(?:bộ nhớ|memory|hồ sơ|profile)\b"
)
_FORGET_NAME = re.compile(
    r"(?i)\b(?:đừng\s+nhớ|quên|xóa|xoá|forget|delete)\b.{0,30}"
    r"\b(?:tên|cách gọi|name)\b"
)
_FORGET_PREFERENCES = re.compile(
    r"(?i)\b(?:đừng\s+nhớ|quên|xóa|xoá|forget|delete)\b.{0,30}"
    r"\b(?:sở thích|cách trả lời|preference|response style)\b"
)


@dataclass(frozen=True)
class ProfileMutation:
    updates: dict[str, str] = field(default_factory=dict)
    deleted_keys: frozenset[str] = frozenset()
    cleared_all: bool = False


def _clean_name(raw: str) -> str | None:
    # Dừng trước một mệnh đề mới: "Tôi tên là An và tôi thích...".
    value = re.split(r"(?i)\s+(?:và|nhưng|and|but)\s+(?:tôi|mình|em|i)\b", raw, maxsplit=1)[0]
    value = " ".join(value.strip(" \t\"'“”‘’").split())
    if not 1 <= len(value) <= 80 or len(value.split()) > 10:
        return None
    if not all(char.isalpha() or char in " -'’" for char in value):
        return None
    return value


def _first_name(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match and (value := _clean_name(match.group(1))):
            return value
    return None


def extract_profile_mutation(text: str) -> ProfileMutation:
    """Chỉ nhận facts profile tường minh; nội dung công việc không tạo memory."""
    normalized = " ".join((text or "").strip().split())
    if not normalized:
        return ProfileMutation()
    if _CLEAR_ALL.search(normalized):
        return ProfileMutation(cleared_all=True)

    deleted: set[str] = set()
    if _FORGET_NAME.search(normalized):
        deleted.update({"display_name", "preferred_name"})
    if _FORGET_PREFERENCES.search(normalized):
        deleted.update({"response_style", "language"})

    updates: dict[str, str] = {}
    if name := _first_name(normalized, _NAME_PATTERNS):
        updates["display_name"] = name
    if preferred_name := _first_name(normalized, _PREFERRED_NAME_PATTERNS):
        updates["preferred_name"] = preferred_name

    folded = normalized.casefold()
    if re.search(r"\b(?:ngắn gọn|súc tích|concise|brief)\b", folded):
        if re.search(r"\b(?:trả lời|câu trả lời|response|answer)\b", folded):
            updates["response_style"] = "ngắn gọn"
    elif re.search(r"\b(?:chi tiết|đầy đủ|detailed|thorough)\b", folded):
        if re.search(r"\b(?:trả lời|câu trả lời|response|answer)\b", folded):
            updates["response_style"] = "chi tiết"

    role_patterns = {
        "học viên": r"\b(?:tôi|mình|em)\s+là\s+(?:một\s+)?(?:học viên|sinh viên)\b",
        "mentor": r"\b(?:tôi|mình)\s+là\s+(?:một\s+)?mentor\b",
        "giảng viên": r"\b(?:tôi|mình)\s+là\s+(?:một\s+)?giảng viên\b",
        "quản lý dự án": r"\b(?:tôi|mình)\s+là\s+(?:một\s+)?(?:quản lý dự án|project manager)\b",
    }
    for value, pattern in role_patterns.items():
        if re.search(pattern, folded):
            updates["role"] = value
            break

    if re.search(r"\b(?:múi giờ|timezone)\b.{0,20}\b(?:việt nam|vietnam|asia/ho_chi_minh)\b", folded):
        updates["timezone"] = "Asia/Ho_Chi_Minh"
    elif match := re.search(r"\b(?:utc|gmt)\s*([+-])\s*(\d{1,2})\b", folded):
        hours = min(int(match.group(2)), 14)
        updates["timezone"] = f"UTC{match.group(1)}{hours:02d}:00"

    if re.search(r"\b(?:trả lời|nói chuyện|response|answer)\b.{0,25}\b(?:tiếng việt|vietnamese)\b", folded):
        updates["language"] = "Tiếng Việt"
    elif re.search(r"\b(?:trả lời|nói chuyện|response|answer)\b.{0,25}\b(?:tiếng anh|english)\b", folded):
        updates["language"] = "English"

    # Một lệnh quên và một update cùng key trong cùng câu: lệnh quên thắng.
    for key in deleted:
        updates.pop(key, None)
    return ProfileMutation(updates=updates, deleted_keys=frozenset(deleted))


def load_user_profile(db: Session, user_id: str) -> dict[str, str]:
    """Đọc profile của đúng user; caller không thể truyền user id qua model."""
    numeric_user_id = int(user_id)
    rows = db.execute(select(UserProfileMemory).where(UserProfileMemory.user_id == numeric_user_id)).scalars()
    profile = {row.key: row.value for row in rows if row.key in PROFILE_KEYS}
    user = db.get(User, numeric_user_id)
    if user and user.display_name and "display_name" not in profile:
        profile["display_name"] = user.display_name
    return profile


def clear_user_profile(db: Session, user_id: str) -> None:
    numeric_user_id = int(user_id)
    db.execute(delete(UserProfileMemory).where(UserProfileMemory.user_id == numeric_user_id))
    user = db.get(User, numeric_user_id)
    if user is not None:
        user.display_name = ""


def set_user_profile_value(
    db: Session,
    user_id: str | int,
    key: str,
    value: str,
    *,
    source_conversation_id: int | None = None,
) -> UserProfileMemory:
    """Ghi một giá trị profile do user sửa trực tiếp từ Memory Inspector."""
    if key not in PROFILE_KEYS:
        raise ValueError(f"Profile key không hợp lệ: {key}")
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("Giá trị profile không được để trống.")
    if key == "display_name" and len(normalized) > 120:
        raise ValueError("Tên hiển thị không được dài quá 120 ký tự.")

    numeric_user_id = int(user_id)
    row = db.execute(
        select(UserProfileMemory).where(
            UserProfileMemory.user_id == numeric_user_id,
            UserProfileMemory.key == key,
        )
    ).scalar_one_or_none()
    if row is None:
        row = UserProfileMemory(user_id=numeric_user_id, key=key, value=normalized)
        db.add(row)
    else:
        row.value = normalized
    row.source_conversation_id = source_conversation_id
    row.updated_at = datetime.now(UTC)

    if key == "display_name":
        user = db.get(User, numeric_user_id)
        if user is not None:
            user.display_name = normalized
    return row


def delete_user_profile_keys(db: Session, user_id: str | int, keys: set[str] | frozenset[str]) -> int:
    """Xoá các profile key khỏi mọi đường prompt-visible của đúng user."""
    allowed = frozenset(key for key in keys if key in PROFILE_KEYS)
    if not allowed:
        return 0
    numeric_user_id = int(user_id)
    rows = list(
        db.execute(
            select(UserProfileMemory).where(
                UserProfileMemory.user_id == numeric_user_id,
                UserProfileMemory.key.in_(allowed),
            )
        ).scalars()
    )
    for row in rows:
        db.delete(row)
    if "display_name" in allowed:
        user = db.get(User, numeric_user_id)
        if user is not None:
            user.display_name = ""
    return len(rows)


def apply_profile_memory(
    db: Session,
    user_id: str,
    text: str,
    *,
    source_conversation_id: int | None = None,
) -> ProfileMutation:
    """Áp mutation vào transaction hiện tại; caller quyết định commit/rollback."""
    numeric_user_id = int(user_id)
    mutation = extract_profile_mutation(text)
    if mutation.cleared_all:
        clear_user_profile(db, user_id)
        return mutation

    if mutation.deleted_keys:
        db.execute(
            delete(UserProfileMemory).where(
                UserProfileMemory.user_id == numeric_user_id,
                UserProfileMemory.key.in_(mutation.deleted_keys),
            )
        )
        if "display_name" in mutation.deleted_keys:
            user = db.get(User, numeric_user_id)
            if user is not None:
                user.display_name = ""

    for key, value in mutation.updates.items():
        if key not in PROFILE_KEYS:
            continue
        set_user_profile_value(
            db,
            numeric_user_id,
            key,
            value,
            source_conversation_id=source_conversation_id,
        )
    return mutation
