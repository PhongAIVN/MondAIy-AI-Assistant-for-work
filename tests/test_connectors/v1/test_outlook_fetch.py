from datetime import UTC, datetime

import pytest

from src.connectors.base import Source
from src.connectors.outlook import API_BASE, OutlookAPIError, OutlookConnector


class _FakeConnection:
    def __init__(self, provider_user_id: str | None = "me@outlook.com") -> None:
        self.provider_user_id = provider_user_id


def _connector() -> OutlookConnector:
    return OutlookConnector(_FakeConnection(), db=None)


class _FakeAsyncClient:
    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeResponse:
    def __init__(self, status_code: int, json_data: dict | None = None, headers: dict | None = None) -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {}

    def json(self) -> dict:
        return self._json_data


def _metadata_item(
    item_id: str, *, is_read: bool = True, importance: str = "normal", subject: str = "", body_preview: str = ""
) -> dict:
    return {
        "id": item_id,
        "subject": subject,
        "from": {"emailAddress": {"address": "sender@example.com"}},
        "receivedDateTime": "2026-08-13T09:00:00Z",
        "isRead": is_read,
        "importance": importance,
        "bodyPreview": body_preview,
        "conversationId": "conv-1",
        "webLink": f"https://outlook.office.com/mail/inbox/id/{item_id}",
    }


def _full_message(item_id: str) -> dict:
    return {
        "id": item_id,
        "subject": "Deadline nộp báo cáo",
        "from": {"emailAddress": {"address": "sender@example.com", "name": "Sender"}},
        "toRecipients": [],
        "ccRecipients": [],
        "receivedDateTime": "2026-08-13T09:00:00Z",
        "body": {"contentType": "text", "content": "Nội dung"},
        "isRead": True,
        "conversationId": "conv-1",
        "webLink": f"https://outlook.office.com/mail/inbox/id/{item_id}",
        "hasAttachments": False,
    }


def _patch_async_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.connectors.outlook.httpx.AsyncClient", lambda **kwargs: _FakeAsyncClient())


# ---------------------------------------------------------------------------
# _get: retry/rate-limit — chưa từng có test trước khi thêm file này.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_json_on_200(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
            return _FakeResponse(200, json_data={"value": [1, 2, 3]})

    connector = _connector()
    result = await connector._get(FakeClient(), f"{API_BASE}/messages")

    assert result == {"value": [1, 2, 3]}


