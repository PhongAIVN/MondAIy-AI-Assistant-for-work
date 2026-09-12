"""Test cho chuỗi Alembic của P-004 (ADR-018).

Không chạy migration lên DB thật — mỗi test tự trỏ DATABASE_URL sang một file
SQLite tạm (tmp_path). alembic/env.py được exec lại từ đầu ở MỖI lần gọi lệnh
(đã tự kiểm chứng: hai test liên tiếp trỏ hai tmp_path khác nhau vẫn ra đúng
DB của từng test), nên chỉ cần monkeypatch `src.config.get_settings` — KHÔNG
đụng `get_settings.cache_clear()` toàn cục. `get_settings()` là `lru_cache`
dùng chung cho cả app (vd. `src.db.settings` chụp instance ngay lúc import),
nhiều test khác monkeypatch thẳng lên instance đó; clear cache giữa chừng suite
làm instance đó lệch khỏi bản mới, và đã tự đo được: patch attribute thay vì
clear cache global tránh làm 3 test khác trong suite bất ngờ đỏ."""

import types
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command

REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


@pytest.fixture
def scratch_db_url(tmp_path, monkeypatch):
    """Trỏ get_settings().database_url (như alembic/env.py đọc) sang một file
    SQLite tạm, chỉ trong phạm vi test này."""
    url = f"sqlite:///{tmp_path / 'scratch.db'}"
    fake_settings = types.SimpleNamespace(database_url=url)
    monkeypatch.setattr("src.config.get_settings", lambda: fake_settings)
    yield url


def test_single_head_and_unbroken_chain():
    """Đúng một head, down_revision nối liền, không có revision mồ côi."""
    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)

    assert script.get_heads() == ["b9d1e4f2a6c8"]

    revisions = list(script.walk_revisions())
    assert {r.revision for r in revisions} == {
        "e01c887a732b",
        "5c3a646a710f",
        "9a42dcf7b631",
        "c4d8f1a2b7e3",
        "d7e2a9c1f4b8",
        "f6b9d12e4a70",
        "a1c4f7e29b30",
        "b9d1e4f2a6c8",
    }

    head_rev = script.get_revision("b9d1e4f2a6c8")
    assert head_rev.down_revision == "a1c4f7e29b30"
    assert script.get_revision("a1c4f7e29b30").down_revision == "f6b9d12e4a70"
    assert script.get_revision("f6b9d12e4a70").down_revision == "d7e2a9c1f4b8"
    assert script.get_revision("d7e2a9c1f4b8").down_revision == "c4d8f1a2b7e3"
    assert script.get_revision("9a42dcf7b631").down_revision == "5c3a646a710f"
    assert script.get_revision("5c3a646a710f").down_revision == "e01c887a732b"
    base_rev = script.get_revision("e01c887a732b")
    assert base_rev.down_revision is None


def test_baseline_upgrade_and_downgrade_emit_no_ddl(scratch_db_url):
    """Baseline rỗng thật sự: upgrade/downgrade không tạo hay xoá bảng nào
    ngoài `alembic_version` (bookkeeping của chính Alembic)."""
    cfg = _alembic_config()

    command.upgrade(cfg, "e01c887a732b")
    engine = sa.create_engine(scratch_db_url)
    tables = set(sa.inspect(engine).get_table_names())
    engine.dispose()
    assert tables == {"alembic_version"}

    command.downgrade(cfg, "base")
    engine = sa.create_engine(scratch_db_url)
    tables = set(sa.inspect(engine).get_table_names())
    with engine.connect() as conn:
        # Alembic không tự xoá bảng bookkeeping `alembic_version` khi downgrade
        # về base — nó chỉ xoá hàng version. Bảng đó không phải DDL do
        # baseline sinh ra nên vẫn được phép còn lại, miễn là rỗng.
        version_rows = conn.execute(sa.text("SELECT * FROM alembic_version")).fetchall()
    engine.dispose()
    assert tables == {"alembic_version"}
    assert version_rows == []


