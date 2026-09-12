"""Tầng chống spam token dùng chung cho Google Docs và Google Sheets.

Ba lớp, theo đúng thứ tự khi phục vụ một lượt đọc:

1. Cache theo revision — trúng cache thì KHÔNG trừ quota và KHÔNG gọi lại LLM.
2. Quota ngày — hết lượt thì 429, nói rõ khi nào được cấp lại.
3. Cap kích thước — do connector áp trước khi đưa nội dung cho LLM.

Đặt cache trước quota là có chủ đích: mở lại cùng một file không đổi nội dung
là thao tác vô hại, tính phí nó chỉ làm người dùng ngại dùng tính năng.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.document_read import DocumentReadCache, DocumentReadQuota


def _today(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).date().isoformat()


def _tomorrow(timezone_name: str) -> str:
    return (datetime.now(ZoneInfo(timezone_name)).date() + timedelta(days=1)).isoformat()


def build_cache_key(
    *,
    user_id: str,
    file_id: str,
    revision: str,
    extractor_version: str,
    sheet_name: str | None = None,
) -> str:
    """Khoá cache của một lượt đọc: đổi bất kỳ thành phần nào là đổi khoá.

    Băm thay vì nối chuỗi thô để độ dài cố định (cột String(64)) và để không
    lưu id tài liệu của người dùng ở dạng đọc được trong bảng cache.
    """
    if not extractor_version.strip():
        raise ValueError("extractor_version không được để trống khi tạo cache tài liệu.")
    raw = "\x00".join(
        [str(user_id), file_id, revision, extractor_version, sheet_name or ""]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _remaining(used: int, limit: int) -> int:
    return max(0, limit - used)


def quota_remaining(db: Session, user_id: str) -> int:
    """Số lượt đọc còn lại hôm nay, không tiêu thụ gì."""
    settings = get_settings()
    limit = settings.google_document_reads_per_day
    row = db.execute(
        select(DocumentReadQuota).where(DocumentReadQuota.user_id == str(user_id))
    ).scalar_one_or_none()
    if row is None or row.quota_day != _today(settings.app_timezone):
        return limit
    return _remaining(row.reads_used, limit)


def _quota_exhausted(limit: int, timezone_name: str) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=(
            f"Bạn đã dùng hết {limit} lượt đọc Google Docs/Sheets trong hôm nay. "
            f"Hạn mức được cấp lại lúc 00:00 ngày {_tomorrow(timezone_name)} "
            f"(giờ {timezone_name})."
        ),
    )


def consume_document_read(db: Session, user_id: str) -> int:
    """Trừ một lượt đọc và trả về số lượt còn lại; hết lượt thì 429.

    Việc trừ lượt phải NGUYÊN TỬ. Đọc bộ đếm ra Python rồi ghi lại giá trị +1 là
    một lost update kinh điển: 10 request song song cùng đọc N rồi cùng ghi N+1,
    tức chạy 10 lượt phân tích mà chỉ trừ 1 lượt — đúng đường lách mà tầng quota
    này sinh ra để chặn. Nên toàn bộ phép cộng nằm trong một câu UPDATE có điều
    kiện `reads_used < limit`, và `rowcount` là câu trả lời có giành được lượt
    hay không. Cách này đúng trên cả sqlite lẫn postgres: cả hai đều khoá hàng
    và tính lại điều kiện WHERE trên phiên bản hàng mới nhất.

    Không có nhánh "bỏ qua khi thiếu cấu hình": ngưỡng luôn tồn tại trong
    `src/config.py`, thiếu thì Settings đã nổ từ lúc khởi động.
    """
    settings = get_settings()
    limit = settings.google_document_reads_per_day
    quota_day = _today(settings.app_timezone)
    uid = str(user_id)

    # Vòng lặp xử lý hai kiểu va chạm giữa các request song song: cùng tạo hàng
    # đầu tiên cho một user (bên thua nhận IntegrityError), và cùng rollover
    # đúng lúc giao ngày (bên thua thấy hàng đã sang ngày mới). Cả hai đều quay
    # lại nhánh UPDATE nguyên tử ở đầu vòng.
    for _ in range(3):
        claimed = db.execute(
            update(DocumentReadQuota)
            .where(
                DocumentReadQuota.user_id == uid,
                DocumentReadQuota.quota_day == quota_day,
                DocumentReadQuota.reads_used < limit,
            )
            .values(reads_used=DocumentReadQuota.reads_used + 1)
            .returning(DocumentReadQuota.reads_used)
        ).fetchone()
        if claimed is not None:
            # RETURNING trả về giá trị của CHÍNH lượt vừa giành được. Nếu select
            # lại sau commit thì con số báo cho người dùng có thể đã kèm lượt của
            # request khác chạy song song — hai người cùng thấy "còn 0 lượt".
            db.commit()
            return _remaining(int(claimed[0]), limit)

        # Hàng của ngày cũ: chuyển sang ngày mới và tính luôn lượt này. Điều
        # kiện `quota_day != today` nằm trong chính câu UPDATE nên hai request
        # cùng lúc chỉ một bên rollover được, bên kia rơi về nhánh cộng ở trên.
        rolled_over = db.execute(
            update(DocumentReadQuota)
            .where(
                DocumentReadQuota.user_id == uid,
                DocumentReadQuota.quota_day != quota_day,
            )
            .values(quota_day=quota_day, reads_used=1)
            .returning(DocumentReadQuota.reads_used)
        ).fetchone()
        if rolled_over is not None:
            db.commit()
            return _remaining(int(rolled_over[0]), limit)

        existing = db.execute(
            select(DocumentReadQuota.reads_used).where(
                DocumentReadQuota.user_id == uid,
                DocumentReadQuota.quota_day == quota_day,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if int(existing) >= limit:
                db.rollback()
                raise _quota_exhausted(limit, settings.app_timezone)
            # Hàng của hôm nay mà vẫn còn lượt: UPDATE #1 trượt chỉ vì lúc nó
            # chạy, hàng còn mang ngày hôm qua và một request khác vừa rollover
            # xong ngay giữa hai câu lệnh. Đây là va chạm giao ngày, KHÔNG phải
            # cạn quota — trả 429 ở đây là từ chối oan người dùng còn nguyên
            # gần hết hạn mức. Quay lại nhánh UPDATE nguyên tử.
            db.rollback()
            continue

        try:
            db.add(DocumentReadQuota(user_id=uid, quota_day=quota_day, reads_used=1))
            db.commit()
        except IntegrityError:
            # Request khác vừa tạo hàng trước; quay lại nhánh UPDATE nguyên tử.
            db.rollback()
            continue
        return _remaining(1, limit)

    raise RuntimeError(f"Không trừ được lượt đọc tài liệu cho user {uid} sau 3 lần thử.")


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Không serialize được kiểu {type(value)!r} vào cache đọc tài liệu.")


def read_cache(db: Session, *, user_id: str, cache_key: str) -> tuple[list[dict], bool] | None:
    """Trả (proposals, truncated) nếu còn hạn, None nếu miss/hết hạn.

    Dòng hết hạn bị xoá ngay tại chỗ để bảng không phình theo mỗi lần sửa file.
    """
    ttl = get_settings().google_document_cache_ttl_seconds
    row = db.execute(
        select(DocumentReadCache).where(
            DocumentReadCache.user_id == str(user_id),
            DocumentReadCache.cache_key == cache_key,
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    created_at = row.created_at
    # SQLite trả datetime naive dù cột khai timezone-aware.
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    if datetime.now(UTC) - created_at > timedelta(seconds=ttl):
        db.delete(row)
        db.commit()
        return None
    return json.loads(row.payload), bool(row.truncated)


def write_cache(db: Session, *, user_id: str, cache_key: str, proposals: list[dict], truncated: bool) -> None:
    """Ghi đè kết quả cho đúng khoá này (upsert theo (user_id, cache_key))."""
    payload = json.dumps(proposals, default=_json_default, ensure_ascii=False)
    row = db.execute(
        select(DocumentReadCache).where(
            DocumentReadCache.user_id == str(user_id),
            DocumentReadCache.cache_key == cache_key,
        )
    ).scalar_one_or_none()
    if row is None:
        row = DocumentReadCache(
            user_id=str(user_id),
            cache_key=cache_key,
            payload=payload,
            truncated=truncated,
            created_at=datetime.now(UTC),
        )
        db.add(row)
    else:
        row.payload = payload
        row.truncated = truncated
        row.created_at = datetime.now(UTC)
    db.commit()
