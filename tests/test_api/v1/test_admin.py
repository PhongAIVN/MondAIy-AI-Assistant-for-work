"""Kiểm tra quyền và ranh giới dữ liệu của admin portal.

Trọng tâm không phải "endpoint trả 200" mà hai thứ dễ hỏng âm thầm: người không
phải admin có vào được không, và response có rò nội dung cá nhân ra không (PRD
§4.4 và §5).
"""

import uuid

import pytest

from src.db import SessionLocal
from src.models.evidence import SourceScope
from src.models.source_scope_access import SourceScopeAccess
from src.models.user import User

ADMIN_PREFIX = "/api/v1/admin"


def _unique_email() -> str:
    return f"admin-test-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client, email: str | None = None) -> tuple[str, str]:
    """Đăng ký một tài khoản mới, trả về (user_id, access_token)."""
    email = email or _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201, response.text
    data = response.json()
    return data["userId"], data["accessToken"]


def _promote(user_id: str, role: str = "admin") -> None:
    """Nâng quyền thẳng trong DB — API không cho tự nâng, và đó là chủ ý."""
    db = SessionLocal()
    try:
        user = db.get(User, int(user_id))
        user.role = role
        db.commit()
    finally:
        db.close()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_khong_co_token_thi_bi_tu_choi(client):
    response = await client.get(f"{ADMIN_PREFIX}/overview")
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["/overview", "/users", "/sources", "/runs", "/audit", "/telemetry"],
)
async def test_participant_khong_vao_duoc_bat_ky_endpoint_admin_nao(client, path):
    """Frontend chặn /admin bằng điều hướng, nhưng gọi thẳng API vẫn phải 403."""
    _, token = await _register(client)
    response = await client.get(f"{ADMIN_PREFIX}{path}", headers=_auth(token))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mentor_cung_khong_duoc_coi_la_admin(client):
    user_id, token = await _register(client)
    _promote(user_id, "mentor")
    response = await client.get(f"{ADMIN_PREFIX}/overview", headers=_auth(token))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_xem_duoc_overview(client):
    user_id, token = await _register(client)
    _promote(user_id)
    response = await client.get(f"{ADMIN_PREFIX}/overview", headers=_auth(token))
    assert response.status_code == 200
    data = response.json()
    assert data["totalUsers"] >= 1
    assert data["roles"]["admin"] >= 1
    assert 0 <= data["sourceHealthPercent"] <= 100
    assert data["windowDays"] == 7


@pytest.mark.asyncio
async def test_tai_khoan_bi_khoa_mat_quyen_ngay_du_token_con_han(client):
    """Token còn hạn không đủ — quyền phải đọc lại từ DB mỗi request."""
    user_id, token = await _register(client)
    _promote(user_id)
    assert (await client.get(f"{ADMIN_PREFIX}/overview", headers=_auth(token))).status_code == 200

    db = SessionLocal()
    try:
        user = db.get(User, int(user_id))
        user.is_active = False
        db.commit()
    finally:
        db.close()

    response = await client.get(f"{ADMIN_PREFIX}/overview", headers=_auth(token))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dang_ky_khong_tu_dat_duoc_role_admin(client):
    """Gửi kèm role trong payload đăng ký không được có tác dụng gì."""
    email = _unique_email()
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "role": "admin"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "participant"

    token = response.json()["accessToken"]
    assert (await client.get(f"{ADMIN_PREFIX}/overview", headers=_auth(token))).status_code == 403