@pytest.mark.asyncio
async def test_get_retries_on_rate_limit_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            _FakeResponse(429, headers={"retry-after": "0"}),
            _FakeResponse(200, json_data={"ok": True}),
        ]
    )
    calls = []

    class FakeClient:
        async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
            calls.append(url)
            return next(responses)

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("src.connectors.outlook.asyncio.sleep", fake_sleep)
    connector = _connector()

    result = await connector._get(FakeClient(), f"{API_BASE}/messages")

    assert result == {"ok": True}
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_get_raises_after_exhausting_rate_limit_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
            return _FakeResponse(429, headers={"retry-after": "0"})

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("src.connectors.outlook.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("src.connectors.outlook._MAX_RATE_LIMIT_RETRIES", 1)
    connector = _connector()

    with pytest.raises(OutlookAPIError):
        await connector._get(FakeClient(), f"{API_BASE}/messages")


@pytest.mark.asyncio
async def test_get_raises_on_non_200_status() -> None:
    class FakeClient:
        async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
            return _FakeResponse(404)

    connector = _connector()

    with pytest.raises(OutlookAPIError):
        await connector._get(FakeClient(), f"{API_BASE}/messages")


# ---------------------------------------------------------------------------
# fetch_range: permission, evidence-first pre-filter, pagination, partial
# failure — pipeline auth-thật đã dùng hàm này nhưng chưa có test nào gọi nó.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_range_propagates_access_token_error(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = _connector()

    async def fake_token() -> str:
        raise OutlookAPIError("Không lấy được access token Outlook: revoked")

    monkeypatch.setattr(connector, "_access_token", fake_token)

    with pytest.raises(OutlookAPIError):
        await connector.fetch_range(
            Source(id="inbox", name="Hộp thư chính"),
            datetime(2026, 8, 1, tzinfo=UTC),
            datetime(2026, 8, 31, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_fetch_range_paginates_and_only_fetches_full_body_for_signalled_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unread = _metadata_item("m-unread", is_read=False)
    high_importance = _metadata_item("m-important", importance="high")
    no_signal = _metadata_item("m-noise", subject="fyi", body_preview="no action here")
    keyword_hit = _metadata_item("m-keyword", body_preview="deadline nộp báo cáo thứ 6")

    call_log: list[tuple[str, dict | None]] = []

    async def fake_get(client: object, url: str, params: dict | None = None) -> dict:
        call_log.append((url, params))
        if url == f"{API_BASE}/mailFolders/inbox/messages":
            return {"value": [unread, high_importance, no_signal], "@odata.nextLink": "NEXT_PAGE"}
        if url == "NEXT_PAGE":
            return {"value": [keyword_hit]}
        message_id = url.rsplit("/", 1)[-1]
        return _full_message(message_id)

    connector = _connector()

    async def fake_token() -> str:
        return "token"

    monkeypatch.setattr(connector, "_access_token", fake_token)
    monkeypatch.setattr(connector, "_get", fake_get)
    _patch_async_client(monkeypatch)

    on_item_calls: list[str] = []
    result = await connector.fetch_range(
        Source(id="inbox", name="Hộp thư chính"),
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 8, 31, tzinfo=UTC),
        on_item=lambda raw, label: on_item_calls.append(raw["id"]),
    )

    assert [m["id"] for m in result] == ["m-unread", "m-important", "m-keyword"]
    assert on_item_calls == ["m-unread", "m-important", "m-keyword"]
    # 2 trang metadata + 3 full-body fetch = 5, "m-noise" không được fetch full body.
    assert len(call_log) == 5
    first_call_params = call_log[0][1]
    assert first_call_params["$select"] == (
        "id,subject,from,receivedDateTime,isRead,importance,bodyPreview,conversationId,webLink"
    )
    assert "receivedDateTime ge 2026-08-01" in first_call_params["$filter"]
    assert "receivedDateTime le 2026-08-31" in first_call_params["$filter"]


@pytest.mark.asyncio
async def test_fetch_range_skips_message_when_full_body_fetch_fails_but_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item1 = _metadata_item("m-ok", is_read=False)
    item2 = _metadata_item("m-broken", is_read=False)

    async def fake_get(client: object, url: str, params: dict | None = None) -> dict:
        if url == f"{API_BASE}/mailFolders/inbox/messages":
            return {"value": [item1, item2]}
        message_id = url.rsplit("/", 1)[-1]
        if message_id == "m-broken":
            raise OutlookAPIError("Graph API lỗi 500")
        return _full_message(message_id)

    connector = _connector()

    async def fake_token() -> str:
        return "token"

    monkeypatch.setattr(connector, "_access_token", fake_token)
    monkeypatch.setattr(connector, "_get", fake_get)
    _patch_async_client(monkeypatch)

    result = await connector.fetch_range(
        Source(id="inbox", name="Hộp thư chính"),
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 8, 31, tzinfo=UTC),
    )

    assert [m["id"] for m in result] == ["m-ok"]


@pytest.mark.asyncio
async def test_fetch_range_stops_collecting_candidates_after_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [_metadata_item(f"m-{i}", is_read=False) for i in range(3)]

    async def fake_get(client: object, url: str, params: dict | None = None) -> dict:
        if url == f"{API_BASE}/mailFolders/inbox/messages":
            return {"value": items, "@odata.nextLink": "NEXT_PAGE"}
        if url == "NEXT_PAGE":
            raise AssertionError("không được gọi trang tiếp theo sau khi đã chạm cap")
        message_id = url.rsplit("/", 1)[-1]
        return _full_message(message_id)

    connector = _connector()

    async def fake_token() -> str:
        return "token"

    monkeypatch.setattr(connector, "_access_token", fake_token)
    monkeypatch.setattr(connector, "_get", fake_get)
    monkeypatch.setattr("src.connectors.outlook._MAX_METADATA_CANDIDATES", 2)
    _patch_async_client(monkeypatch)

    result = await connector.fetch_range(
        Source(id="inbox", name="Hộp thư chính"),
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 8, 31, tzinfo=UTC),
    )

    assert [m["id"] for m in result] == ["m-0", "m-1"]
