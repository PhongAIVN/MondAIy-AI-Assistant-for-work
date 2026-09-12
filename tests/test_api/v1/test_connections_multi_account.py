import uuid

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from src import db as db_module
from src.api.connections import _upsert_connection
from src.db import SessionLocal
from src.models.connection import Connection
from src.services.connections import google


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


async def _register(client) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": _email("multi-google"), "password": "correct-horse-1"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["userId"], body["accessToken"]


def _seed_google(user_id: str, email: str, token: str) -> Connection:
    db = SessionLocal()
    try:
        row = _upsert_connection(
            db,
            user_id=user_id,
            provider="google",
            account_label=email,
            provider_user_id=email,
            token_data={"access_token": token, "refresh_token": f"refresh-{token}"},
        )
        return row
    finally:
        db.close()


@pytest.mark.asyncio
async def test_list_connections_returns_all_google_accounts_with_ids(client):
    user_id, token = await _register(client)
    first = _seed_google(user_id, "first@example.com", "token-first")
    second = _seed_google(user_id, "second@example.com", "token-second")

    response = await client.get("/api/v1/connections", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text
    google_rows = [item for item in response.json()["connections"] if item["provider"] == "google"]
    assert {item["id"] for item in google_rows} == {first.id, second.id}
    assert {item["accountLabel"] for item in google_rows} == {"first@example.com", "second@example.com"}
    assert any(item["provider"] == "discord" and item["connected"] is False for item in response.json()["connections"])


def test_google_upsert_updates_identity_but_inserts_different_account():
    user_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        first = _upsert_connection(
            db,
            user_id=user_id,
            provider="google",
            account_label="first@example.com",
            provider_user_id="first@example.com",
            token_data={"access_token": "first-token"},
        )
        updated = _upsert_connection(
            db,
            user_id=user_id,
            provider="google",
            account_label="first-renamed@example.com",
            provider_user_id="FIRST@EXAMPLE.COM",
            token_data={"access_token": "first-token-new"},
        )
        second = _upsert_connection(
            db,
            user_id=user_id,
            provider="google",
            account_label="second@example.com",
            provider_user_id="second@example.com",
            token_data={"access_token": "second-token"},
        )

        assert updated.id == first.id
        assert second.id != first.id
        assert len(db.scalars(select(Connection).where(Connection.user_id == user_id)).all()) == 2
    finally:
        db.close()


@pytest.mark.asyncio
async def test_disconnect_by_connection_id_only_deletes_target_account(client, monkeypatch):
    user_id, token = await _register(client)
    first = _seed_google(user_id, "first@example.com", "token-first")
    second = _seed_google(user_id, "second@example.com", "token-second")
    revoked: list[str] = []

    async def fake_revoke(access_token: str) -> None:
        revoked.append(access_token)

    monkeypatch.setattr(google, "revoke_token", fake_revoke)
    response = await client.post(
        f"/api/v1/connections/account/{first.id}/disconnect",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204, response.text
    assert revoked == ["token-first"]
    db = SessionLocal()
    try:
        remaining = db.scalars(select(Connection).where(Connection.user_id == user_id)).all()
        assert [row.id for row in remaining] == [second.id]
    finally:
        db.close()


@pytest.mark.asyncio
async def test_disconnect_by_connection_id_rejects_another_users_account(client):
    first_user_id, first_token = await _register(client)
    second_user_id, _ = await _register(client)
    row = _seed_google(second_user_id, "other@example.com", "other-token")

    response = await client.post(
        f"/api/v1/connections/account/{row.id}/disconnect",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert response.status_code == 404
    db = SessionLocal()
    try:
        assert db.get(Connection, row.id) is not None
    finally:
        db.close()


def test_runtime_migration_preserves_rows_and_allows_multiple_google_accounts(monkeypatch):
    old_engine = create_engine("sqlite:///:memory:")
    with old_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE connections ("
                "id INTEGER PRIMARY KEY, user_id VARCHAR(128) NOT NULL, provider VARCHAR(32) NOT NULL, "
                "account_label VARCHAR(255), provider_user_id VARCHAR(128), external_site_id VARCHAR(255), "
                "access_token_encrypted TEXT, refresh_token_encrypted TEXT, scopes VARCHAR(512), "
                "expires_at DATETIME, connected_at DATETIME NOT NULL, status VARCHAR(32), "
                "initial_sync_completed BOOLEAN, last_synced_at DATETIME, email_count INTEGER, "
                "last_error VARCHAR(1024), CONSTRAINT uq_connection_user_provider UNIQUE (user_id, provider))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO connections "
                "(id, user_id, provider, account_label, provider_user_id, connected_at) "
                "VALUES (1, 'user-1', 'google', 'old@example.com', 'old@example.com', CURRENT_TIMESTAMP)"
            )
        )
    monkeypatch.setattr(db_module, "engine", old_engine)

    db_module._ensure_connection_account_constraints()
    db_module._ensure_connection_account_constraints()

    with old_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO connections "
                "(id, user_id, provider, account_label, provider_user_id, connected_at) "
                "VALUES (2, 'user-1', 'google', 'new@example.com', 'new@example.com', CURRENT_TIMESTAMP)"
            )
        )
    with old_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO connections "
                "(id, user_id, provider, account_label, connected_at) "
                "VALUES (3, 'user-1', 'discord', 'discord', CURRENT_TIMESTAMP)"
            )
        )
    with pytest.raises(IntegrityError):
        with old_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO connections "
                    "(id, user_id, provider, account_label, connected_at) "
                    "VALUES (4, 'user-1', 'discord', 'duplicate', CURRENT_TIMESTAMP)"
                )
            )
    with old_engine.connect() as connection:
        rows = connection.execute(text("SELECT id, account_label FROM connections ORDER BY id")).all()

    assert rows == [(1, "old@example.com"), (2, "new@example.com"), (3, "discord")]
    assert "uq_connection_user_provider" not in {
        item["name"] for item in inspect(old_engine).get_unique_constraints("connections")
    }
