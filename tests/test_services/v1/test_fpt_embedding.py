"""Nhúng qua FPT Cloud marketplace.

Đường nhúng cũ gọi OpenRouter với `nvidia/nemotron-3-embed-1b:free` và hiện trả
402 vì hết credit — RAG chết, trace production cho thấy intent router rơi về
`shared_rag_embedding_unavailable`.

FPT marketplace đã được dùng sẵn cho STT ở P-004, nên `Vietnamese_Embedding` chạy
trên đúng cổng và đúng key đó. Đã kiểm bằng key production: HTTP 200, vector
**1024 chiều**.

Số chiều mới là chỗ dễ hỏng nhất: cột pgvector production đang là `vector(2048)`.
Vì vậy `VECTOR_DIMS` và migration phải khớp nhau, và test dưới khoá điều đó.
"""

from __future__ import annotations

import httpx
import pytest

from src.models.evidence import VECTOR_DIMS
from src.services import retrieval


class _Settings:
    embedding_provider = "fpt"
    fpt_api_key = "test-key"
    fpt_base_url = "https://mkp-api.fptcloud.com"
    fpt_embedding_model = "Vietnamese_Embedding"
    embedding_timeout_seconds = 8.0


def test_vector_dims_khop_provider_dang_cau_hinh() -> None:
    """Lệch số chiều là hỏng lúc ghi DB, không phải lúc gọi API.

    Không khoá cứng 1024: số chiều phụ thuộc provider, và khoá cứng chính là
    lỗi P1 mà review độc lập đã bắt được.
    """
    from src.config import get_settings
    from src.models.evidence import _DIMS_THEO_PROVIDER

    assert VECTOR_DIMS == _DIMS_THEO_PROVIDER[get_settings().embedding_provider]
    assert _DIMS_THEO_PROVIDER["fpt"] == 1024


def test_goi_dung_cong_va_dung_model(monkeypatch) -> None:
    ghi_lai: dict = {}

    def _post(url, headers=None, json=None, timeout=None):
        ghi_lai.update(url=url, headers=headers, json=json, timeout=timeout)
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.1] * VECTOR_DIMS}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(retrieval, "get_settings", lambda: _Settings())
    monkeypatch.setattr(retrieval.httpx, "post", _post)

    ket_qua = retrieval.embed_queries(["nộp báo cáo tuần"])

    assert ghi_lai["url"] == "https://mkp-api.fptcloud.com/v1/embeddings"
    assert ghi_lai["json"]["model"] == "Vietnamese_Embedding"
    assert ghi_lai["headers"]["Authorization"] == "Bearer test-key"
    assert len(ket_qua) == 1
    assert len(ket_qua[0]) == VECTOR_DIMS


def test_giu_dung_thu_tu_theo_index(monkeypatch) -> None:
    """API có thể trả không đúng thứ tự; ghép nhầm vector với câu là sai âm thầm."""

    def _post(url, headers=None, json=None, timeout=None):
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [2.0] * VECTOR_DIMS},
                    {"index": 0, "embedding": [1.0] * VECTOR_DIMS},
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(retrieval, "get_settings", lambda: _Settings())
    monkeypatch.setattr(retrieval.httpx, "post", _post)

    a, b = retrieval.embed_queries(["câu một", "câu hai"])

    assert a[0] == 1.0
    assert b[0] == 2.0


def test_thieu_key_thi_no_to_chu_khong_tra_rong(monkeypatch) -> None:
    """Embedding rỗng làm truy hồi trả kết quả sai mà không ai biết vì sao."""

    class _KhongKey(_Settings):
        fpt_api_key = ""

    monkeypatch.setattr(retrieval, "get_settings", lambda: _KhongKey())

    with pytest.raises(RuntimeError, match="FPT_API_KEY"):
        retrieval.embed_queries(["gì đó"])


