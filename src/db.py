from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")
if _is_sqlite:
    # sqlite:///./data/app.db -> ./data/app.db ; tạo thư mục cha nếu chưa có
    # để tránh "unable to open database file" khi chạy dev lần đầu.
    sqlite_path = Path(settings.database_url.split("sqlite:///", 1)[-1])
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

_connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_runtime_schema() -> None:
    """Small dev/pilot migration for databases created before OAuth state fields."""
    _ensure_user_role_columns()
    _ensure_password_reset_columns()
    _ensure_forgot_password_lockout_columns()
    _ensure_connection_schema()
    _ensure_postgres_fts_schema()
    _ensure_task_columns()
    _ensure_task_cluster_key_scope()
    _ensure_run_queue_schema()
    _ensure_pipeline_resolved_columns()
    _ensure_conversation_summary_columns()
    _ensure_program_event_admin_columns()
    _ensure_reminder_columns()
    _ensure_notification_preference_columns()
    _ensure_routine_columns()
    _ensure_sync_cursor_columns()
    _ensure_task_evidence_columns()
    _ensure_run_language_column()
    _ensure_pipeline_attachment_extract_columns()
    _ensure_message_mailbox_columns()
    _ensure_conversation_project_column()
    _ensure_conversation_favorite_column()
    _ensure_conversation_share_columns()
    _ensure_project_summary_columns()
    _ensure_meeting_note_project_column()
    if engine.dialect.name != "sqlite":
        _ensure_connection_account_constraints()
        return
    columns = {column["name"] for column in inspect(engine).get_columns("connections")}
    additions = {
        "status": "VARCHAR(32) DEFAULT 'connected_pending_sync'",
        "initial_sync_completed": "BOOLEAN DEFAULT 0",
        "last_synced_at": "DATETIME",
        "email_count": "INTEGER DEFAULT 0",
        "last_error": "VARCHAR(1024)",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE connections ADD COLUMN {name} {definition}"))
        if "briefs" in inspect(engine).get_table_names():
            brief_columns = {column["name"] for column in inspect(engine).get_columns("briefs")}
            if "evidence" not in brief_columns:
                connection.execute(text("ALTER TABLE briefs ADD COLUMN evidence JSON DEFAULT '[]'"))
    _ensure_connection_account_constraints()


def _ensure_task_columns() -> None:
    """Add task fields introduced after the original production schema."""
    if "tasks" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
    false_literal = "0" if engine.dialect.name == "sqlite" else "FALSE"
    json_empty_array = "'[]'" if engine.dialect.name == "sqlite" else "'[]'::JSON"
    timestamp_type = "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP WITH TIME ZONE"
    additions = {
        "assignee": "VARCHAR(255)",
        "assignee_ambiguous": f"BOOLEAN DEFAULT {false_literal}",
        # Explainability rule-based (src/services/jira_rules.py) — xem Task 4/5
        # trong jira-detail.drawio (Decision + Audit).
        "decision": "VARCHAR(16)",
        "reasons": f"JSON DEFAULT {json_empty_array}",
        "rule_version": "VARCHAR(32)",
        "reminder_dismiss_count": "INTEGER DEFAULT 0",
        "completed_at": timestamp_type,
    }
    missing = {name: definition for name, definition in additions.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {definition}"))


def _ensure_task_cluster_key_scope() -> None:
    """Sửa unique constraint trên tasks.cluster_key về đúng phạm vi user (2026-08-15).

    Model đã đổi UniqueConstraint("user_id", "cluster_key") từ lâu (xem
    src/models/task.py — comment ghi rõ constraint cũ toàn cục "gộp nhầm việc
    của 2 user có cùng cluster_key trùng nhau"), nhưng create_all không bao
    giờ sửa constraint của bảng đã tồn tại — DB thật vẫn giữ đúng cái bug đã
    được coi là "đã fix": 2 user khác nhau không tạo được task cùng
    cluster_key (vd 2 user cùng sync 1 email broadcast/thông báo chung), lần
    thứ hai sẽ ăn UniqueViolation thay vì insert bình thường."""
    if engine.dialect.name != "postgresql":
        return
    if "tasks" not in inspect(engine).get_table_names():
        return
    existing = {c["name"] for c in inspect(engine).get_unique_constraints("tasks")}
    if "uq_task_user_cluster_key" in existing:
        return
    with engine.begin() as connection:
        if "uq_task_cluster_key" in existing:
            connection.execute(text("ALTER TABLE tasks DROP CONSTRAINT uq_task_cluster_key"))
        connection.execute(
            text("ALTER TABLE tasks ADD CONSTRAINT uq_task_user_cluster_key UNIQUE (user_id, cluster_key)")
        )


def _ensure_task_evidence_columns() -> None:
    """`has_attachment` thêm sau bản gốc — đánh dấu nguồn evidence có file
    đính kèm hay không, để Tasks page hiện badge 📎."""
    if "task_evidence" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("task_evidence")}
    if "has_attachment" in columns:
        return
    false_literal = "0" if engine.dialect.name == "sqlite" else "FALSE"
    with engine.begin() as connection:
        connection.execute(
            text(f"ALTER TABLE task_evidence ADD COLUMN has_attachment BOOLEAN DEFAULT {false_literal}")
        )


def _ensure_run_language_column() -> None:
    """`language` thêm sau bản gốc — ngôn ngữ tóm tắt LLM dùng cho lần Run
    này, cùng tinh thần với cột `timezone` đã có sẵn."""
    if "runs" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("runs")}
    if "language" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE runs ADD COLUMN language VARCHAR(8) DEFAULT 'vi'"))


