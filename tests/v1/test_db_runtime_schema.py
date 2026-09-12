import json

from sqlalchemy import create_engine, inspect, text

from src import db as db_module


def test_runtime_schema_adds_missing_pipeline_identity_columns(monkeypatch):
    old_engine = create_engine("sqlite:///:memory:")
    with old_engine.begin() as connection:
        connection.execute(text("CREATE TABLE pipeline_resolved_items (id INTEGER PRIMARY KEY)"))
    monkeypatch.setattr(db_module, "engine", old_engine)

    db_module._ensure_pipeline_resolved_columns()
    # Chạy lần hai phải no-op để startup/redeploy idempotent.
    db_module._ensure_pipeline_resolved_columns()

    columns = {column["name"] for column in inspect(old_engine).get_columns("pipeline_resolved_items")}
    assert {"assignee", "assignee_ambiguous"}.issubset(columns)


def test_runtime_schema_adds_google_avatar_to_existing_users(monkeypatch):
    old_engine = create_engine("sqlite:///:memory:")
    with old_engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255), password_hash VARCHAR(255))")
        )
    monkeypatch.setattr(db_module, "engine", old_engine)

    db_module._ensure_user_role_columns()
    db_module._ensure_user_role_columns()

    columns = {column["name"] for column in inspect(old_engine).get_columns("users")}
    assert "avatar_url" in columns


def test_runtime_schema_adds_daily_feedback_bonus_to_existing_users(monkeypatch):
    old_engine = create_engine("sqlite:///:memory:")
    with old_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, llm_quota_day VARCHAR(10), "
                "llm_questions_used INTEGER DEFAULT 0)"
            )
        )
    monkeypatch.setattr(db_module, "engine", old_engine)

    db_module._ensure_run_queue_schema()
    db_module._ensure_run_queue_schema()

    columns = {column["name"] for column in inspect(old_engine).get_columns("users")}
    assert "llm_bonus_questions" in columns


def test_runtime_schema_adds_usage_quota_columns_to_existing_users(monkeypatch):
    old_engine = create_engine("sqlite:///:memory:")
    with old_engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255))"))
    monkeypatch.setattr(db_module, "engine", old_engine)

    db_module._ensure_user_role_columns()

    columns = {column["name"] for column in inspect(old_engine).get_columns("users")}
    assert {
        "meeting_summary_quota_day",
        "meeting_summaries_used",
        "feedback_attempts",
        "feedback_quality_day",
        "feedback_cooldown_until",
    }.issubset(columns)


def test_runtime_schema_upgrades_existing_notification_preferences(monkeypatch):
    """create_all không nâng bảng cũ; startup phải thêm cột và giữ kênh bật."""
    old_engine = create_engine("sqlite:///:memory:")
    with old_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE notification_preferences ("
                "id INTEGER PRIMARY KEY, user_id VARCHAR(128), timezone VARCHAR(64), "
                "quiet_hours_start INTEGER, quiet_hours_end INTEGER, hourly_cap INTEGER, "
                "batch_window_minutes INTEGER)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO notification_preferences "
                "(id, user_id, timezone, quiet_hours_start, quiet_hours_end, hourly_cap, batch_window_minutes) "
                "VALUES (1, 'existing-user', 'Asia/Ho_Chi_Minh', 22, 7, 5, 15)"
            )
        )
    monkeypatch.setattr(db_module, "engine", old_engine)

    db_module._ensure_notification_preference_columns()
    db_module._ensure_notification_preference_columns()

    columns = {column["name"] for column in inspect(old_engine).get_columns("notification_preferences")}
    assert {
        "daily_brief_hour",
        "daily_brief_last_date",
        "extension_enabled",
        "telegram_enabled",
        "web_push_enabled",
        "muted_kinds",
    }.issubset(columns)
    with old_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT extension_enabled, telegram_enabled, web_push_enabled, muted_kinds "
                "FROM notification_preferences WHERE id = 1"
            )
        ).one()
    assert tuple(row[:3]) == (1, 1, 1)
    assert json.loads(row[3]) == []
