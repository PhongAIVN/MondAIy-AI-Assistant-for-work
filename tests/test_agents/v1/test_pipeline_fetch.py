import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.agents.pipeline.nodes.fetch import fetch_node
from src.connectors.calendar import CalendarConnector
from src.connectors.gmail import GmailConnector
from src.connectors.jira import JiraConnector
from src.connectors.registry import CONNECTORS_BY_PROVIDER, resolve_connector
from src.db import Base
from src.models.connection import Connection
from src.models.run import Run

_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine)


@pytest.fixture
def db_and_run():
    db = _SessionLocal()
    run = Run(
        user_id=1,
        sources=[],
        range_from=datetime.now(UTC),
        range_to=datetime.now(UTC),
        idempotency_key=f"test-fetch-node-{uuid.uuid4()}",
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        yield db, run
    finally:
        db.close()


def _connection(db, user_id: str, provider: str) -> Connection:
    row = Connection(user_id=user_id, provider=provider, account_label="acc")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


async def _fake_fetch_range(self, source, time_from, time_to, on_item=None):
    return []


def _fake_fetch_range_with_items(items: list[tuple[dict, str]]):
    async def _fetch(self, source, time_from, time_to, on_item=None):
        raw_items = []
        for raw, label in items:
            raw_items.append(raw)
            if on_item is not None:
                on_item(raw, label)
        return raw_items

    return _fetch


def test_fetch_node_dispatches_google_to_gmail_connector(db_and_run, monkeypatch):
    db, run = db_and_run
    monkeypatch.setattr(GmailConnector, "fetch_range", _fake_fetch_range)
    connection = _connection(db, "u1", "google")
    state = {
        "db": db,
        "run_id": run.id,
        "user_id": "u1",
        "sources": [{"connection_id": connection.id, "source_id": "INBOX"}],
        "time_from": datetime.now(UTC),
        "time_to": datetime.now(UTC),
    }

    result = asyncio.run(fetch_node(state))

    assert result["errors"] == []
    assert len(result["raw_messages"]) == 1
    assert isinstance(result["raw_messages"][0]["connector"], GmailConnector)


def test_fetch_node_dispatches_namespaced_google_calendar_source(db_and_run, monkeypatch):
    db, run = db_and_run
    seen_source_ids: list[str] = []

    async def fake_calendar_fetch(self, source, time_from, time_to, on_item=None):
        seen_source_ids.append(source.id)
        return []

    monkeypatch.setattr(CalendarConnector, "fetch_range", fake_calendar_fetch)
    connection = _connection(db, "u-calendar", "google")
    state = {
        "db": db,
        "run_id": run.id,
        "user_id": "u-calendar",
        "sources": [{"connection_id": connection.id, "source_id": "calendar:primary"}],
        "time_from": datetime.now(UTC),
        "time_to": datetime.now(UTC),
    }

    result = asyncio.run(fetch_node(state))

    assert result["errors"] == []
    assert isinstance(result["raw_messages"][0]["connector"], CalendarConnector)
    assert seen_source_ids == ["primary"]


def test_fetch_node_dispatches_jira_to_jira_connector(db_and_run, monkeypatch):
    db, run = db_and_run
    monkeypatch.setattr(JiraConnector, "fetch_range", _fake_fetch_range)
    connection = _connection(db, "u1", "jira")
    state = {
        "db": db,
        "run_id": run.id,
        "user_id": "u1",
        "sources": [{"connection_id": connection.id, "source_id": "PROJ"}],
        "time_from": datetime.now(UTC),
        "time_to": datetime.now(UTC),
    }

    result = asyncio.run(fetch_node(state))

    assert result["errors"] == []
    assert len(result["raw_messages"]) == 1
    assert isinstance(result["raw_messages"][0]["connector"], JiraConnector)


def test_fetch_node_records_error_for_unknown_provider_without_crashing(db_and_run):
    db, run = db_and_run
    connection = _connection(db, "u1", "notion")
    state = {
        "db": db,
        "run_id": run.id,
        "user_id": "u1",
        "sources": [{"connection_id": connection.id, "source_id": "x"}],
        "time_from": datetime.now(UTC),
        "time_to": datetime.now(UTC),
    }

    result = asyncio.run(fetch_node(state))

    assert result["raw_messages"] == []
    assert len(result["errors"]) == 1
    assert "chưa cắm vào pipeline" in result["errors"][0]


def test_connector_registry_exposes_both_google_products_and_jira():
    assert [binding.namespace for binding in CONNECTORS_BY_PROVIDER["google"]] == ["gmail", "calendar"]
    assert [binding.connector_cls for binding in CONNECTORS_BY_PROVIDER["google"]] == [
        GmailConnector,
        CalendarConnector,
    ]
    assert CONNECTORS_BY_PROVIDER["jira"][0].connector_cls is JiraConnector


def test_connector_registry_keeps_legacy_unprefixed_google_sources_on_gmail():
    connector_cls, source_id = resolve_connector("google", "INBOX")
    assert connector_cls is GmailConnector
    assert source_id == "INBOX"


def test_connector_registry_rejects_unknown_google_namespace():
    with pytest.raises(ValueError, match="namespace"):
        resolve_connector("google", "drive:root")


def test_fetch_node_calls_publish_progress_once_per_item_with_running_count(db_and_run, monkeypatch):
    db, run = db_and_run
    items = [({"id": "m1"}, "Mail một"), ({"id": "m2"}, "Mail hai"), ({"id": "m3"}, "Mail ba")]
    monkeypatch.setattr(GmailConnector, "fetch_range", _fake_fetch_range_with_items(items))
    user_id = f"u-{uuid.uuid4()}"
    connection = _connection(db, user_id, "google")

    calls: list[tuple[str, int, str]] = []
    state = {
        "db": db,
        "run_id": run.id,
        "user_id": user_id,
        "sources": [{"connection_id": connection.id, "source_id": "INBOX"}],
        "time_from": datetime.now(UTC),
        "time_to": datetime.now(UTC),
        "publish_progress": lambda source_id, count, label: calls.append((source_id, count, label)),
    }

    result = asyncio.run(fetch_node(state))

    assert len(result["raw_messages"][0]["raw_items"]) == 3
    assert calls == [("INBOX", 1, "Mail một"), ("INBOX", 2, "Mail hai"), ("INBOX", 3, "Mail ba")]


def test_fetch_node_keeps_separate_counters_per_source(db_and_run, monkeypatch):
    db, run = db_and_run
    monkeypatch.setattr(
        GmailConnector,
        "fetch_range",
        _fake_fetch_range_with_items([({"id": "a1"}, "A1"), ({"id": "a2"}, "A2")]),
    )
    monkeypatch.setattr(
        JiraConnector,
        "fetch_range",
        _fake_fetch_range_with_items([({"id": "b1"}, "B1")]),
    )
    shared_user = f"u-{uuid.uuid4()}"
    google_conn = _connection(db, shared_user, "google")
    jira_conn = _connection(db, shared_user, "jira")

    calls: list[tuple[str, int, str]] = []
    state = {
        "db": db,
        "run_id": run.id,
        "user_id": shared_user,
        "sources": [
            {"connection_id": google_conn.id, "source_id": "INBOX"},
            {"connection_id": jira_conn.id, "source_id": "PROJ"},
        ],
        "time_from": datetime.now(UTC),
        "time_to": datetime.now(UTC),
        "publish_progress": lambda source_id, count, label: calls.append((source_id, count, label)),
    }

    asyncio.run(fetch_node(state))

    counts_by_source = {source_id: count for source_id, count, _ in calls}
    assert counts_by_source["INBOX"] == 2
    assert counts_by_source["PROJ"] == 1