def _ensure_pipeline_attachment_extract_columns() -> None:
    """`structured_extract` thêm sau bản gốc — kết quả LangExtract theo
    section (trang/sheet/heading), None khi structured extraction tắt/lỗi."""
    if "pipeline_attachment_extracts" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("pipeline_attachment_extracts")}
    if "structured_extract" in columns:
        return
    column_type = "TEXT" if engine.dialect.name == "sqlite" else "JSON"
    with engine.begin() as connection:
        connection.execute(
            text(f"ALTER TABLE pipeline_attachment_extracts ADD COLUMN structured_extract {column_type}")
        )


def _ensure_message_mailbox_columns() -> None:
    """Metadata hộp thư thêm sau bản gốc của bảng `messages` — cần cho đường
    đọc-từ-cache lọc đúng như đường gọi Gmail API trực tiếp."""
    if "messages" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("messages")}
    json_type = "TEXT" if engine.dialect.name == "sqlite" else "JSON"
    bool_default = "0" if engine.dialect.name == "sqlite" else "false"
    wanted = {
        "subject": "TEXT DEFAULT ''",
        "snippet": "TEXT DEFAULT ''",
        "to_addresses": json_type,
        "cc_addresses": json_type,
        "mailbox_email": "VARCHAR(255)",
        "is_unread": f"BOOLEAN DEFAULT {bool_default}",
        "has_marketing_boilerplate": f"BOOLEAN DEFAULT {bool_default}",
    }
    missing = {name: ddl for name, ddl in wanted.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, ddl in missing.items():
            connection.execute(text(f"ALTER TABLE messages ADD COLUMN {name} {ddl}"))


def _ensure_conversation_project_column() -> None:
    """`project_id` thêm sau bản gốc của bảng `conversations` (2026-08-22)."""
    if "conversations" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("conversations")}
    if "project_id" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE conversations ADD COLUMN project_id INTEGER"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_conversations_project_id ON conversations(project_id)")
        )


def _ensure_project_summary_columns() -> None:
    """Cache tóm tắt dự án thêm sau bản gốc của bảng `projects` (2026-08-22)."""
    if "projects" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("projects")}
    wanted = {
        "summary": "TEXT DEFAULT ''",
        "summary_fingerprint": "VARCHAR(64) DEFAULT ''",
        "summary_updated_at": "TIMESTAMP WITH TIME ZONE"
        if engine.dialect.name != "sqlite"
        else "TIMESTAMP",
    }
    missing = {name: ddl for name, ddl in wanted.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, ddl in missing.items():
            connection.execute(text(f"ALTER TABLE projects ADD COLUMN {name} {ddl}"))


def _ensure_meeting_note_project_column() -> None:
    if "meeting_notes" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("meeting_notes")}
    if "project_id" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE meeting_notes ADD COLUMN project_id INTEGER"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_meeting_notes_project_id ON meeting_notes(project_id)"))


