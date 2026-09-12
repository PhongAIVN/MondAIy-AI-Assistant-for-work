import base64

import pytest

from src.connectors.gmail import GmailConnector


class _FakeConnection:
    def __init__(self, provider_user_id: str = "me@example.test") -> None:
        self.provider_user_id = provider_user_id


class _FakeResponse:
    def __init__(self, status_code: int, json_data: dict) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.headers: dict = {}

    def json(self) -> dict:
        return self._json_data


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.requested_paths: list[str] = []

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        self.requested_paths.append(url)
        return self._response


def _connector(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> tuple[GmailConnector, _FakeAsyncClient]:
    connector = GmailConnector(_FakeConnection(), db=None)
    monkeypatch.setattr(connector, "_access_token", lambda: _async_return("fake-token"))
    fake_client = _FakeAsyncClient(response)
    monkeypatch.setattr("src.connectors.gmail.httpx.AsyncClient", lambda **kwargs: fake_client)
    return connector, fake_client


async def _async_return(value):
    return value


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.mark.asyncio
async def test_download_attachment_decodes_binary_bytes_correctly(monkeypatch: pytest.MonkeyPatch):
    original_bytes = b"%PDF-1.4 fake pdf binary content \x00\x01\x02"
    response = _FakeResponse(200, {"size": len(original_bytes), "data": _b64url(original_bytes)})
    connector, fake_client = _connector(monkeypatch, response)

    result = await connector.download_attachment("msg-1", "att-1")

    assert result == original_bytes
    assert fake_client.requested_paths == ["https://gmail.googleapis.com/gmail/v1/users/me/messages/msg-1/attachments/att-1"]


@pytest.mark.asyncio
async def test_download_attachment_raises_on_api_error(monkeypatch: pytest.MonkeyPatch):
    from src.connectors.gmail import GmailAPIError

    response = _FakeResponse(404, {})
    connector, _ = _connector(monkeypatch, response)

    with pytest.raises(GmailAPIError):
        await connector.download_attachment("msg-1", "missing-attachment")
