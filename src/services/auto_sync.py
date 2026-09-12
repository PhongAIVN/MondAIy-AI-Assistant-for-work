"""Tự động tạo Run cho những user tới hạn đồng bộ (ADR-011).

Trước đây không có gì tự tạo Run: `src/worker.py` chỉ poll bảng `runs` tìm
dòng đã `queued`, mà dòng đó chỉ sinh ra khi người dùng bấm Sync trên FE. Hệ
quả là mở app lên lúc nào cũng thấy dữ liệu của lần bấm gần nhất.

Ranh giới privacy của module này: nó KHÔNG bao giờ tự chọn nguồn mới. Nguồn của
run tự động được sao chép nguyên văn từ run thành công gần nhất mà chính người
dùng đã tự tay chọn. Không có run thành công nào trước đó thì không auto-sync —
người dùng phải Sync thủ công ít nhất một lần để nói rõ họ muốn quét cái gì.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.runs import RunEnqueueBlockedError, enqueue_run
from src.config import get_settings
from src.models.run import Run
from src.models.schemas import RunCreateRequest, SyncSourceRef
from src.models.user import User

logger = logging.getLogger(__name__)


def _latest_run(db: Session, user_id: int, statuses: tuple[str, ...] | None = None) -> Run | None:
    """Run mới nhất của user, lọc theo trạng thái nếu có."""
    stmt = select(Run).where(Run.user_id == user_id)
    if statuses is not None:
        stmt = stmt.where(Run.status.in_(statuses))
    return db.execute(stmt.order_by(Run.created_at.desc()).limit(1)).scalar_one_or_none()


def _auto_idempotency_key(user_id: int, now: datetime, interval_minutes: int) -> str:
    """Khoá idempotency chốt theo ô thời gian, không theo thời điểm gọi.

    Mọi lần quét rơi vào cùng một ô `interval_minutes` sinh ra đúng một khoá.
    Nhờ vậy hai worker replica cùng phát hiện một user tới hạn trong cùng ô sẽ
    tạo ra cùng khoá, và enqueue_run() trả lại run cũ thay vì xếp hàng hai lần.
    """
    bucket = int(now.timestamp()) // (interval_minutes * 60)
    return f"auto-{user_id}-{bucket}"


def find_due_users(db: Session, now: datetime | None = None) -> list[User]:
    """Những user đủ điều kiện để scheduler tạo Run hộ, xếp người cũ nhất trước.

    Cơ chế lọc, theo thứ tự rẻ tiền trước: user còn hoạt động và chưa tắt công
    tắc riêng -> chưa có run nào đang `queued`/`running` (không chen ngang Sync
    thủ công người dùng đang ngồi chờ) -> run gần nhất ở BẤT KỲ trạng thái nào
    đã cách đây quá `auto_sync_interval_minutes`. Dùng run gần nhất bất kể
    trạng thái, chứ không chỉ run thành công, để một chuỗi run lỗi cũng phải
    giãn đúng nhịp thay vì bị thử lại liên tục.

    Trả về TOÀN BỘ người tới hạn, không cắt theo trần per-tick — cắt là việc
    của enqueue_due_auto_syncs(). Tách vậy để "ai tới hạn" và "xử bao nhiêu
    người mỗi vòng" là hai câu hỏi kiểm chứng được riêng.
    """
    settings = get_settings()
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(minutes=settings.auto_sync_interval_minutes)

    candidates = (
        db.execute(select(User).where(User.is_active.is_(True), User.auto_sync_enabled.is_(True))).scalars().all()
    )

    due: list[tuple[datetime, User]] = []
    for user in candidates:
        if _latest_run(db, user.id, ("queued", "running")) is not None:
            continue
        last = _latest_run(db, user.id)
        if last is None:
            continue
        last_at = last.created_at
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=UTC)
        if last_at > cutoff:
            continue
        due.append((last_at, user))

    due.sort(key=lambda pair: pair[0])
    return [user for _, user in due]


def build_auto_run_request(db: Session, user: User, now: datetime | None = None) -> RunCreateRequest | None:
    """Dựng payload Run tự động từ đúng bộ nguồn user đã tự chọn lần gần nhất.

    Trả None khi user chưa từng có run thành công, hoặc run đó không còn nguồn
    nào hợp lệ (kết nối đã bị gỡ thì `sources` cũ vẫn nằm trong DB nhưng vô
    nghĩa). Cửa sổ quét là `auto_sync_range_hours` gần nhất, ngắn hơn Sync thủ
    công vì phần cũ đã được các run trước ghi vào DB rồi.
    """
    settings = get_settings()
    now = now or datetime.now(UTC)

    last_ok = _latest_run(db, user.id, ("succeeded",))
    if last_ok is None or not last_ok.sources:
        return None

    sources = [SyncSourceRef.model_validate(item) for item in last_ok.sources]
    if not sources:
        return None
    # Cắt theo hạn mức phòng khi trần bị hạ xuống sau lúc run cũ được tạo —
    # nếu không, mọi vòng quét sẽ ném RunEnqueueBlockedError mãi mãi.
    sources = sources[: settings.max_sync_sources]

    return RunCreateRequest(
        sources=sources,
        time_from=now - timedelta(hours=settings.auto_sync_range_hours),
        time_to=now,
        timezone=last_ok.timezone or "UTC",
        language=last_ok.language or "vi",
        idempotency_key=_auto_idempotency_key(user.id, now, settings.auto_sync_interval_minutes),
        mode=last_ok.mode or "task_extraction",
    )


def enqueue_due_auto_syncs(db: Session, now: datetime | None = None) -> int:
    """Một vòng quét: tìm user tới hạn, xếp Run cho họ, trả về số run đã tạo.

    Vướng hạn mức (hệ thống đang bận, user vừa có run khác chen vào) không phải
    lỗi — bỏ qua, vòng quét sau sẽ thử lại. Chỉ log ở mức debug để không làm
    ngập log mỗi 5 phút.
    """
    settings = get_settings()
    if not settings.auto_sync_enabled:
        return 0

    created = 0
    # Cắt theo số user XỬ LÝ chứ không phải số run tạo được: nếu đếm theo run
    # thành công thì một loạt user bị bỏ qua sẽ kéo vòng quét chạy hết bảng.
    for user in find_due_users(db, now)[: settings.auto_sync_max_users_per_tick]:
        body = build_auto_run_request(db, user, now)
        if body is None:
            continue
        try:
            run = enqueue_run(db, user.id, body)
        except RunEnqueueBlockedError as blocked:
            logger.debug("Auto-sync bỏ qua user %s: %s", user.id, blocked.detail)
            continue
        except Exception:  # noqa: BLE001 - một user hỏng không được giết cả vòng quét
            db.rollback()
            logger.exception("Auto-sync lỗi khi enqueue cho user %s", user.id)
            continue
        created += 1
        logger.info("Auto-sync đã xếp run %s cho user %s (%s nguồn)", run.id, user.id, len(body.sources))

    return created