def _ensure_pipeline_resolved_columns() -> None:
    """Add identity-resolution audit fields to databases created before TAPB-121.

    `create_all` does not alter an existing table. Without this migration the
    pipeline reaches resolve successfully, then fails while persisting its CP0
    audit row because SQLAlchemy inserts columns PostgreSQL does not have.
    """
    if "pipeline_resolved_items" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("pipeline_resolved_items")}
    false_literal = "0" if engine.dialect.name == "sqlite" else "FALSE"
    additions = {
        "assignee": "VARCHAR(255)",
        "assignee_ambiguous": f"BOOLEAN DEFAULT {false_literal}",
    }
    missing = {name: definition for name, definition in additions.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE pipeline_resolved_items ADD COLUMN {name} {definition}"))


def _ensure_conversation_summary_columns() -> None:
    """Thêm hai cột bộ nhớ ngắn hạn cho bảng conversations đã tồn tại.

    create_all không sửa bảng có sẵn, mà mọi lượt chat đều đọc `summary` ngay ở
    bước dựng ngữ cảnh — thiếu cột là hỏng toàn bộ đường chat, không phải hỏng
    một tính năng phụ.
    """
    if "conversations" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("conversations")}
    additions = {
        "summary": "TEXT DEFAULT ''",
        "summary_through_message_id": "INTEGER",
    }
    missing = {name: definition for name, definition in additions.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE conversations ADD COLUMN {name} {definition}"))
        if "summary" in missing:
            connection.execute(text("UPDATE conversations SET summary = '' WHERE summary IS NULL"))


def _ensure_conversation_favorite_column() -> None:
    """Add the persistent Sidebar favorite flag to existing databases."""
    if "conversations" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("conversations")}
    if "is_favorite" in columns:
        return
    with engine.begin() as connection:
        default = "0" if engine.dialect.name == "sqlite" else "FALSE"
        connection.execute(
            text(f"ALTER TABLE conversations ADD COLUMN is_favorite BOOLEAN DEFAULT {default} NOT NULL")
        )


def _ensure_conversation_share_columns() -> None:
    """Add public sharing fields to existing conversation databases."""
    if "conversations" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("conversations")}
    additions = {
        "share_visibility": "VARCHAR(16) DEFAULT 'private'",
        "share_token": "VARCHAR(96)",
    }
    missing = {name: definition for name, definition in additions.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE conversations ADD COLUMN {name} {definition}"))
        if "share_visibility" in missing:
            connection.execute(text("UPDATE conversations SET share_visibility = 'private' WHERE share_visibility IS NULL"))


def _ensure_program_event_admin_columns() -> None:
    """Thêm lớp quản trị cho bảng `program_events` đã tồn tại (ADR-010).

    Bảng này được tạo bởi lần nhập lịch trước khi có trang quản trị, nên DB nào
    đã nhập feed một lần là đang thiếu đúng những cột dưới đây. Thiếu `status`
    thì mọi truy vấn lịch đều ném lỗi, không phải hỏng một tính năng phụ.
    """
    if "program_events" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("program_events")}
    false_literal = "0" if engine.dialect.name == "sqlite" else "FALSE"
    additions = {
        "origin": "VARCHAR(16) DEFAULT 'feed'",
        "status": "VARCHAR(16) DEFAULT 'published'",
        "locked_fields": "JSON",
        "feed_payload": "JSON",
        "source_conflict": f"BOOLEAN DEFAULT {false_literal}",
        "updated_by": "VARCHAR(64)",
        "updated_at": "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP WITH TIME ZONE",
        "published_at": "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP WITH TIME ZONE",
    }
    missing = {name: ddl for name, ddl in additions.items() if name not in columns}
    if not missing:
        return

    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE program_events ADD COLUMN {name} {definition}"))
        # DEFAULT chỉ áp cho dòng thêm sau. Mốc đã nhập trước đó vẫn NULL, mà
        # NULL status thì bộ lọc `status IN ('published')` loại hết — học viên
        # mất sạch lịch ngay sau khi nâng cấp.
        if "status" in missing:
            connection.execute(
                text("UPDATE program_events SET status = 'published' WHERE status IS NULL")
            )
        if "origin" in missing:
            connection.execute(text("UPDATE program_events SET origin = 'feed' WHERE origin IS NULL"))
        if "source_conflict" in missing:
            connection.execute(
                text(f"UPDATE program_events SET source_conflict = {false_literal} WHERE source_conflict IS NULL")
            )


