from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.config import Settings


def test_default_redis_url_targets_local_daemon_for_host_backend():
    settings = Settings(_env_file=None)
    assert settings.redis_url == "redis://localhost:6379/0"


def test_local_compose_exposes_redis_for_host_backend():
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))

    assert "${REDIS_HOST_PORT:-6379}:6379" in compose["services"]["redis"]["ports"]


def test_program_cohort_slug_is_required(monkeypatch):
    monkeypatch.delenv("PROGRAM_COHORT_SLUG", raising=False)

    with pytest.raises(ValidationError, match="program_cohort_slug"):
        Settings(_env_file=None)


def test_app_timezone_is_required(monkeypatch):
    monkeypatch.delenv("APP_TIMEZONE", raising=False)

    with pytest.raises(ValidationError, match="app_timezone"):
        Settings(_env_file=None)