def test_revision_two_round_trip_adds_and_removes_cleanly(scratch_db_url):
    """Dựng `tasks` ở trạng thái trước hai revision, rồi chứng minh upgrade
    thêm đúng cột/bảng và downgrade xoá sạch — không phá dòng dữ liệu cũ."""
    cfg = _alembic_config()

    pre_migration_engine = sa.create_engine(scratch_db_url)
    with pre_migration_engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL,
                    cluster_key VARCHAR(64) NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    detail TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO tasks (id, user_id, cluster_key, title, detail, created_at, updated_at) "
                "VALUES (1, 'u1', 'ck1', 'Việc có sẵn', 'chi tiết', '2026-01-01', '2026-01-01')"
            )
        )
    pre_migration_engine.dispose()

    command.stamp(cfg, "e01c887a732b")
    command.upgrade(cfg, "head")

    engine = sa.create_engine(scratch_db_url)
    inspector = sa.inspect(engine)
    task_columns = {c["name"] for c in inspector.get_columns("tasks")}
    assert {
        "estimate_low_min",
        "estimate_high_min",
        "actual_minutes",
        "depends_on_task_id",
        "energy",
    } <= task_columns
    assert {
        "expected_output",
        "acceptance_criteria",
        "context_input",
        "constraints",
        "execution_tool",
        "execution_method",
        "stated_priority",
        "stakeholders",
        "deliver_to",
    } <= task_columns
    assert "task_steps" in inspector.get_table_names()
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT id, title FROM tasks WHERE id = 1")).fetchone()
    assert row == (1, "Việc có sẵn")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO tasks (id, user_id, cluster_key, title, detail, created_at, updated_at) "
                "VALUES (2, 'u2', 'ck2', 'Task mới', 'chi tiết', '2026-01-01', '2026-01-01')"
            )
        )
        stakeholders = conn.execute(sa.text("SELECT stakeholders FROM tasks WHERE id = 2")).scalar_one()
    assert stakeholders in ([], "[]")
    engine.dispose()

    command.downgrade(cfg, "e01c887a732b")

    engine = sa.create_engine(scratch_db_url)
    inspector = sa.inspect(engine)
    task_columns_after = {c["name"] for c in inspector.get_columns("tasks")}
    assert task_columns_after == {
        "id",
        "user_id",
        "cluster_key",
        "title",
        "detail",
        "created_at",
        "updated_at",
    }
    assert "task_steps" not in inspector.get_table_names()
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT id, title FROM tasks WHERE id = 1")).fetchone()
    assert row == (1, "Việc có sẵn")
    engine.dispose()


def test_fresh_db_where_create_all_already_built_head_stamps_and_upgrades_cleanly(scratch_db_url):
    """Tái hiện đúng lỗi đã báo: create_all() trên model MỚI dựng sẵn 5 cột +
    task_steps, rồi stamp baseline + upgrade head không được ném
    `duplicate column name` nữa."""
    import importlib
    import pkgutil

    import src.models as models_pkg
    from src.db import Base

    for module_info in pkgutil.iter_modules(models_pkg.__path__, prefix="src.models."):
        importlib.import_module(module_info.name)

    engine = sa.create_engine(scratch_db_url)
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    cfg = _alembic_config()
    command.stamp(cfg, "e01c887a732b")
    command.upgrade(cfg, "head")

    engine = sa.create_engine(scratch_db_url)
    inspector = sa.inspect(engine)
    task_columns = {c["name"] for c in inspector.get_columns("tasks")}
    assert {
        "estimate_low_min",
        "energy",
        "depends_on_task_id",
        "expected_output",
        "acceptance_criteria",
        "context_input",
        "constraints",
        "execution_tool",
        "execution_method",
        "stated_priority",
        "stakeholders",
        "deliver_to",
    } <= task_columns
    assert "task_steps" in inspector.get_table_names()
    engine.dispose()
