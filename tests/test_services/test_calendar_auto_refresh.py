"""Làm mới lịch ở nền và thông báo khi lịch bị đổi (FR-102).

Hai ràng buộc được khoá ở đây, và chúng quan trọng hơn phần cơ khí:

1. Vòng nền KHÔNG tự thêm nguồn — chỉ chạm kết nối Google người dùng đã tự nối
   và chưa gỡ, đúng ranh giới ADR-011 đặt cho auto-sync.
2. Thông báo "lịch đổi" chỉ bắn khi thật sự đáng chen ngang. Báo mọi lần Google
   chạm vào metadata là cách nhanh nhất khiến người dùng tắt thông báo, và lúc
   đó ta mất luôn những tin thật sự quan trọng.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.config import get_settings
from src.db import SessionLocal
from src.models.calendar_event import CalendarEvent
from src.models.connection import Connection
from src.models.reminder import Reminder
from src.services import calendar_cache
from src.services.calendar_auto_refresh import find_due_connections, refresh_due_calendars

_created_user_ids: set[str] = set()


@pytest.fixture(autouse=True)
def _bat_lam_moi_nen(monkeypatch):
    """Công tắc tổng mặc định TẮT ở production nên test phải bật tường minh."""
    settings = get_settings()
    monkeypatch.setattr(settings, "calendar_auto_refresh_enabled", True)
    _created_user_ids.clear()
    yield
    with SessionLocal() as db:
        if _created_user_ids:
            db.query(Reminder).filter(Reminder.user_id.in_(_created_user_ids)).delete(synchronize_session=False)
            db.query(CalendarEvent).filter(CalendarEvent.user_id.in_(_created_user_ids)).delete(
                synchronize_session=False
            )
            db.query(Connection).filter(Connection.user_id.in_(_created_user_ids)).delete(synchronize_session=False)
            db.commit()
    _created_user_ids.clear()
    get_settings.cache_clear()


def _make_user_id() -> str:
    user_id = f"cal-refresh-{uuid.uuid4().hex[:12]}"
    _created_user_ids.add(user_id)
    return user_id


def _make_connection(db, user_id: str, *, status: str = "connected_ready") -> Connection:
    connection = Connection(user_id=user_id, provider="google", status=status, scopes="")
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def _make_event(db, user_id: str, *, synced_at: datetime, event_id: str = "evt-1") -> CalendarEvent:
    row = CalendarEvent(
        user_id=user_id,
        calendar_id="primary",
        event_id=event_id,
        title="Workshop 08",
        description="",
        starts_at=datetime.now(UTC) + timedelta(days=1),
        ends_at=datetime.now(UTC) + timedelta(days=1, hours=2),
        all_day=False,
        status="active",
        deep_link="https://calendar.google.com/evt-1",
        payload={},
        synced_at=synced_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TestChonUserToiHan:
    def test_chua_tung_dong_bo_thi_toi_han_ngay(self):
        with SessionLocal() as db:
            user_id = _make_user_id()
            _make_connection(db, user_id)

            due = find_due_connections(db)
            assert user_id in {str(c.user_id) for c in due}

    def test_vua_dong_bo_xong_thi_chua_toi_han(self):
        with SessionLocal() as db:
            user_id = _make_user_id()
            _make_connection(db, user_id)
            _make_event(db, user_id, synced_at=datetime.now(UTC))

            assert user_id not in {str(c.user_id) for c in find_due_connections(db)}

    def test_dong_bo_qua_lau_thi_toi_han_lai(self):
        with SessionLocal() as db:
            user_id = _make_user_id()
            _make_connection(db, user_id)
            qua_han = datetime.now(UTC) - timedelta(
                minutes=get_settings().calendar_auto_refresh_interval_minutes + 10
            )
            _make_event(db, user_id, synced_at=qua_han)

            assert user_id in {str(c.user_id) for c in find_due_connections(db)}

    @pytest.mark.parametrize("status", ["disconnected", "error", "expired", "revoked"])
    def test_ket_noi_da_chet_khong_bao_gio_bi_cham_toi(self, status):
        """Người dùng đã gỡ kết nối thì hệ thống không được gọi Google thay họ."""
        with SessionLocal() as db:
            user_id = _make_user_id()
            _make_connection(db, user_id, status=status)

            assert user_id not in {str(c.user_id) for c in find_due_connections(db)}


class TestVongQuet:
    @pytest.mark.asyncio
    async def test_cong_tac_tat_thi_khong_lam_gi(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "calendar_auto_refresh_enabled", False)
        goi = []
        monkeypatch.setattr(
            "src.services.calendar_auto_refresh.calendar_cache.refresh_window",
            lambda *a, **k: goi.append(1),
        )
        with SessionLocal() as db:
            _make_connection(db, _make_user_id())
            assert await refresh_due_calendars(db) == 0
        assert goi == []

    @pytest.mark.asyncio
    async def test_mot_user_hong_khong_chan_nhung_user_con_lai(self, monkeypatch):
        """Lỗi của một người không được biến thành lỗi của cả hệ thống."""
        hong = _make_user_id()

        async def refresh_gia(db, *, user_id, connection, time_from, time_to):
            if user_id == hong:
                raise RuntimeError("token hết hạn")
            return {"calendars": [], "failed_calendars": [], "synced_count": 0}

        monkeypatch.setattr("src.services.calendar_auto_refresh.calendar_cache.refresh_window", refresh_gia)

        with SessionLocal() as db:
            _make_connection(db, hong)
            _make_connection(db, _make_user_id())
            _make_connection(db, _make_user_id())

            da_lam = await refresh_due_calendars(db)

        # 3 người tới hạn, 1 hỏng -> vẫn phải xử xong 2 người còn lại.
        assert da_lam >= 2

    @pytest.mark.asyncio
    async def test_cat_theo_tran_moi_vong_quet(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "calendar_auto_refresh_max_users_per_tick", 2)

        async def refresh_gia(db, **kwargs):
            return {"calendars": [], "failed_calendars": [], "synced_count": 0}

        monkeypatch.setattr("src.services.calendar_auto_refresh.calendar_cache.refresh_window", refresh_gia)

        with SessionLocal() as db:
            for _ in range(4):
                _make_connection(db, _make_user_id())

            assert await refresh_due_calendars(db) == 2


class TestThongBaoLichDoi:
    def test_doi_gio_sinh_dung_mot_thong_bao(self):
        with SessionLocal() as db:
            user_id = _make_user_id()
            row = _make_event(db, user_id, synced_at=datetime.now(UTC))
            gio_moi = row.starts_at + timedelta(hours=3)

            calendar_cache.upsert_event(
                db,
                user_id=user_id,
                calendar_id="primary",
                raw_event={
                    "id": "evt-1",
                    "summary": "Workshop 08",
                    "start": {"dateTime": gio_moi.isoformat()},
                    "end": {"dateTime": (gio_moi + timedelta(hours=2)).isoformat()},
                },
            )
            db.commit()

            thong_bao = db.query(Reminder).filter(
                Reminder.user_id == user_id, Reminder.kind == "calendar_changed"
            ).all()
            assert len(thong_bao) == 1
            assert thong_bao[0].payload["change"] == "time_changed"
            # Giờ cũ phải còn trong payload, nếu không người dùng không biết
            # buổi này đã dời từ đâu sang đâu.
            assert thong_bao[0].payload["previousStartsAt"] is not None

    def test_huy_su_kien_sinh_thong_bao_va_giu_gio_cu(self):
        with SessionLocal() as db:
            user_id = _make_user_id()
            _make_event(db, user_id, synced_at=datetime.now(UTC))

            calendar_cache.upsert_event(
                db,
                user_id=user_id,
                calendar_id="primary",
                raw_event={"id": "evt-1", "status": "cancelled"},
            )
            db.commit()

            thong_bao = db.query(Reminder).filter(
                Reminder.user_id == user_id, Reminder.kind == "calendar_changed"
            ).one()
            assert thong_bao.payload["change"] == "cancelled"
            assert thong_bao.payload["startsAt"] is not None

    def test_doi_mo_ta_khong_sinh_thong_bao(self):
        """Google chạm vào metadata khá thường xuyên — không phải tin cho người dùng."""
        with SessionLocal() as db:
            user_id = _make_user_id()
            row = _make_event(db, user_id, synced_at=datetime.now(UTC))

            calendar_cache.upsert_event(
                db,
                user_id=user_id,
                calendar_id="primary",
                raw_event={
                    "id": "evt-1",
                    "summary": "Workshop 08",
                    "description": "Nhớ mang laptop",
                    "start": {"dateTime": row.starts_at.replace(tzinfo=UTC).isoformat()},
                    "end": {"dateTime": (row.starts_at.replace(tzinfo=UTC) + timedelta(hours=2)).isoformat()},
                },
            )
            db.commit()

            assert (
                db.query(Reminder)
                .filter(Reminder.user_id == user_id, Reminder.kind == "calendar_changed")
                .count()
                == 0
            )

    def test_su_kien_da_qua_khong_sinh_thong_bao(self):
        with SessionLocal() as db:
            user_id = _make_user_id()
            row = _make_event(db, user_id, synced_at=datetime.now(UTC))
            row.starts_at = datetime.now(UTC) - timedelta(days=3)
            db.commit()

            calendar_cache.upsert_event(
                db,
                user_id=user_id,
                calendar_id="primary",
                raw_event={"id": "evt-1", "status": "cancelled"},
            )
            db.commit()

            assert (
                db.query(Reminder)
                .filter(Reminder.user_id == user_id, Reminder.kind == "calendar_changed")
                .count()
                == 0
            )

    def test_su_kien_qua_xa_khong_chen_ngang(self):
        with SessionLocal() as db:
            user_id = _make_user_id()
            row = _make_event(db, user_id, synced_at=datetime.now(UTC))
            row.starts_at = datetime.now(UTC) + timedelta(days=45)
            db.commit()

            calendar_cache.upsert_event(
                db,
                user_id=user_id,
                calendar_id="primary",
                raw_event={"id": "evt-1", "status": "cancelled"},
            )
            db.commit()

            assert (
                db.query(Reminder)
                .filter(Reminder.user_id == user_id, Reminder.kind == "calendar_changed")
                .count()
                == 0
            )

    def test_dong_bo_lai_cung_thay_doi_khong_sinh_trung(self):
        """Vòng nền chạy mỗi 30 phút — không được nhắc lại cùng một tin mỗi lượt."""
        with SessionLocal() as db:
            user_id = _make_user_id()
            row = _make_event(db, user_id, synced_at=datetime.now(UTC))
            gio_moi = row.starts_at + timedelta(hours=3)
            raw = {
                "id": "evt-1",
                "summary": "Workshop 08",
                "start": {"dateTime": gio_moi.isoformat()},
                "end": {"dateTime": (gio_moi + timedelta(hours=2)).isoformat()},
            }

            calendar_cache.upsert_event(db, user_id=user_id, calendar_id="primary", raw_event=raw)
            db.commit()
            calendar_cache.upsert_event(db, user_id=user_id, calendar_id="primary", raw_event=raw)
            db.commit()

            assert (
                db.query(Reminder)
                .filter(Reminder.user_id == user_id, Reminder.kind == "calendar_changed")
                .count()
                == 1
            )

    def test_su_kien_moi_hoan_toan_khong_sinh_thong_bao_doi_lich(self):
        """Lần đầu thấy một sự kiện không phải là 'đã đổi' — đó chỉ là nạp dữ liệu."""
        with SessionLocal() as db:
            user_id = _make_user_id()

            calendar_cache.upsert_event(
                db,
                user_id=user_id,
                calendar_id="primary",
                raw_event={
                    "id": "evt-moi",
                    "summary": "Buổi mới",
                    "start": {"dateTime": (datetime.now(UTC) + timedelta(days=2)).isoformat()},
                    "end": {"dateTime": (datetime.now(UTC) + timedelta(days=2, hours=1)).isoformat()},
                },
            )
            db.commit()

            assert (
                db.query(Reminder)
                .filter(Reminder.user_id == user_id, Reminder.kind == "calendar_changed")
                .count()
                == 0
            )
