"""Dự án — lớp sắp xếp hội thoại.

Điểm dễ sai nhất không phải CRUD mà là ranh giới sở hữu: id dự án và id hội
thoại đều do client gửi lên, nên mọi đường phải tự kiểm chủ sở hữu.
"""

import uuid

import pytest
from sqlalchemy import delete

from src.db import SessionLocal
from src.models.conversation import Conversation
from src.models.project import Project


async def _register(client) -> tuple[str, dict[str, str]]:
    email = f"test-projects-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"}
    )
    assert response.status_code == 201, response.text
    data = response.json()
    return data["userId"], {"Authorization": f"Bearer {data['accessToken']}"}


def _make_conversation(user_id: str, title: str = "Bàn về ECG") -> int:
    with SessionLocal() as db:
        row = Conversation(user_id=str(user_id), title=title)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


async def _create(client, headers, name: str, description: str = "") -> dict:
    response = await client.post(
        "/api/v1/projects", json={"name": name, "description": description}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_list_and_delete_project(client):
    _, headers = await _register(client)

    created = await _create(client, headers, "Khoá luận", "Nghiên cứu ECG")
    assert created["conversationCount"] == 0
    assert created["description"] == "Nghiên cứu ECG"

    listing = await client.get("/api/v1/projects", headers=headers)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["projects"]] == [created["id"]]

    deleted = await client.delete(f"/api/v1/projects/{created['id']}", headers=headers)
    assert deleted.status_code == 204
    listing = await client.get("/api/v1/projects", headers=headers)
    assert listing.json()["projects"] == []


@pytest.mark.asyncio
async def test_duplicate_name_is_rejected_with_a_clear_status(client):
    """409 chứ không 500 — client cần hiện thông báo ngay tại ô nhập tên."""
    _, headers = await _register(client)
    await _create(client, headers, "Trùng tên")

    again = await client.post("/api/v1/projects", json={"name": "Trùng tên"}, headers=headers)

    assert again.status_code == 409


@pytest.mark.asyncio
async def test_deleting_a_project_keeps_its_conversations(client):
    """Xoá dự án là bỏ CÁCH SẮP XẾP, không phải bỏ nội dung. Kéo theo xoá hội
    thoại thì một cú bấm nhầm làm mất trắng lịch sử trò chuyện."""
    user_id, headers = await _register(client)
    conversation_id = _make_conversation(user_id)
    project = await _create(client, headers, "Tạm")

    added = await client.post(
        f"/api/v1/projects/{project['id']}/conversations/{conversation_id}", headers=headers
    )
    assert added.status_code == 200
    assert added.json()["conversationCount"] == 1

    await client.delete(f"/api/v1/projects/{project['id']}", headers=headers)

    with SessionLocal() as db:
        row = db.get(Conversation, conversation_id)
        assert row is not None
        assert row.project_id is None


@pytest.mark.asyncio
async def test_a_project_cannot_swallow_someone_elses_conversation(client):
    """id hội thoại đi từ client lên. Không kiểm chủ sở hữu thì một tài khoản
    có thể kéo hội thoại của người khác vào dự án của mình."""
    _, headers = await _register(client)
    stranger_id, _ = await _register(client)
    stranger_conversation = _make_conversation(stranger_id, "Việc riêng người khác")
    project = await _create(client, headers, "Kẻ tò mò")

    response = await client.post(
        f"/api/v1/projects/{project['id']}/conversations/{stranger_conversation}", headers=headers
    )

    assert response.status_code == 404
    with SessionLocal() as db:
        assert db.get(Conversation, stranger_conversation).project_id is None


@pytest.mark.asyncio
async def test_touching_another_users_project_returns_404_not_403(client):
    """404 để không tiết lộ dự án đó có tồn tại hay không."""
    stranger_id, stranger_headers = await _register(client)
    stranger_project = await _create(client, stranger_headers, "Bí mật")
    _, headers = await _register(client)

    response = await client.patch(
        f"/api/v1/projects/{stranger_project['id']}", json={"name": "Chiếm"}, headers=headers
    )

    assert response.status_code == 404
    with SessionLocal() as db:
        assert db.get(Project, stranger_project["id"]).name == "Bí mật"


@pytest.mark.asyncio
async def test_removing_a_conversation_puts_it_back_in_the_unsorted_pile(client):
    user_id, headers = await _register(client)
    conversation_id = _make_conversation(user_id)
    project = await _create(client, headers, "Có rồi bỏ")
    await client.post(
        f"/api/v1/projects/{project['id']}/conversations/{conversation_id}", headers=headers
    )

    removed = await client.delete(f"/api/v1/projects/conversations/{conversation_id}", headers=headers)

    assert removed.status_code == 204
    with SessionLocal() as db:
        assert db.get(Conversation, conversation_id).project_id is None


@pytest.mark.asyncio
async def test_suggestion_is_empty_when_the_user_has_no_projects(client):
    """Không có dự án nào thì không có gì để gợi ý — rỗng là kết quả hợp lệ."""
    user_id, headers = await _register(client)
    conversation_id = _make_conversation(user_id)

    response = await client.get(f"/api/v1/projects/suggestion/{conversation_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["suggestion"] is None


@pytest.mark.asyncio
async def test_suggestion_never_breaks_the_chat_screen(client, monkeypatch):
    """Gợi ý là tiện ích phụ; hỏng nó không được chắn đường người đang trò chuyện."""
    import src.api.projects as projects_api

    user_id, headers = await _register(client)
    conversation_id = _make_conversation(user_id)
    await _create(client, headers, "Có dự án")

    def boom(*args, **kwargs):
        raise RuntimeError("mô phỏng lỗi nhúng")

    monkeypatch.setattr(projects_api, "suggest_project", boom)

    response = await client.get(f"/api/v1/projects/suggestion/{conversation_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["suggestion"] is None


@pytest.mark.asyncio
async def test_suggestion_for_someone_elses_conversation_is_refused(client):
    stranger_id, _ = await _register(client)
    stranger_conversation = _make_conversation(stranger_id)
    _, headers = await _register(client)

    response = await client.get(
        f"/api/v1/projects/suggestion/{stranger_conversation}", headers=headers
    )

    assert response.status_code == 404


def test_cleanup_stray_rows():
    """Suite này chạy trên cùng database với môi trường dev — dọn hàng do test
    tạo ra, nếu không bảng dự án của người dùng thật đầy rác 'Khoá luận'."""
    with SessionLocal() as db:
        db.execute(delete(Project).where(Project.user_id.like("%")).where(Project.name.in_(
            ["Khoá luận", "Trùng tên", "Tạm", "Kẻ tò mò", "Bí mật", "Có rồi bỏ", "Có dự án"]
        )))
        db.commit()