def _ensure_postgres_fts_schema() -> None:
    """Create the PostgreSQL full-text search column used by retrieval.

    The column is not represented by SQLAlchemy because it is a generated
    ``tsvector`` column.  ``create_all`` therefore cannot add it to an existing
    production database, so keep this small idempotent migration in startup.
    """
    if engine.dialect.name != "postgresql":
        return
    inspector = inspect(engine)
    if "chunks" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION mondaiy_fts(txt text)
                RETURNS tsvector AS $$
                  SELECT to_tsvector('simple', unaccent(coalesce(txt, '')))
                $$ LANGUAGE sql IMMUTABLE
                """
            )
        )
        connection.execute(
            text(
                """
                ALTER TABLE chunks
                ADD COLUMN IF NOT EXISTS fts tsvector
                GENERATED ALWAYS AS (mondaiy_fts(text)) STORED
                """
            )
        )
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_fts ON chunks USING GIN (fts)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_trgm ON chunks USING GIN (text gin_trgm_ops)"))


def _ensure_connection_schema() -> None:
    """Keep existing pilot databases compatible with new connection providers.

    `create_all` creates fresh tables but never adds columns or widens existing
    ones. Jira introduced `external_site_id` and tokens that can exceed the old
    VARCHAR(2048), so both SQLite tests and PostgreSQL production need this
    small forward migration before any Connection query runs.
    """
    inspector = inspect(engine)
    if "connections" not in inspector.get_table_names():
        return
    columns = {column["name"]: column for column in inspector.get_columns("connections")}

    with engine.begin() as connection:
        if "external_site_id" not in columns:
            connection.execute(text("ALTER TABLE connections ADD COLUMN external_site_id VARCHAR(255)"))

        if engine.dialect.name == "postgresql":
            for column_name in ("access_token_encrypted", "refresh_token_encrypted"):
                column = columns.get(column_name)
                if column is not None and column["type"].__class__.__name__.lower() != "text":
                    connection.execute(text(f"ALTER TABLE connections ALTER COLUMN {column_name} TYPE TEXT"))

        # Một Telegram identity chỉ được map tới một user. Partial unique index
        # không ảnh hưởng provider khác và chặn race giữa hai callback song song.
        if engine.dialect.name in {"sqlite", "postgresql"}:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_connections_telegram_identity "
                    "ON connections(provider_user_id) "
                    "WHERE provider = 'telegram' AND provider_user_id IS NOT NULL"
                )
            )


def _ensure_connection_account_constraints() -> None:
    """Migrate the legacy provider-wide uniqueness to account-safe indexes.

    Older databases used one global ``(user_id, provider)`` constraint, which
    made a second Google OAuth callback overwrite or reject the first account.
    PostgreSQL can drop that constraint in place. SQLite needs a small table
    rebuild because it cannot drop a table constraint with ALTER TABLE.
    """
    inspector = inspect(engine)
    if "connections" not in inspector.get_table_names():
        return

    legacy_name = "uq_connection_user_provider"
    unique_constraints = {item["name"] for item in inspector.get_unique_constraints("connections")}
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            if legacy_name in unique_constraints:
                connection.execute(text(f"ALTER TABLE connections DROP CONSTRAINT {legacy_name}"))
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_connection_user_provider_non_google "
                    "ON connections (user_id, provider) WHERE provider <> 'google'"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_connection_user_google_identity "
                    "ON connections (user_id, provider, provider_user_id) "
                    "WHERE provider = 'google' AND provider_user_id IS NOT NULL"
                )
            )
        return

    if engine.dialect.name != "sqlite":
        return

    if unique_constraints:
        _rebuild_sqlite_connections_without_legacy_unique()
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_connection_user_provider_non_google "
                "ON connections (user_id, provider) WHERE provider <> 'google'"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_connection_user_google_identity "
                "ON connections (user_id, provider, provider_user_id) "
                "WHERE provider = 'google' AND provider_user_id IS NOT NULL"
            )
        )


def _rebuild_sqlite_connections_without_legacy_unique() -> None:
    """Rebuild old SQLite pilot tables while retaining every connection row."""
    columns = (
        "id, user_id, provider, account_label, provider_user_id, external_site_id, "
        "access_token_encrypted, refresh_token_encrypted, scopes, expires_at, connected_at, "
        "status, initial_sync_completed, last_synced_at, email_count, last_error"
    )
    create_sql = """
        CREATE TABLE connections__new (
            id INTEGER NOT NULL PRIMARY KEY,
            user_id VARCHAR(128) NOT NULL,
            provider VARCHAR(32) NOT NULL,
            account_label VARCHAR(255),
            provider_user_id VARCHAR(128),
            external_site_id VARCHAR(255),
            access_token_encrypted TEXT,
            refresh_token_encrypted TEXT,
            scopes VARCHAR(512),
            expires_at DATETIME,
            connected_at DATETIME NOT NULL,
            status VARCHAR(32) DEFAULT 'connected_pending_sync',
            initial_sync_completed BOOLEAN DEFAULT 0,
            last_synced_at DATETIME,
            email_count INTEGER DEFAULT 0,
            last_error VARCHAR(1024)
        )
    """
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        transaction = connection.begin()
        try:
            connection.execute(text("ALTER TABLE connections RENAME TO connections__legacy"))
            connection.execute(text(create_sql))
            connection.execute(
                text(f"INSERT INTO connections__new ({columns}) SELECT {columns} FROM connections__legacy")
            )
            connection.execute(text("DROP TABLE connections__legacy"))
            connection.execute(text("ALTER TABLE connections__new RENAME TO connections"))
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_connections_user_id "
                    "ON connections (user_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_connection_user_provider_non_google "
                    "ON connections (user_id, provider) WHERE provider <> 'google'"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_connection_user_google_identity "
                    "ON connections (user_id, provider, provider_user_id) "
                    "WHERE provider = 'google' AND provider_user_id IS NOT NULL"
                )
            )
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def _ensure_user_role_columns() -> None:
    """Thêm các cột profile/RBAC cho bảng users đã tồn tại.

    Khác đoạn migration bên trên ở chỗ nó chạy trên cả postgres: DB pilot đang
    chạy thật cũng thiếu ba cột này, mà create_all không bao giờ sửa bảng đã có.
    Thiếu cột thì mọi truy vấn chạm User đều ném lỗi ngay lúc khởi động.
    """
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"]: column for column in inspector.get_columns("users")}

    # sqlite hiểu 1/0, postgres đòi TRUE/FALSE — dùng chung một chuỗi là hỏng.
    true_literal = "1" if engine.dialect.name == "sqlite" else "TRUE"
    additions = {
        "apple_subject": "VARCHAR(255)",
        "apple_refresh_token_encrypted": "TEXT",
        "display_name": "VARCHAR(120) DEFAULT ''",
        "avatar_url": "VARCHAR(2048)",
        "role": "VARCHAR(16) DEFAULT 'participant'",
        "is_active": f"BOOLEAN DEFAULT {true_literal}",
        "program_access_level": "VARCHAR(1) DEFAULT 'C'",
        "program_cohort_slug": "VARCHAR(64)",
        "auto_sync_enabled": f"BOOLEAN DEFAULT {true_literal}",
        "meeting_summary_quota_day": "VARCHAR(10)",
        "meeting_summaries_used": "INTEGER DEFAULT 0",
        "feedback_attempts": "INTEGER DEFAULT 0",
        "feedback_quality_day": "VARCHAR(10)",
        "feedback_cooldown_until": "TIMESTAMPTZ" if engine.dialect.name != "sqlite" else "DATETIME",
    }
    missing = {name: ddl for name, ddl in additions.items() if name not in columns}
    # password_hash đổi từ NOT NULL sang nullable (tài khoản "Đăng nhập với
    # Google" chưa từng đặt mật khẩu) — cột tạo trước migration này trên DB
    # dev/pilot nên phải tự DROP NOT NULL, create_all không sửa bảng đã có.
    # Kiểm tra độc lập với `missing`: chạy lần 2 trở đi không còn cột nào
    # thiếu, nhưng constraint NOT NULL vẫn còn cho tới khi ALTER này chạy.
    password_hash_column = columns.get("password_hash")
    needs_password_hash_nullable = (
        engine.dialect.name == "postgresql"
        and password_hash_column is not None
        and not password_hash_column.get("nullable", True)
    )
    if not missing and not needs_password_hash_nullable:
        return

    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {definition}"))
        if "apple_subject" in missing:
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_apple_subject ON users(apple_subject)"))
        if needs_password_hash_nullable:
            connection.execute(text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"))
        # DEFAULT chỉ áp cho dòng thêm sau. Các tài khoản đã tồn tại vẫn NULL,
        # mà NULL role thì require_admin so sánh sai và người dùng cũ mất quyền.
        if "role" in missing:
            connection.execute(text("UPDATE users SET role = 'participant' WHERE role IS NULL"))
        if "display_name" in missing:
            connection.execute(text("UPDATE users SET display_name = '' WHERE display_name IS NULL"))
        if "is_active" in missing:
            connection.execute(text(f"UPDATE users SET is_active = {true_literal} WHERE is_active IS NULL"))
        if "program_access_level" in missing:
            connection.execute(text("UPDATE users SET program_access_level = 'C' WHERE program_access_level IS NULL"))
        # NULL ở đây là "chưa quyết", mà find_due_users() lọc bằng is_(True)
        # nên user cũ sẽ im lặng không bao giờ được auto-sync. Ghi giá trị thật.
        if "auto_sync_enabled" in missing:
            connection.execute(
                text(f"UPDATE users SET auto_sync_enabled = {true_literal} WHERE auto_sync_enabled IS NULL")
            )
        if "meeting_summaries_used" in missing:
            connection.execute(text("UPDATE users SET meeting_summaries_used = 0 WHERE meeting_summaries_used IS NULL"))
        if "feedback_attempts" in missing:
            connection.execute(text("UPDATE users SET feedback_attempts = 0 WHERE feedback_attempts IS NULL"))


def _ensure_password_reset_columns() -> None:
    """Thêm cột token đặt lại mật khẩu cho bảng users đã tồn tại (2026-08-14)."""
    if "users" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    timestamp_type = "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP WITH TIME ZONE"
    additions = {
        "reset_token_hash": "VARCHAR(64)",
        "reset_token_expires_at": timestamp_type,
    }
    missing = {name: ddl for name, ddl in additions.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {definition}"))
        if "reset_token_hash" in missing:
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_users_reset_token_hash ON users(reset_token_hash)")
            )


def _ensure_forgot_password_lockout_columns() -> None:
    """Thêm cột khoá tạm per-user cho spam 'quên mật khẩu' (2026-08-15)."""
    if "users" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    timestamp_type = "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP WITH TIME ZONE"
    additions = {
        "reset_request_count": "INTEGER DEFAULT 0",
        "reset_request_window_started_at": timestamp_type,
        "reset_locked_until": timestamp_type,
    }
    missing = {name: ddl for name, ddl in additions.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {definition}"))
        if "reset_request_count" in missing:
            connection.execute(text("UPDATE users SET reset_request_count = 0 WHERE reset_request_count IS NULL"))


def _ensure_reminder_columns() -> None:
    """Mở rộng `reminders` từ chỉ-task_due sang 4 loại thông báo (2026-08-12).

    `task_id` đổi từ NOT NULL sang nullable (conflict_evidence/daily_brief
    không gắn 1 task) — cột này tạo trước migration này trên DB dev nên phải
    tự DROP NOT NULL, `create_all` không sửa constraint của bảng đã có.
    """
    if "reminders" not in inspect(engine).get_table_names():
        return
    columns = {column["name"]: column for column in inspect(engine).get_columns("reminders")}
    json_empty_object = "'{}'" if engine.dialect.name == "sqlite" else "'{}'::JSON"
    additions = {
        "kind": "VARCHAR(32) DEFAULT 'task_due'",
        "related_task_id": "INTEGER",
        "payload": f"JSON DEFAULT {json_empty_object}",
    }
    missing = {name: ddl for name, ddl in additions.items() if name not in columns}

    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE reminders ADD COLUMN {name} {definition}"))
        if "kind" in missing:
            connection.execute(text("UPDATE reminders SET kind = 'task_due' WHERE kind IS NULL"))
        task_id_column = columns.get("task_id")
        if (
            engine.dialect.name == "postgresql"
            and task_id_column is not None
            and not task_id_column.get("nullable", True)
        ):
            connection.execute(text("ALTER TABLE reminders ALTER COLUMN task_id DROP NOT NULL"))


def _ensure_notification_preference_columns() -> None:
    """Thêm giờ nhận daily brief và tuỳ chọn kênh/loại cho bảng đã tồn tại."""
    if "notification_preferences" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("notification_preferences")}
    true_literal = "1" if engine.dialect.name == "sqlite" else "TRUE"
    json_empty_array = "'[]'" if engine.dialect.name == "sqlite" else "'[]'::JSON"
    additions = {
        "daily_brief_hour": "INTEGER",
        "daily_brief_last_date": "VARCHAR(10)",
        # DEFAULT phải là BẬT: dòng cấu hình có sẵn từ trước không khai báo gì
        # về kênh, và mặc định NULL/0 sẽ im lặng cắt hết thông báo của những
        # người đang dùng — kiểu hỏng không ai báo lỗi, chỉ thấy app "hết nhắc".
        "extension_enabled": f"BOOLEAN DEFAULT {true_literal}",
        "telegram_enabled": f"BOOLEAN DEFAULT {true_literal}",
        "web_push_enabled": f"BOOLEAN DEFAULT {true_literal}",
        "muted_kinds": f"JSON DEFAULT {json_empty_array}",
    }
    missing = {name: ddl for name, ddl in additions.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE notification_preferences ADD COLUMN {name} {definition}"))


def _ensure_routine_columns() -> None:
    """Thêm notify_push/notify_email cho bảng routines đã tồn tại (2026-08-14)."""
    if "routines" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("routines")}
    true_literal = "1" if engine.dialect.name == "sqlite" else "TRUE"
    false_literal = "0" if engine.dialect.name == "sqlite" else "FALSE"
    additions = {
        "notify_push": f"BOOLEAN DEFAULT {true_literal}",
        "notify_email": f"BOOLEAN DEFAULT {false_literal}",
    }
    missing = {name: ddl for name, ddl in additions.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE routines ADD COLUMN {name} {definition}"))


def _ensure_sync_cursor_columns() -> None:
    """Thêm user_id cho bảng sync_cursors đã tồn tại (2026-08-15).

    Model đặt `user_id` từ đầu nhưng bảng thật tạo trước đó (chưa từng wire
    vào pipeline, xem TAPB-121) nên create_all không bao giờ thêm cột này vào
    bảng đã có — phát hiện lúc viết account_deletion.py, mọi câu lệnh SELECT/
    DELETE theo user_id trên bảng này đều crash 'column does not exist'."""
    if "sync_cursors" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("sync_cursors")}
    if "user_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE sync_cursors ADD COLUMN user_id VARCHAR(128)"))
            connection.execute(text("UPDATE sync_cursors SET user_id = '' WHERE user_id IS NULL"))
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_sync_cursors_user_id ON sync_cursors(user_id)")
            )
    if engine.dialect.name in {"sqlite", "postgresql"}:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_sync_cursor_user_key "
                    "ON sync_cursors(user_id, key)"
                )
            )


def _ensure_run_queue_schema() -> None:
    """Add queue/quota columns to databases created before the P0 guards."""
    timestamp_type = "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP WITH TIME ZONE"
    additions = {
        "runs": {
            "timezone": "VARCHAR(64) DEFAULT 'UTC'",
            "mode": "VARCHAR(32) DEFAULT 'task_extraction'",
            "attempts": "INTEGER DEFAULT 0",
            "claimed_at": timestamp_type,
        },
        "users": {
            "llm_quota_day": "VARCHAR(10)",
            "llm_questions_used": "INTEGER DEFAULT 0",
            "llm_bonus_questions": "INTEGER DEFAULT 0",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in additions.items():
            if table not in inspector.get_table_names():
                continue
            present = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in present:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
