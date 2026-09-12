"""Endpoint đăng ký/huỷ đăng ký Web Push — xem src/api/push.py.

Ràng buộc quan trọng nhất: endpoint của trình duyệt là bí mật giao vận, nên
biết chuỗi endpoint của người khác cũng không được đọc hay xoá được nó.
"""

import uuid

import pytest

from src.config import get_settings
from src.db import SessionLocal
from src.models.push_subscription import PushSubscription
from src.models.user import User

# Chỉ dọn đúng phần test này tạo: DB test dùng chung giữa các file.
_created_emails: set[str] = set()


@pytest.fixture(autouse=True)
def _cleanup_push_rows():
    _created_emails.clear()
    yield
    with SessionLocal() as db:
        if _created_emails:
            user_ids = [
                str(row.id) for row in db.query(User).filter(User.email.in_(_created_emails)).all()
            ]
            if user_ids:
                db.query(PushSubscription).filter(PushSubscription.user_id.in_(user_ids)).delete(
                    synchronize_session=False
                )
            db.query(User).filter(User.email.in_(_created_emails)).delete(synchronize_session=False)
            db.commit()
    _created_emails.clear()


async def _register(client) -> tuple[str, str]:
    email = f"push-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    _created_emails.add(email)
    data = response.json()
    return data["userId"], data["accessToken"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _subscribe_body(endpoint: str) -> dict:
    return {
        "endpoint": endpoint,
        "keys": {"p256dh": "p256dh-test", "auth": "auth-test"},
        "userAgent": "pytest",
    }


@pytest.mark.asyncio
async def test_public_key_tra_khoa_da_cau_hinh(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "public-key-abc")
    monkeypatch.setattr(settings, "web_push_enabled", True)

    response = await client.get("/api/v1/push/public-key")

    assert response.status_code == 200
    assert response.json() == {"publicKey": "public-key-abc", "enabled": True}


@pytest.mark.asyncio
async def test_public_key_rong_khi_chua_cau_hinh(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "")
    monkeypatch.setattr(settings, "web_push_enabled", False)

    response = await client.get("/api/v1/push/public-key")

    assert response.status_code == 200
    assert response.json() == {"publicKey": "", "enabled": False}


@pytest.mark.asyncio
async def test_subscribe_can_dang_nhap(client):
    response = await client.post("/api/v1/push/subscribe", json=_subscribe_body("https://push.test/a"))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dang_ky_roi_huy_dang_ky(client):
    user_id, token = await _register(client)
    endpoint = f"https://push.example.test/{uuid.uuid4().hex}"

    created = await client.post("/api/v1/push/subscribe", json=_subscribe_body(endpoint), headers=_auth(token))
    assert created.status_code == 201
    assert created.json() == {"subscribed": True}

    with SessionLocal() as db:
        rows = db.query(PushSubscription).filter_by(endpoint=endpoint).all()
        assert len(rows) == 1
        assert rows[0].user_id == user_id
        assert rows[0].user_agent == "pytest"

    removed = await client.request(
        "DELETE", "/api/v1/push/subscribe", json={"endpoint": endpoint}, headers=_auth(token)
    )
    assert removed.status_code == 200
    assert removed.json() == {"subscribed": False}
    with SessionLocal() as db:
        assert db.query(PushSubscription).filter_by(endpoint=endpoint).count() == 0


@pytest.mark.asyncio
async def test_dang_ky_lai_cung_endpoint_khong_sinh_dong_trung(client):
    _, token = await _register(client)
    endpoint = f"https://push.example.test/{uuid.uuid4().hex}"

    first = await client.post("/api/v1/push/subscribe", json=_subscribe_body(endpoint), headers=_auth(token))
    assert first.status_code == 201
    body = _subscribe_body(endpoint)
    body["keys"]["p256dh"] = "p256dh-moi"
    second = await client.post("/api/v1/push/subscribe", json=body, headers=_auth(token))
    assert second.status_code == 201

    with SessionLocal() as db:
        rows = db.query(PushSubscription).filter_by(endpoint=endpoint).all()
        assert len(rows) == 1
        assert rows[0].p256dh == "p256dh-moi"


@pytest.mark.asyncio
async def test_khong_huy_duoc_dang_ky_cua_nguoi_khac(client):
    owner_id, owner_token = await _register(client)
    _, attacker_token = await _register(client)
    endpoint = f"https://push.example.test/{uuid.uuid4().hex}"
    await client.post("/api/v1/push/subscribe", json=_subscribe_body(endpoint), headers=_auth(owner_token))

    response = await client.request(
        "DELETE", "/api/v1/push/subscribe", json={"endpoint": endpoint}, headers=_auth(attacker_token)
    )

    assert response.status_code == 404
    with SessionLocal() as db:
        row = db.query(PushSubscription).filter_by(endpoint=endpoint).one()
        assert row.user_id == owner_id


@pytest.mark.asyncio
async def test_dang_nhap_tai_khoan_khac_tren_cung_may_chuyen_quyen_so_huu(client):
    """Cùng một endpoint chỉ được thuộc về một người tại một thời điểm.

    Giữ chủ cũ thì người vừa đăng nhập trên máy đó sẽ thấy thông báo của người
    trước — rò dữ liệu, không phải chuyện tiện dụng.
    """
    owner_id, owner_token = await _register(client)
    second_id, second_token = await _register(client)
    endpoint = f"https://push.example.test/{uuid.uuid4().hex}"

    await client.post("/api/v1/push/subscribe", json=_subscribe_body(endpoint), headers=_auth(owner_token))
    await client.post("/api/v1/push/subscribe", json=_subscribe_body(endpoint), headers=_auth(second_token))

    with SessionLocal() as db:
        rows = db.query(PushSubscription).filter_by(endpoint=endpoint).all()
        assert len(rows) == 1
        assert rows[0].user_id == second_id
        assert rows[0].user_id != owner_id
