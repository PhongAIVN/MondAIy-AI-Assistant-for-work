"""Thùng rác task: giữ 7 ngày, khôi phục được, quá hạn thì xoá vĩnh viễn.

Đây là đường DUY NHẤT trong hệ tự xoá dữ liệu người dùng mà không ai bấm nút,
nên phần lớn test ở đây khẳng định cái gì KHÔNG được xoá, chứ không phải cái gì
được xoá. Một job dọn quá tay không báo lỗi — nó chỉ lặng lẽ làm mất việc của
người dùng, và không có gì để truy sau khi đã commit.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db import SessionLocal
from src.models.task import Task
from src.services.task_trash import purge_expired_trash, trash_cutoff

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user_id() -> str:
    """Mỗi test một user riêng. Suite dùng chung một DB và không reset giữa các
    test, nên đếm toàn bảng sẽ đọc phải dữ liệu của test khác — đúng loại rò rỉ
    làm test xanh/đỏ vì lý do chẳng liên quan."""
    return f"u-{uuid.uuid4().hex[:12]}"


def _task(db: Session, user_id: str, *, status: str, cancelled_at: datetime | None, title: str) -> Task:
    row = Task(
        user_id=user_id,
        cluster_key=f"k-{user_id}-{title}",
        title=title,
        detail="",
        status=status,
        cancelled_at=cancelled_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _con_lai(db: Session, user_id: str) -> set[str]:
    return {row.title for row in db.query(Task).filter(Task.user_id == user_id).all()}


def test_xoa_task_qua_han_trong_thung_rac(db: Session, user_id: str) -> None:
    qua_han = NOW - timedelta(days=8)
    _task(db, user_id, status="cancelled", cancelled_at=qua_han, title="qua-han")

    assert purge_expired_trash(db, now=NOW) == 1
    assert _con_lai(db, user_id) == set()


def test_khong_xoa_task_con_trong_han(db: Session, user_id: str) -> None:
    con_han = NOW - timedelta(days=6, hours=23)
    _task(db, user_id, status="cancelled", cancelled_at=con_han, title="con-han")

    assert purge_expired_trash(db, now=NOW) == 0
    assert _con_lai(db, user_id) == {"con-han"}


def test_khong_bao_gio_xoa_task_khong_co_moc_huy(db: Session, user_id: str) -> None:
    """Task huỷ TRƯỚC khi có cột này đều NULL — đoán mốc cho chúng là bịa.

    Nếu backfill bằng `updated_at`, hạn xoá của task huỷ từ lâu rơi vào QUÁ KHỨ,
    nên vòng dọn đầu tiên sau khi deploy sẽ xoá sạch chúng ngay, không ai kịp
    thấy thùng rác lần nào.
    """
    _task(db, user_id, status="cancelled", cancelled_at=None, title="huy-tu-truoc")

    assert purge_expired_trash(db, now=NOW) == 0
    assert _con_lai(db, user_id) == {"huy-tu-truoc"}


@pytest.mark.parametrize("status", ["proposed", "confirmed", "completed"])
def test_khong_dung_toi_task_ngoai_thung_rac(db: Session, user_id: str, status: str) -> None:
    """Kể cả khi mốc huỷ sót lại từ một lần huỷ trước đó."""
    _task(
        db,
        user_id,
        status=status,
        cancelled_at=NOW - timedelta(days=90),
        title=f"dang-{status}",
    )

    assert purge_expired_trash(db, now=NOW) == 0
    assert _con_lai(db, user_id) == {f"dang-{status}"}


def test_ton_trong_tran_moi_vong(db: Session, user_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASK_TRASH_PURGE_BATCH_LIMIT", "2")
    get_settings.cache_clear()
    try:
        for i in range(5):
            _task(
                db,
                user_id,
                status="cancelled",
                cancelled_at=NOW - timedelta(days=10 + i),
                title=f"rac-{i}",
            )

        assert purge_expired_trash(db, now=NOW) == 2
        assert len(_con_lai(db, user_id)) == 3
    finally:
        get_settings.cache_clear()


def test_xoa_cai_cu_nhat_truoc(db: Session, user_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Trần mỗi vòng chỉ đúng nếu thứ tự xoá là xác định."""
    monkeypatch.setenv("TASK_TRASH_PURGE_BATCH_LIMIT", "1")
    get_settings.cache_clear()
    try:
        _task(db, user_id, status="cancelled", cancelled_at=NOW - timedelta(days=30), title="cu-nhat")
        _task(db, user_id, status="cancelled", cancelled_at=NOW - timedelta(days=8), title="moi-hon")

        purge_expired_trash(db, now=NOW)

        assert _con_lai(db, user_id) == {"moi-hon"}
    finally:
        get_settings.cache_clear()


def test_moc_han_theo_dung_so_ngay_da_cau_hinh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASK_TRASH_RETENTION_DAYS", "3")
    get_settings.cache_clear()
    try:
        assert trash_cutoff(NOW) == NOW - timedelta(days=3)
    finally:
        get_settings.cache_clear()


def test_don_tren_toan_he_chu_khong_theo_tung_user(db: Session, user_id: str) -> None:
    """Đây là job nền, không phải thao tác của người dùng.

    Cố ý khẳng định tính chất này: một bản dọn lỡ bị bó theo user sẽ để lại rác
    của mọi user không đăng nhập trong kỳ, và không ai phát hiện cho tới lúc
    bảng phình ra.
    """
    user_khac = f"{user_id}-khac"
    _task(db, user_id, status="cancelled", cancelled_at=NOW - timedelta(days=9), title="cua-toi")
    _task(db, user_khac, status="cancelled", cancelled_at=NOW - timedelta(days=9), title="cua-nguoi-khac")

    purge_expired_trash(db, now=NOW)

    assert _con_lai(db, user_id) == set()
    assert _con_lai(db, user_khac) == set()