def test_provider_openrouter_khong_di_qua_duong_fpt(monkeypatch) -> None:
    """Cờ provider phải thật sự quyết định đường đi, không chỉ là trang trí."""

    class _OpenRouter(_Settings):
        embedding_provider = "openrouter"

    da_goi: list[int] = []

    class _DiDungNhanhOpenRouterError(RuntimeError):
        """Sentinel: tới được đây nghĩa là đã rẽ vào nhánh openrouter."""

    monkeypatch.setattr(retrieval, "get_settings", lambda: _OpenRouter())
    monkeypatch.setattr(retrieval, "_embed_qua_fpt", lambda *a, **k: da_goi.append(1))
    monkeypatch.setattr(
        retrieval,
        "build_openrouter_key_pool",
        lambda: (_ for _ in ()).throw(_DiDungNhanhOpenRouterError()),
    )

    with pytest.raises(_DiDungNhanhOpenRouterError):
        retrieval.embed_queries(["gì đó"])
    assert not da_goi, "provider=openrouter mà vẫn gọi đường FPT"


def test_vector_dims_theo_provider_dang_cau_hinh(monkeypatch) -> None:
    """Hằng số cố định là bẫy cho lần CÀI MỚI.

    `EMBEDDING_PROVIDER` mặc định vẫn là openrouter (model trả 2048). Nếu
    VECTOR_DIMS cứng ở 1024 thì cài mới tạo cột 1024 rồi nhúng 2048 vào —
    hỏng ngay lệnh ghi đầu tiên, ở một máy hoàn toàn sạch.
    """
    from src.models import evidence

    assert evidence._DIMS_THEO_PROVIDER == {"openrouter": 2048, "fpt": 1024}

    class _S:
        embedding_provider = "fpt"

    monkeypatch.setattr(evidence, "get_settings", lambda: _S(), raising=False)
    import src.config as config_module

    monkeypatch.setattr(config_module, "get_settings", lambda: _S())
    assert evidence._vector_dims() == 1024

    class _S2:
        embedding_provider = "openrouter"

    monkeypatch.setattr(config_module, "get_settings", lambda: _S2())
    assert evidence._vector_dims() == 2048


def test_nhan_model_la_model_that_su_sinh_ra_vector(monkeypatch) -> None:
    """Nhãn sai làm lần đổi model sau bỏ qua re-embed, và không ai biết."""

    class _Fpt(_Settings):
        embedding_model = "nvidia/nemotron-3-embed-1b:free"

    class _Or(_Settings):
        embedding_provider = "openrouter"
        embedding_model = "nvidia/nemotron-3-embed-1b:free"

    monkeypatch.setattr(retrieval, "get_settings", lambda: _Fpt())
    assert retrieval.active_embedding_model() == "Vietnamese_Embedding"

    monkeypatch.setattr(retrieval, "get_settings", lambda: _Or())
    assert retrieval.active_embedding_model() == "nvidia/nemotron-3-embed-1b:free"


def test_fpt_thu_lai_khi_loi_tam_thoi(monkeypatch) -> None:
    """429/5xx là lỗi TẠM. Ném thẳng lên làm mất luôn kết quả FTS đã lấy."""
    lan = {"n": 0}

    def _post(url, headers=None, json=None, timeout=None):
        lan["n"] += 1
        if lan["n"] < 3:
            return httpx.Response(503, json={}, request=httpx.Request("POST", url))
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.3] * 1024}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(retrieval, "get_settings", lambda: _Settings())
    monkeypatch.setattr(retrieval.httpx, "post", _post)
    monkeypatch.setattr(retrieval.time, "sleep", lambda _s: None)

    ket_qua = retrieval.embed_queries(["gì đó"])

    assert lan["n"] == 3, "phải thử lại chứ không bỏ cuộc ngay"
    assert len(ket_qua[0]) == 1024


def test_loi_that_su_thi_khong_thu_lai(monkeypatch) -> None:
    """401/403 là sai cấu hình — thử lại chỉ làm chậm lúc chẩn đoán."""
    lan = {"n": 0}

    def _post(url, headers=None, json=None, timeout=None):
        lan["n"] += 1
        return httpx.Response(401, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr(retrieval, "get_settings", lambda: _Settings())
    monkeypatch.setattr(retrieval.httpx, "post", _post)

    with pytest.raises(httpx.HTTPStatusError):
        retrieval.embed_queries(["gì đó"])
    assert lan["n"] == 1
