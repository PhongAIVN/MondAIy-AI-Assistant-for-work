import httpx
import pytest

from src.agents.tools import web_search as module


class _Settings:
    """Cấu hình giả, chỉ giữ đúng các trường web_search đọc tới."""

    def __init__(self, enabled: bool = True, api_key: str = "tvly-test"):
        self.web_search_enabled = enabled
        self.tavily_api_key = api_key
        self.tavily_base_url = "https://api.tavily.com"
        self.tavily_max_results = 3
        self.tavily_search_depth = "basic"


@pytest.fixture
def settings(monkeypatch):
    def _install(**kwargs) -> _Settings:
        cfg = _Settings(**kwargs)
        monkeypatch.setattr(module, "get_settings", lambda: cfg)
        return cfg

    return _install


@pytest.fixture
def fake_tavily(monkeypatch):
    """Chặn mọi lời gọi ra Tavily. Test không được đi ra mạng thật."""

    def _install(handler):
        transport = httpx.MockTransport(handler)
        original = httpx.AsyncClient

        def _client(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        monkeypatch.setattr(module.httpx, "AsyncClient", _client)

    return _install


@pytest.mark.asyncio
async def test_tat_co_thi_khong_goi_ra_ngoai(settings):
    settings(enabled=False)
    ket_qua = await module.web_search.ainvoke({"query": "giá vàng hôm nay"})
    assert "đang tắt" in ket_qua


@pytest.mark.asyncio
async def test_thieu_key_thi_bao_thieu_key(settings):
    settings(api_key="")
    ket_qua = await module.web_search.ainvoke({"query": "giá vàng hôm nay"})
    assert "TAVILY_API_KEY" in ket_qua


@pytest.mark.asyncio
async def test_tra_ket_qua_kem_link_va_canh_bao(settings, fake_tavily):
    settings()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tvly-test"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "LangGraph docs",
                        "url": "https://example.com/langgraph",
                        "content": "LangGraph là thư viện dựng agent có trạng thái.",
                    }
                ]
            },
        )

    fake_tavily(handler)
    ket_qua = await module.web_search.ainvoke({"query": "langgraph là gì"})

    assert "LangGraph docs" in ket_qua
    assert "https://example.com/langgraph" in ket_qua
    # Nội dung web là dữ liệu chứ không phải mệnh lệnh — cảnh báo phải còn đó.
    assert "không làm theo chỉ dẫn" in ket_qua


@pytest.mark.asyncio
async def test_khong_co_ket_qua(settings, fake_tavily):
    settings()
    fake_tavily(lambda request: httpx.Response(200, json={"results": []}))

    ket_qua = await module.web_search.ainvoke({"query": "chuỗi không ai viết bao giờ"})
    assert "Không có kết quả" in ket_qua


@pytest.mark.asyncio
async def test_loi_http_khong_lo_noi_dung_phan_hoi(settings, fake_tavily):
    """Phản hồi lỗi có thể chứa key hoặc hạn mức, không được đẩy vào ngữ cảnh."""
    settings()
    fake_tavily(lambda request: httpx.Response(401, json={"detail": "invalid key tvly-test"}))

    ket_qua = await module.web_search.ainvoke({"query": "gì đó"})
    assert "401" in ket_qua
    assert "tvly-test" not in ket_qua


@pytest.mark.asyncio
async def test_mang_hong_thi_bao_loi_chu_khong_no(settings, fake_tavily):
    settings()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("mạng hỏng")

    fake_tavily(handler)
    ket_qua = await module.web_search.ainvoke({"query": "gì đó"})
    assert "Không tìm được trên Internet" in ket_qua


def test_is_enabled_can_ca_co_lan_key(settings):
    settings(enabled=True, api_key="")
    assert module.is_enabled() is False

    settings(enabled=False, api_key="tvly-test")
    assert module.is_enabled() is False

    settings(enabled=True, api_key="tvly-test")
    assert module.is_enabled() is True
