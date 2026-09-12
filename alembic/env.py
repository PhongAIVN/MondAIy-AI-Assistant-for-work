"""Alembic env — URL và metadata lấy từ đúng nguồn sự thật của app.

Không hardcode connection string, không đọc .env riêng: `get_settings()` đã
làm việc đó (xem src/config.py). `target_metadata` phải thấy ĐỦ bảng, nên ta
import mọi module dưới `src/models/` thay vì import `src.main` (main.py kéo
theo toàn bộ router/side-effect của app, quá nặng và rủi ro cho một migration
runner). `src/models/__init__.py` không import đủ (xem AGENTS.md), nên duyệt
package bằng pkgutil cho chắc.
"""

import importlib
import pkgutil
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import src.models as _models_package
from alembic import context
from src.config import get_settings
from src.db import Base

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False — mặc định True sẽ TẮT mọi logger app đã
    # tạo trước đó (propagate/handlers bị dọn sạch), ảnh hưởng tới bất kỳ code
    # nào chạy alembic trong cùng process (đã tự đo: chạy chung với pytest làm
    # 3 test khác dựa vào caplog bị đỏ vì logger của chúng bị fileConfig tắt).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Đăng ký mọi model vào Base.metadata trước khi dùng làm target_metadata.
for _module_info in pkgutil.iter_modules(_models_package.__path__, prefix=f"{_models_package.__name__}."):
    importlib.import_module(_module_info.name)

target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
