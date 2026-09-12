import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from src.services import gmail_tools
from src.services.gmail_recall import GmailSweepFamily, build_gmail_sweep_plan


class _Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _Connector:
    calls: list[tuple[str, dict | None]] = []

    def __init__(self, connection, db):
        self.connection = connection

    async def _access_token(self):
        return "test-token"

    async def _get(self, client, path, params=None):
        self.calls.append((path, params))
        if path == "/messages":
            return {"messages": [{"id": "m-noise"}, {"id": "m-action"}]}
        return {"id": path.rsplit("/", 1)[-1], "payload": {"headers": []}}

    def normalize(self, raw, source):
        if raw["id"] == "m-noise":
            return {"id": raw["id"], "subject": "Newsletter: ten inbox tips", "text": "unsubscribe sale"}
        return {"id": raw["id"], "subject": "Submit project report by Friday", "text": "Please submit the report by Friday."}


@pytest.fixture(autouse=True)
def _fake_gmail(monkeypatch):
    _Connector.calls = []
    monkeypatch.setattr(gmail_tools, "GmailConnector", _Connector)
    monkeypatch.setattr(
        gmail_tools,
        "_connection_for_user",
        lambda db, user_id: SimpleNamespace(provider_user_id="student@example.com"),
    )
    monkeypatch.setattr(gmail_tools.httpx, "AsyncClient", lambda **kwargs: _Client())


def test_deadline_sweep_has_independent_families_and_wide_temporal_backstop():
    start = datetime(2026, 8, 12, tzinfo=UTC)
    end = datetime(2026, 8, 13, tzinfo=UTC)
    plan = build_gmail_sweep_plan(start, end)

    assert [item.family for item in plan] == [
        GmailSweepFamily.DIRECT,
        GmailSweepFamily.ACTION,
        GmailSweepFamily.TEMPORAL,
        GmailSweepFamily.RELATIONSHIP,
        GmailSweepFamily.ACTIVE,
        GmailSweepFamily.SUBJECT,
    ]
    assert plan[0].time_from == datetime(2026, 2, 13, tzinfo=UTC)
    assert plan[0].time_to == datetime(2027, 2, 9, tzinfo=UTC)
    assert "deadline" not in plan[0].query
    assert "submit" in plan[1].query


@pytest.mark.asyncio
async def test_deadline_sweep_deduplicates_candidates_and_preserves_partial_receipt(monkeypatch):
    calls = []

    async def fake_search(db, user_id, time_from, time_to, query="", max_results=12):
        calls.append(query)
        if "month" in query:
            raise RuntimeError("page timeout")
        return [{"id": "same", "subject": query}]

    monkeypatch.setattr(gmail_tools, "search_gmail_messages", fake_search)
    messages, receipts = await gmail_tools.search_gmail_deadline_candidates(
        object(), "user-1", datetime(2026, 8, 12, tzinfo=UTC), datetime(2026, 8, 13, tzinfo=UTC),
        query="from:mentor@example.com",
    )

    assert len(calls) == 7
    assert [message["id"] for message in messages] == ["same"]
    assert any(item.status == "partial" and item.family == GmailSweepFamily.TEMPORAL for item in receipts)
    assert any(item.family == GmailSweepFamily.TARGETED for item in receipts)


@pytest.mark.asyncio
async def test_deadline_sweeps_run_concurrently_with_a_bounded_concurrency(monkeypatch):
    active = 0
    maximum = 0

    async def fake_search(db, user_id, time_from, time_to, query="", max_results=12):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return [{"id": query}]

    monkeypatch.setattr(gmail_tools, "search_gmail_messages", fake_search)
    messages, receipts = await gmail_tools.search_gmail_deadline_candidates(
        object(), "user-1", datetime(2026, 8, 12, tzinfo=UTC), datetime(2026, 8, 13, tzinfo=UTC),
    )

    assert len(receipts) == 6
    assert len(messages) == 6
    assert 1 < maximum <= gmail_tools.GMAIL_SWEEP_CONCURRENCY


@pytest.mark.asyncio
async def test_search_gmail_filters_noise_before_returning_agent_evidence():
    messages = await gmail_tools.search_gmail_messages(
        object(),
        "user-1",
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 8, 2, tzinfo=UTC),
        query="from:mentor@example.com",
        max_results=999,
    )

    assert [message["id"] for message in messages] == ["m-action"]
    assert messages[0]["importance"] in {"important", "critical"}
    path, params = _Connector.calls[0]
    assert path == "/messages"
    assert params["maxResults"] == gmail_tools.MAX_FILTER_CANDIDATES
    assert "from:mentor@example.com" in params["q"]
    assert f"after:{int(datetime(2026, 8, 1, tzinfo=UTC).timestamp())}" in params["q"]
    assert f"before:{int(datetime(2026, 8, 2, tzinfo=UTC).timestamp())}" in params["q"]
    assert [path for path, _ in _Connector.calls[1:]] == ["/messages/m-noise", "/messages/m-action"]


@pytest.mark.asyncio
async def test_search_gmail_uses_offline_index_without_calling_gmail_api(monkeypatch):
    cached = {
        "id": "cached-1",
        "provider": "google",
        "source_id": "INBOX",
        "author_id": "mentor@example.com",
        "author_name": "Mentor",
        "text": "Please review the Parkwave report by Friday.",
        "sent_at": datetime(2026, 7, 10, tzinfo=UTC),
        "deep_link": "https://mail.google.com/mail/u/0/#all/cached-1",
        "capture_mode": "offline_index",
    }
    monkeypatch.setattr(gmail_tools, "_cached_gmail_messages", lambda *args, **kwargs: (True, [cached]))

    messages = await gmail_tools.search_gmail_messages(
        object(),
        "user-1",
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 8, 1, tzinfo=UTC),
        query="Parkwave",
    )

    assert messages[0]["id"] == "cached-1"
    assert messages[0]["capture_mode"] == "offline_index"
    assert _Connector.calls == []


@pytest.mark.asyncio
async def test_read_gmail_fetches_only_the_selected_message():
    message = await gmail_tools.read_gmail_message(object(), "user-1", "m-42")

    assert message["id"] == "m-42"
    assert message["subject"] == "Submit project report by Friday"
    assert _Connector.calls == [("/messages/m-42", {"format": "full"})]
