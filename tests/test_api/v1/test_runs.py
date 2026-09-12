import asyncio
import base64
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.api.runs import (
    _count_gmail_messages,
    _evidence_items,
    _run_payload,
    _stream_events,
    claim_next_run,
    execute_run,
)
from src.config import get_settings
from src.db import SessionLocal
from src.models.connection import Connection
from src.models.message import Message
from src.models.run_node_event import RunNodeEvent
from src.models.user import User


def test_brief_evidence_excludes_items_marked_ignore_by_filter():
    items = [
        {"id": "actionable", "importance": "important", "brief_section": "needs_action"},
        {"id": "noise", "importance": "ignore", "brief_section": "ignore"},
    ]

    assert [item["id"] for item in _evidence_items(items)] == ["actionable"]


def _unique_email() -> str:
    return f"test-runs-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _create_google_connection(user_id: str) -> int:
    db = SessionLocal()
    try:
        conn = Connection(
            user_id=user_id,
            provider="google",
            account_label="me@example.test",
            provider_user_id="me@example.test",
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        return conn.id
    finally:
        db.close()


async def _wait_background_tasks() -> None:
    # API chỉ enqueue; test chủ động mô phỏng worker riêng claim và execute.
    while True:
        with SessionLocal() as db:
            run = claim_next_run(db)
            if run is None:
                return
            payload = _run_payload(run)
            run_id, user_id = run.id, run.user_id
        await execute_run(run_id, user_id, payload)


def _run_body(connection_id: int, idempotency_key: str) -> dict:
    return {
        "sources": [{"connectionId": connection_id, "sourceId": "INBOX"}],
        "timeFrom": "2026-01-01T00:00:00Z",
        "timeTo": "2026-01-08T00:00:00Z",
        "idempotencyKey": idempotency_key,
    }


@pytest.mark.asyncio
async def test_create_run_idempotent_same_key_returns_same_run(client):
    user_id, token = await _register(client)
    connection_id = _create_google_connection(user_id)
    headers = {"Authorization": f"Bearer {token}"}
    body = _run_body(connection_id, f"key-{uuid.uuid4().hex[:8]}")

    first = await client.post("/api/v1/runs", json=body, headers=headers)
    second = await client.post("/api/v1/runs", json=body, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    await _wait_background_tasks()


@pytest.mark.asyncio
async def test_second_active_run_for_same_user_is_rejected(client):
    user_id, token = await _register(client)
    connection_id = _create_google_connection(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post(
        "/api/v1/runs",
        json=_run_body(connection_id, f"key-{uuid.uuid4().hex[:8]}"),
        headers=headers,
    )
    second = await client.post(
        "/api/v1/runs",
        json=_run_body(connection_id, f"key-{uuid.uuid4().hex[:8]}"),
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 429
    assert "Sync" in second.json()["detail"]
    await _wait_background_tasks()


@pytest.mark.asyncio
async def test_run_rejects_more_than_configured_source_limit(client):
    user_id, token = await _register(client)
    connection_id = _create_google_connection(user_id)
    body = _run_body(connection_id, f"key-{uuid.uuid4().hex[:8]}")
    body["sources"] = [
        {"connectionId": connection_id, "sourceId": f"source-{index}"}
        for index in range(get_settings().max_sync_sources + 1)
    ]

    response = await client.post("/api/v1/runs", json=body, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 422
    assert str(get_settings().max_sync_sources) in response.json()["detail"]


@pytest.mark.asyncio
async def test_sse_observes_events_written_by_separate_worker_session(client):
    user_id, token = await _register(client)
    connection_id = _create_google_connection(user_id)
    created = await client.post(
        "/api/v1/runs",
        json=_run_body(connection_id, f"key-{uuid.uuid4().hex[:8]}"),
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = created.json()["id"]
    stream = _stream_events(run_id, user_id)
    pending_event = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)

    with SessionLocal() as worker_db:
        from src.models.run import Run

        run = worker_db.get(Run, run_id)
        worker_db.add(RunNodeEvent(run_id=run_id, node="done", status="ok", count=0))
        run.status = "succeeded"
        worker_db.commit()

    frame = await asyncio.wait_for(pending_event, timeout=2)
    assert '"node": "done"' in frame
    await stream.aclose()


@pytest.mark.asyncio
async def test_get_run_belonging_to_other_user_returns_404(client):
    user_a_id, token_a = await _register(client)
    _, token_b = await _register(client)
    connection_id = _create_google_connection(user_a_id)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    created = await client.post(
        "/api/v1/runs", json=_run_body(connection_id, f"key-{uuid.uuid4().hex[:8]}"), headers=headers_a
    )
    run_id = created.json()["id"]

    response = await client.get(f"/api/v1/runs/{run_id}", headers=headers_b)
    assert response.status_code == 404

    await _wait_background_tasks()


@pytest.mark.asyncio
async def test_run_with_missing_connection_keeps_running_and_records_fetch_error(client):
    # 1 source lỗi (connection không tồn tại) không được sập cả run — fetch_node
    # bắt lỗi vào errors[], pipeline chạy hết 9 node với 0 message, run vẫn
    # "succeeded" (0 task), chỉ event "fetch" mang status=error.
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    body = _run_body(connection_id=999999, idempotency_key=f"key-{uuid.uuid4().hex[:8]}")

    created = await client.post("/api/v1/runs", json=body, headers=headers)
    run_id = created.json()["id"]

    await _wait_background_tasks()

    detail = await client.get(f"/api/v1/runs/{run_id}", headers=headers)
    assert detail.json()["status"] == "succeeded"

    events = await client.get(f"/api/v1/runs/{run_id}/events", headers=headers)
    assert events.status_code == 200
    assert '"node": "fetch"' in events.text
    assert '"status": "error"' in events.text

    brief = await client.get(f"/api/v1/runs/{run_id}/brief", headers=headers)
    assert brief.status_code == 200
    assert brief.json()["topPriority"] == []


@pytest.mark.asyncio
async def test_run_brief_requires_ownership_check_first(client):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/runs/999999/brief", headers=headers)
    assert response.status_code == 404


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def _fake_gmail_message(msg_id: str, text: str) -> dict:
    return {
        "id": msg_id,
        "threadId": f"thread-{msg_id}",
        "internalDate": str(int(datetime.now(UTC).timestamp() * 1000)),
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": "From", "value": "Sender <sender@example.test>"}],
            "body": {"data": _b64(text)},
        },
    }


@pytest.mark.asyncio
async def test_run_full_flow_with_mock_llm_and_fake_fetch_succeeds(client):
    get_settings.cache_clear()
    try:
        with patch.dict("os.environ", {"MOCK_LLM": "true"}):
            get_settings.cache_clear()

            user_id, token = await _register(client)
            connection_id = _create_google_connection(user_id)
            headers = {"Authorization": f"Bearer {token}"}
            body = _run_body(connection_id, f"key-{uuid.uuid4().hex[:8]}")

            fake_messages = [_fake_gmail_message("m1", "Vui lòng nộp báo cáo trước thứ Sáu 9:00am ICT.")]

            with patch(
                "src.connectors.gmail.GmailConnector.fetch_range",
                new=AsyncMock(return_value=fake_messages),
            ):
                created = await client.post("/api/v1/runs", json=body, headers=headers)
                run_id = created.json()["id"]
                await _wait_background_tasks()

            detail = await client.get(f"/api/v1/runs/{run_id}", headers=headers)
            assert detail.json()["status"] == "succeeded"

            events = await client.get(f"/api/v1/runs/{run_id}/events", headers=headers)
            assert '"node": "persist"' in events.text or "persist" in events.text
            assert '"node": "done"' in events.text or "done" in events.text

            brief = await client.get(f"/api/v1/runs/{run_id}/brief", headers=headers)
            assert brief.status_code == 200
            assert brief.json()["summary"]
    finally:
        get_settings.cache_clear()


def test_gmail_message_count_excludes_calendar_events_on_shared_google_connection():
    user_id = f"count-user-{uuid.uuid4().hex}"
    with SessionLocal() as db:
        connection = Connection(user_id=user_id, provider="google")
        db.add(connection)
        db.flush()
        common = {
            "user_id": user_id,
            "connection_id": connection.id,
            "source_id": "primary",
            "text": "event",
            "sent_at": datetime.now(UTC),
            "deep_link": "https://calendar.google.com/",
        }
        db.add_all(
            [
                Message(provider="google", external_id=f"mail-{uuid.uuid4().hex}", **common),
                Message(
                    provider="google_calendar",
                    external_id=f"event-{uuid.uuid4().hex}",
                    **common,
                ),
            ]
        )
        db.commit()

        assert _count_gmail_messages(db, connection.id) == 1


@pytest.mark.asyncio
async def test_run_limits_endpoint_reports_the_same_cap_the_api_enforces(client):
    """FE chặn tick nguồn dựa trên endpoint này, nên nó phải khớp luật thật.

    Lệch một con số là người dùng tick tới hạn FE cho phép rồi vẫn ăn 422.
    """
    _, token = await _register(client)

    response = await client.get("/api/v1/runs/limits", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    settings = get_settings()
    assert body["maxSyncSources"] == settings.max_sync_sources
    assert body["maxSyncRangeDays"] == settings.max_sync_range_days
    assert body["autoSyncIntervalMinutes"] == settings.auto_sync_interval_minutes


@pytest.mark.asyncio
async def test_run_limits_requires_authentication(client):
    """Hạn mức là cấu hình vận hành, không phát cho khách vãng lai."""
    response = await client.get("/api/v1/runs/limits")

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_run_limits_reports_auto_sync_off_when_user_opted_out(client, monkeypatch):
    """Công tắc tổng bật nhưng user tự tắt -> FE phải thấy TẮT, không hiện băng."""
    monkeypatch.setattr(get_settings(), "auto_sync_enabled", True)
    user_id, token = await _register(client)
    with SessionLocal() as db:
        db.get(User, int(user_id)).auto_sync_enabled = False
        db.commit()

    response = await client.get("/api/v1/runs/limits", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["autoSyncEnabled"] is False


@pytest.mark.asyncio
async def test_auto_sync_preference_requires_authentication(client):
    get_response = await client.get("/api/v1/runs/auto-sync-preference")
    patch_response = await client.patch("/api/v1/runs/auto-sync-preference", json={"autoSyncEnabled": False})

    assert get_response.status_code in (401, 403)
    assert patch_response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_auto_sync_preference_persists_only_the_callers_choice(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "auto_sync_enabled", True)
    first_user_id, first_token = await _register(client)
    second_user_id, second_token = await _register(client)

    initial = await client.get(
        "/api/v1/runs/auto-sync-preference",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert initial.status_code == 200
    assert initial.json()["userAutoSyncEnabled"] is True
    assert initial.json()["autoSyncEnabled"] is True

    response = await client.patch(
        "/api/v1/runs/auto-sync-preference",
        json={"autoSyncEnabled": False},
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert response.status_code == 200
    assert response.json()["userAutoSyncEnabled"] is False
    assert response.json()["autoSyncEnabled"] is False

    second_response = await client.get(
        "/api/v1/runs/auto-sync-preference",
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert second_response.status_code == 200
    assert second_response.json()["userAutoSyncEnabled"] is True
    assert second_response.json()["autoSyncEnabled"] is True

    with SessionLocal() as db:
        assert db.get(User, int(first_user_id)).auto_sync_enabled is False
        assert db.get(User, int(second_user_id)).auto_sync_enabled is True


@pytest.mark.asyncio
async def test_auto_sync_preference_rejects_missing_or_unknown_fields(client):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    for body in ({}, {"userId": 999, "autoSyncEnabled": False}):
        response = await client.patch("/api/v1/runs/auto-sync-preference", json=body, headers=headers)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_auto_sync_preference_reports_saved_choice_when_global_scheduler_is_off(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "auto_sync_enabled", False)
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        "/api/v1/runs/auto-sync-preference",
        json={"autoSyncEnabled": True},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["userAutoSyncEnabled"] is True
    assert response.json()["autoSyncEnabled"] is False
    assert response.json()["autoSyncIntervalMinutes"] == get_settings().auto_sync_interval_minutes


@pytest.mark.asyncio
async def test_run_at_exactly_the_source_limit_is_accepted(client):
    """Biên trên phải chạy được — nếu không thì FE cho tick tới hạn rồi vẫn hỏng."""
    user_id, token = await _register(client)
    connection_id = _create_google_connection(user_id)
    body = _run_body(connection_id, f"key-{uuid.uuid4().hex[:8]}")
    body["sources"] = [
        {"connectionId": connection_id, "sourceId": f"source-{index}"}
        for index in range(get_settings().max_sync_sources)
    ]

    response = await client.post("/api/v1/runs", json=body, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    await _wait_background_tasks()


@pytest.mark.asyncio
async def test_run_language_defaults_to_vi_when_not_provided(client):
    from src.models.run import Run

    user_id, token = await _register(client)
    connection_id = _create_google_connection(user_id)
    body = _run_body(connection_id, f"key-{uuid.uuid4().hex[:8]}")
    assert "language" not in body

    created = await client.post("/api/v1/runs", json=body, headers={"Authorization": f"Bearer {token}"})
    run_id = created.json()["id"]

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.language == "vi"
    await _wait_background_tasks()


@pytest.mark.asyncio
async def test_run_stores_explicit_language_from_request(client):
    from src.models.run import Run

    user_id, token = await _register(client)
    connection_id = _create_google_connection(user_id)
    body = _run_body(connection_id, f"key-{uuid.uuid4().hex[:8]}")
    body["language"] = "en"

    created = await client.post("/api/v1/runs", json=body, headers={"Authorization": f"Bearer {token}"})
    run_id = created.json()["id"]

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.language == "en"
    await _wait_background_tasks()


def test_run_payload_reconstructs_language_from_persisted_run():
    """`_run_payload` là chỗ worker dựng lại RunCreateRequest từ Run đã lưu
    khi dequeue — quên field này thì language luôn rơi về default 'vi' dù
    Run.language đã lưu đúng giá trị khác."""
    from datetime import UTC
    from datetime import datetime as dt

    from src.models.run import Run

    run = Run(
        user_id=1,
        sources=[{"connectionId": 1, "sourceId": "INBOX"}],
        range_from=dt(2026, 1, 1, tzinfo=UTC),
        range_to=dt(2026, 1, 2, tzinfo=UTC),
        idempotency_key="test-key",
        timezone="Asia/Ho_Chi_Minh",
        language="en",
        mode="task_extraction",
    )

    payload = _run_payload(run)

    assert payload.language == "en"