@pytest.mark.asyncio
async def test_doi_role_ghi_audit_va_co_hieu_luc(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)
    target_id, target_token = await _register(client)

    response = await client.patch(
        f"{ADMIN_PREFIX}/users/{target_id}",
        json={"role": "mentor"},
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["role"] == "mentor"

    # /auth/me phải phản ánh role mới, nếu không frontend vẫn dựng nav cũ.
    me = await client.get("/api/v1/auth/me", headers=_auth(target_token))
    assert me.json()["role"] == "mentor"

    audit = await client.get(f"{ADMIN_PREFIX}/audit?action=admin_user_updated", headers=_auth(admin_token))
    assert audit.status_code == 200
    entry = next(row for row in audit.json()["items"] if row["objectId"] == str(target_id))
    assert entry["actorId"] == str(admin_id)
    assert entry["details"]["before"]["role"] == "participant"
    assert entry["details"]["after"]["role"] == "mentor"


@pytest.mark.asyncio
async def test_admin_gan_cohort_cho_user_va_list_phan_anh_gia_tri_moi(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)
    target_id, _ = await _register(client)

    response = await client.patch(
        f"{ADMIN_PREFIX}/users/{target_id}",
        json={"programCohortSlug": " Cohort-IV "},
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["programCohortSlug"] == "cohort-iv"

    listed = await client.get(f"{ADMIN_PREFIX}/users", headers=_auth(admin_token))
    row = next(item for item in listed.json()["items"] if item["id"] == str(target_id))
    assert row["programCohortSlug"] == "cohort-iv"


@pytest.mark.asyncio
async def test_admin_khong_the_gan_cohort_slug_khong_hop_le(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)
    target_id, _ = await _register(client)

    response = await client.patch(
        f"{ADMIN_PREFIX}/users/{target_id}",
        json={"programCohortSlug": "cohort iv!"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_khong_tu_ha_quyen_chinh_minh(client):
    """Tự hạ quyền là cách nhanh nhất để khoá cả nhóm ra khỏi portal."""
    admin_id, admin_token = await _register(client)
    _promote(admin_id)

    response = await client.patch(
        f"{ADMIN_PREFIX}/users/{admin_id}",
        json={"role": "participant"},
        headers=_auth(admin_token),
    )
    assert response.status_code == 400

    response = await client.patch(
        f"{ADMIN_PREFIX}/users/{admin_id}",
        json={"isActive": False},
        headers=_auth(admin_token),
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_patch_user_khong_ton_tai_tra_404(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)
    response = await client.patch(f"{ADMIN_PREFIX}/users/99999999", json={"role": "mentor"}, headers=_auth(admin_token))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_replace_user_source_scope_grants(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)
    target_id, target_token = await _register(client)
    del target_token

    db = SessionLocal()
    try:
        first = SourceScope(provider="discord", external_id=f"scope-{uuid.uuid4().hex}", name="Announcements")
        second = SourceScope(provider="discord", external_id=f"scope-{uuid.uuid4().hex}", name="Tasks")
        db.add_all([first, second])
        db.commit()
        first_id, second_id = first.id, second.id
    finally:
        db.close()

    response = await client.put(
        f"{ADMIN_PREFIX}/users/{target_id}/source-scopes",
        json={"scopeIds": [first_id, second_id]},
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["scopeIds"] == [first_id, second_id]

    response = await client.put(
        f"{ADMIN_PREFIX}/users/{target_id}/source-scopes",
        json={"scopeIds": [second_id]},
        headers=_auth(admin_token),
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        grants = db.query(SourceScopeAccess).filter_by(user_id=target_id).all()
        active = {grant.scope_id for grant in grants if grant.status == "confirmed" and grant.valid_to is None}
        assert active == {second_id}
        assert any(grant.scope_id == first_id and grant.status == "revoked" for grant in grants)
    finally:
        db.close()


@pytest.mark.asyncio
async def test_patch_user_khong_co_truong_nao_tra_422(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)
    target_id, _ = await _register(client)
    response = await client.patch(f"{ADMIN_PREFIX}/users/{target_id}", json={}, headers=_auth(admin_token))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_danh_sach_user_loc_duoc_va_khong_lo_password_hash(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)
    target_email = _unique_email()
    await _register(client, target_email)

    response = await client.get(f"{ADMIN_PREFIX}/users?search={target_email}", headers=_auth(admin_token))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    row = data["items"][0]
    assert row["email"] == target_email
    assert "passwordHash" not in row
    assert "password_hash" not in row


@pytest.mark.asyncio
async def test_loc_theo_role_chi_tra_dung_role_do(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)

    response = await client.get(f"{ADMIN_PREFIX}/users?role=admin", headers=_auth(admin_token))
    assert response.status_code == 200
    assert all(row["role"] == "admin" for row in response.json()["items"])


@pytest.mark.asyncio
@pytest.mark.parametrize("level", ["A", "B", "C"])
async def test_loc_theo_phan_loai_quyen_chuong_trinh(client, level):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)
    matching_id, _ = await _register(client)
    other_id, _ = await _register(client)

    db = SessionLocal()
    try:
        db.get(User, int(matching_id)).program_access_level = level
        db.get(User, int(other_id)).program_access_level = "B" if level != "B" else "C"
        db.commit()
    finally:
        db.close()

    response = await client.get(
        f"{ADMIN_PREFIX}/users?programAccessLevel={level}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    rows = response.json()["items"]
    assert rows
    assert all(row["programAccessLevel"] == level for row in rows)
    assert any(row["id"] == matching_id for row in rows)


@pytest.mark.asyncio
async def test_loc_ket_hop_role_va_phan_loai_quyen_chuong_trinh(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)
    target_id, _ = await _register(client)
    db = SessionLocal()
    try:
        target = db.get(User, int(target_id))
        target.role = "mentor"
        target.program_access_level = "A"
        db.commit()
    finally:
        db.close()

    response = await client.get(
        f"{ADMIN_PREFIX}/users?role=mentor&programAccessLevel=A",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    rows = response.json()["items"]
    assert rows
    assert all(row["role"] == "mentor" and row["programAccessLevel"] == "A" for row in rows)
    assert any(row["id"] == target_id for row in rows)


@pytest.mark.asyncio
async def test_loc_phan_loai_quyen_chuong_trinh_khong_hop_le_tra_422(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)
    response = await client.get(
        f"{ADMIN_PREFIX}/users?programAccessLevel=member",
        headers=_auth(admin_token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sources_runs_telemetry_tra_dung_cau_truc(client):
    admin_id, admin_token = await _register(client)
    _promote(admin_id)

    sources = await client.get(f"{ADMIN_PREFIX}/sources", headers=_auth(admin_token))
    assert sources.status_code == 200
    assert {"providers", "connections"} <= set(sources.json())

    runs = await client.get(f"{ADMIN_PREFIX}/runs", headers=_auth(admin_token))
    assert runs.status_code == 200
    assert {"items", "total"} <= set(runs.json())

    telemetry = await client.get(f"{ADMIN_PREFIX}/telemetry?days=30", headers=_auth(admin_token))
    assert telemetry.status_code == 200
    body = telemetry.json()
    assert body["windowDays"] == 30
    # Số đếm thôi — không trả `attributes` ra ngoài, vì đó là chỗ duy nhất trong
    # bảng telemetry còn có thể dính dữ liệu người dùng.
    assert all(set(row) == {"name", "count", "avgDurationMs"} for row in body["events"])


@pytest.mark.asyncio
async def test_khong_endpoint_admin_nao_tra_noi_dung_ca_nhan(client):
    """Chốt chặn theo PRD §5: response không được chứa nội dung gốc.

    Test này cố ý so theo tên trường chứ không theo giá trị — thêm một trường
    `summary` hay `title` vào response admin là hỏng ngay ở đây, kể cả khi lúc
    chạy test bảng còn rỗng nên chưa có dữ liệu thật để rò.
    """
    admin_id, admin_token = await _register(client)
    _promote(admin_id)

    cam = {"summary", "title", "detail", "quote", "content", "message", "snippet", "answer", "body"}
    for path in ["/overview", "/users", "/sources", "/runs", "/audit", "/telemetry"]:
        response = await client.get(f"{ADMIN_PREFIX}{path}", headers=_auth(admin_token))
        assert response.status_code == 200
        assert not (cam & _thu_thap_khoa(response.json())), f"{path} lộ trường nội dung"


def _thu_thap_khoa(payload) -> set[str]:
    """Gom mọi khoá xuất hiện ở bất kỳ độ sâu nào của response."""
    keys: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(key)
            keys |= _thu_thap_khoa(value)
    elif isinstance(payload, list):
        for item in payload:
            keys |= _thu_thap_khoa(item)
    return keys


@pytest.mark.asyncio
async def test_khoa_tai_khoan_admin_khac_van_con_nguoi_vao_duoc_portal(client):
    """Sau mọi thao tác trên người khác, người gọi vẫn là admin.

    Đây là lý do không cần chốt riêng "phải còn ít nhất một quản trị viên": tự
    đổi role và tự khoá mình đã bị chặn, nên người gọi luôn còn quyền.
    """
    actor_id, actor_token = await _register(client)
    _promote(actor_id)
    other_id, _ = await _register(client)
    _promote(other_id)

    response = await client.patch(
        f"{ADMIN_PREFIX}/users/{other_id}",
        json={"role": "participant", "isActive": False},
        headers=_auth(actor_token),
    )
    assert response.status_code == 200
    assert response.json()["isActive"] is False

    still_admin = await client.get(f"{ADMIN_PREFIX}/overview", headers=_auth(actor_token))
    assert still_admin.status_code == 200
